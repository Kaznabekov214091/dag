from dataclasses import dataclass

from mastery.rate import level_mix
from questions.picker import pick_questions
from questions.repository import seen_question_ids


@dataclass(frozen=True)
class WorksheetItem:
    position: int
    question_id: int
    node_id: int
    difficulty: int


def build_items(conn, navigator, profile, plan):
    """Turn a plan into numbered questions, prerequisites first.

    Each node's questions are split over difficulties by its level (`level_mix`), unless the plan fixes one.

    Returns (items, short): `short` lists skills that got fewer questions than planned (pool too small).
    """
    seen = seen_question_ids(conn, profile.student_id)
    picked, items, short = set(), [], []

    for skill in navigator.order(plan.skill_counts):
        wanted = plan.skill_counts[skill]
        mix = {plan.difficulty: wanted} if plan.difficulty else level_mix(profile.level(skill), wanted)
        got = 0
        for difficulty, count in mix.items():
            ids = pick_questions(conn, skill, count, difficulty, seen, picked)
            picked.update(ids)
            got += len(ids)
            items += [WorksheetItem(len(items) + i + 1, q, skill, difficulty) for i, q in enumerate(ids)]
        if got < wanted:
            short.append(skill)
    return items, short
