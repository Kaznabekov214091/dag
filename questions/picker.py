from .repository import fetch_question_ids


def pick_questions(conn, node_id, count, difficulty, seen, picked):
    """`count` questions for a skill: unseen ones first, then repeats once the pool runs out.

    `picked` (already on this worksheet) is never repeated.
    """
    ids = fetch_question_ids(conn, node_id, difficulty, count, seen | picked)
    if len(ids) < count:
        ids += fetch_question_ids(conn, node_id, difficulty, count - len(ids), picked | set(ids))
    return ids
