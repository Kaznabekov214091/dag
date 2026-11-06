import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# DB tests run against TEST_DB_URL; it must be set before config is imported anywhere
if os.getenv("TEST_DB_URL"):
    os.environ["DB_URL"] = os.environ["TEST_DB_URL"]

import pandas as pd
import pytest

from importer.excel_reader import read_sheet, to_prerequisite_rows, to_skills_table
from skill_dag.graph.builder import build_dag
from skill_dag.navigator import SkillNavigator

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def navigator_from(skills, prereqs):
    return SkillNavigator({t: build_dag(skills, prereqs, t) for t in ("soft", "hard")})


@pytest.fixture
def small_nav():
    """A: 1 -> 2 -> 3(Gate)   B: 11 -> 12 -> 13(Gate)   C: 21 -> 22

    soft is the chain 1..22; hard is sparser, and 11 has no hard prerequisites (falls back to soft: 3).
    """
    skills = pd.DataFrame([
        (1, "A", None, "a1"), (2, "A", None, "a2"), (3, "A", "Gate", "A mastery"),
        (11, "B", None, "b1"), (12, "B", None, "b2"), (13, "B", "Gate", "B mastery"),
        (21, "C", None, "c1"), (22, "C", None, "c2"),
    ], columns=["id", "topic", "sub_topic", "skill"])
    chain = [1, 2, 3, 11, 12, 13, 21, 22]
    soft = [(b, a, "soft") for a, b in zip(chain, chain[1:])]
    hard = [(2, 1), (3, 1), (3, 2), (12, 11), (13, 11), (13, 12), (21, 13), (22, 21), (22, 12)]
    prereqs = pd.DataFrame(soft + [(s, p, "hard") for s, p in hard], columns=["skill_id", "prerequisite_id", "type"])
    return navigator_from(skills, prereqs)


@pytest.fixture(scope="session")
def algebra_nav():
    raw = read_sheet(ROOT / "algebra.xlsx")
    prereqs, _ = to_prerequisite_rows(raw)
    return navigator_from(to_skills_table(raw), prereqs)
