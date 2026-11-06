"""Bring the DB skill graph in line with the spreadsheet without dropping anything students depend on."""
from dataclasses import dataclass, field

from sqlalchemy import inspect, text


@dataclass
class SyncPlan:
    added: list = field(default_factory=list)
    changed: list = field(default_factory=list)
    removed: list = field(default_factory=list)          # unused: deleted
    kept_removed: list = field(default_factory=list)     # gone from the sheet but used by questions/mastery: kept
    edges_added: int = 0
    edges_removed: int = 0

    @property
    def has_changes(self):
        return bool(self.added or self.changed or self.removed or self.edges_added or self.edges_removed)


def used_skill_ids(conn):
    """Skills referenced by questions or student mastery (tables may not exist yet)."""
    tables = set(inspect(conn).get_table_names())
    used = set()
    for table in ("questions", "student_mastery"):
        if table in tables:
            used |= {r[0] for r in conn.execute(text(f"SELECT DISTINCT node_id FROM {table}"))}
    return used


def plan_sync(conn, skills_df, prereq_df):
    current = {
        r["id"]: (r["topic"], r["sub_topic"], r["skill"])
        for r in conn.execute(text("SELECT id, topic, sub_topic, skill FROM skills")).mappings()
    }
    wanted = {int(r.id): (r.topic, r.sub_topic, r.skill) for r in skills_df.itertuples(index=False)}

    current_edges = {tuple(r) for r in conn.execute(text("SELECT skill_id, prerequisite_id, type FROM skill_prerequisites"))}
    wanted_edges = {(int(r.skill_id), int(r.prerequisite_id), r.type) for r in prereq_df.itertuples(index=False)}

    gone = sorted(set(current) - set(wanted))
    used = used_skill_ids(conn) if gone else set()
    return SyncPlan(
        added=sorted(set(wanted) - set(current)),
        changed=sorted(s for s in set(wanted) & set(current) if wanted[s] != current[s]),
        removed=[s for s in gone if s not in used],
        kept_removed=[s for s in gone if s in used],
        edges_added=len(wanted_edges - current_edges),
        edges_removed=len(current_edges - wanted_edges),
    )


def apply_sync(conn, plan, skills_df, prereq_df):
    """Run inside one transaction: upsert skills, replace edges, delete unused removed skills."""
    rows = [
        {"id": int(r.id), "topic": r.topic, "sub_topic": r.sub_topic, "skill": r.skill}
        for r in skills_df.itertuples(index=False) if int(r.id) in set(plan.added) | set(plan.changed)
    ]
    if rows:
        conn.execute(text(
            "INSERT INTO skills (id, topic, sub_topic, skill) VALUES (:id, :topic, :sub_topic, :skill) "
            "ON CONFLICT (id) DO UPDATE SET topic = EXCLUDED.topic, sub_topic = EXCLUDED.sub_topic, "
            "skill = EXCLUDED.skill"
        ), rows)

    conn.execute(text("DELETE FROM skill_prerequisites"))
    edges = [
        {"skill_id": int(r.skill_id), "prerequisite_id": int(r.prerequisite_id), "type": r.type}
        for r in prereq_df.itertuples(index=False)
    ]
    if edges:
        conn.execute(text(
            "INSERT INTO skill_prerequisites (skill_id, prerequisite_id, type) "
            "VALUES (:skill_id, :prerequisite_id, :type)"
        ), edges)

    if plan.removed:
        conn.execute(text("DELETE FROM skills WHERE id = ANY(:ids)"), {"ids": plan.removed})
