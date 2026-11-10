from itertools import groupby

from .repository import fetch_question_ids, seen_question_ids


def pick_for_blueprint(conn, student_id, slots):
    """One question per blueprint slot (node, difficulty).

    Returns [(slot, question_id)] in slot order. Slots the pool can't fill are left out.
    """
    seen = seen_question_ids(conn, student_id)
    picked, result = set(), []
    for slot, group in groupby(slots):
        ids = pick_questions(conn, slot.node_id, len(list(group)), slot.difficulty, seen, picked)
        picked.update(ids)
        result += [(slot, q) for q in ids]
    return result


def pick_questions(conn, node_id, count, difficulty, seen, picked):
    """`count` questions for a skill: unseen ones first, then repeats once the pool runs out.

    `picked` (already on this worksheet) is never repeated.
    """
    ids = fetch_question_ids(conn, node_id, difficulty, count, seen | picked)
    if len(ids) < count:
        ids += fetch_question_ids(conn, node_id, difficulty, count - len(ids), picked | set(ids))
    return ids
