"""End to end through the API against a throwaway Postgres database.

Runs only when TEST_DB_URL is set, e.g.
    TEST_DB_URL=postgresql+psycopg2://postgres:root@localhost:5432/dag_test pytest tests/test_api_flow.py
Every table in that database is dropped and recreated.
"""
import json
import os
from pathlib import Path

import networkx as nx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DB_URL"), reason="TEST_DB_URL not set")

ROOT = Path(__file__).resolve().parents[1]
TABLES = ["answer_boxes", "worksheet_items", "worksheets", "assignments", "student_mastery", "questions",
          "skill_prerequisites", "skills", "class_students", "classes", "users", "organizations"]


def create_database_if_missing(url):
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}).scalar():
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="module")
def seeded():
    from db.connection import get_engine
    from importer.excel_reader import read_sheet, to_prerequisite_rows, to_skills_table
    from importer.sync import apply_sync, plan_sync

    create_database_if_missing(os.environ["TEST_DB_URL"])
    engine = get_engine()
    with engine.begin() as conn:
        for t in TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))
        conn.exec_driver_sql((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))

        raw = read_sheet(ROOT / "algebra.xlsx")
        skills, (prereqs, _) = to_skills_table(raw), to_prerequisite_rows(raw)
        apply_sync(conn, plan_sync(conn, skills, prereqs), skills, prereqs)

        org = conn.execute(text("INSERT INTO organizations (name) VALUES ('Test school') RETURNING id")).scalar()
        teacher = conn.execute(text("INSERT INTO users (org_id, full_name, role) VALUES (:o, 'T', 'teacher') RETURNING id"), {"o": org}).scalar()
        students = [conn.execute(text("INSERT INTO users (org_id, full_name, role) VALUES (:o, :n, 'student') RETURNING id"),
                                 {"o": org, "n": n}).scalar() for n in ("new", "mid")]
        klass = conn.execute(text("INSERT INTO classes (org_id, teacher_id, name, grade_level, school_year) "
                                  "VALUES (:o, :t, '6B', 6, '2026-2027') RETURNING id"), {"o": org, "t": teacher}).scalar()
        conn.execute(text("INSERT INTO class_students VALUES (:c, :s)"), [{"c": klass, "s": s} for s in students])
        conn.execute(
            text("INSERT INTO questions (node_id, content, answer, difficulty) VALUES (:n, :c, :a, :d)"),
            [{"n": int(s), "c": json.dumps({"text": f"q{s}-{d}-{i}"}), "a": json.dumps("x"), "d": d}
             for s in skills["id"] for d in range(1, 4) for i in range(2)],
        )
    yield {"engine": engine, "teacher": teacher, "class": klass, "new": students[0], "mid": students[1],
           "skills": skills}


@pytest.fixture(scope="module")
def client(seeded):
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as c:
        yield c


def new_assignment(client, seeded, title):
    r = client.post("/assignments", json={"class_id": seeded["class"], "teacher_id": seeded["teacher"],
                                          "title": title, "num_questions": 10})
    assert r.status_code == 200, r.text
    return r.json()


def answer(client, worksheet_id, knows):
    ws = client.get(f"/worksheets/{worksheet_id}").json()
    scores = {it["position"]: 1.0 if knows(it["node_id"]) else 0.0 for it in ws["items"]}
    r = client.post(f"/worksheets/{worksheet_id}/scores", json={"scores": scores})
    assert r.status_code == 200, r.text
    return r.json()


def test_full_cycle(client, seeded):
    nav = client.app.state.navigator
    topics = client.get("/skills/topics").json()
    missing = {302} | nx.descendants(nav.prerequisites, 302)
    knows = {seeded["new"]: lambda s: True, seeded["mid"]: lambda s: s not in missing}
    forms = {str(seeded["mid"]): {"answers": {t: "partly" for t in topics[:4]}}}

    # placement rounds, every student in the class, until both are placed
    for round_no in range(1, 5):
        a = new_assignment(client, seeded, f"placement {round_no}")
        r = client.post(f"/assignments/{a}/worksheets", json={"placement_forms": forms if round_no == 1 else {}})
        assert r.status_code == 200, r.text
        pending = [w for w in r.json() if w["kind"] == "placement"]
        if not pending:
            break
        for w in pending:
            items = client.get(f"/worksheets/{w['worksheet_id']}").json()["items"]
            assert {it["difficulty"] for it in items} == {2}           # placement asks medium
            answer(client, w["worksheet_id"], knows[w["student_id"]])
    else:
        pytest.fail("placement did not finish")

    mid = client.get(f"/students/{seeded['mid']}/profile").json()
    assert mid["placed"]
    gaps = {s["node_id"] for s in mid["skills"] if "gap" in s["flags"]}
    assert gaps == {302}
    assert {s["node_id"]: s["difficulty"] for s in mid["skills"]}[302] == 1   # failed in placement -> easy

    # practice: the engine puts the gap on the sheet; practising it moves mastery up
    a = new_assignment(client, seeded, "practice 1")
    sheets = {w["student_id"]: w for w in client.post(f"/assignments/{a}/worksheets", json={}).json()}
    assert sheets[seeded["mid"]]["kind"] == "practice"
    items = client.get(f"/worksheets/{sheets[seeded['mid']]['worksheet_id']}").json()["items"]
    assert 302 in {it["node_id"] for it in items}
    before = {s["node_id"]: s["mastery"] for s in mid["skills"]}[302]
    result = answer(client, sheets[seeded["mid"]]["worksheet_id"], lambda s: True)
    assert result["kind"] == "practice" and 302 in result["updated_skills"]
    after = {s["node_id"]: s["mastery"] for s in client.get(f"/students/{seeded['mid']}/profile").json()["skills"]}[302]
    assert after > before

    # teacher: one student only, only the selected skill
    a = new_assignment(client, seeded, "targeted")
    r = client.post(f"/assignments/{a}/worksheets", json={
        "student_ids": [seeded["new"]],
        "settings": {"target_node_ids": [1911], "include_weak_prereqs": False, "num_questions": 4}})
    (w,) = r.json()
    items = client.get(f"/worksheets/{w['worksheet_id']}").json()["items"]
    assert {it["node_id"] for it in items} == {1911} and len(items) == 4

    # read-only moves
    assert client.get(f"/students/{seeded['new']}/next-skills").status_code == 200
    report = client.get(f"/students/{seeded['mid']}/gaps/405").json()
    assert report["skill_id"] == 405

    # incomplete scores are refused without saving; scoring twice is refused
    path = f"/worksheets/{w['worksheet_id']}/scores"
    assert client.post(path, json={"scores": {"1": 1}}).status_code == 422
    assert client.post(path, json={"scores": {str(p): 1 for p in range(1, 5)}}).status_code == 200
    assert client.post(path, json={"scores": {str(p): 1 for p in range(1, 5)}}).status_code == 409
