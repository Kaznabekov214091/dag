from collections import Counter
from dataclasses import dataclass

from questions.picker import pick_for_blueprint

from .blueprint import blueprint


@dataclass(frozen=True)
class WorksheetItem:
    position: int
    question_id: int
    node_id: int
    difficulty: int


def build_items(conn, navigator, profile, plan):
    """Plan -> blueprint (node, difficulty per question) -> questions picked from the pool.

    Returns (items, short): `short` lists skills that got fewer questions than planned (pool too small).
    """
    slots = blueprint(navigator, profile, plan)
    picked = pick_for_blueprint(conn, profile.student_id, slots)
    items = [WorksheetItem(i + 1, q, slot.node_id, slot.difficulty) for i, (slot, q) in enumerate(picked)]

    got = Counter(item.node_id for item in items)
    short = [node for node in dict.fromkeys(s.node_id for s in slots) if got[node] < plan.skill_counts[node]]
    return items, short
