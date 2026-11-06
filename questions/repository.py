from sqlalchemy import bindparam, text


def fetch_question_ids(conn, node_id, difficulty, limit, exclude_ids=()):
    """Random question ids for a skill node, closest to `difficulty` first."""
    exclude_clause = "AND id NOT IN :exclude_ids" if exclude_ids else ""
    sql = text(
        f"SELECT id FROM questions WHERE node_id = :node_id {exclude_clause} "
        f"ORDER BY ABS(difficulty - :difficulty), RANDOM() LIMIT :limit"
    )
    params = {"node_id": node_id, "difficulty": difficulty, "limit": limit}
    if exclude_ids:
        sql = sql.bindparams(bindparam("exclude_ids", expanding=True))
        params["exclude_ids"] = list(exclude_ids)
    return [row[0] for row in conn.execute(sql, params)]


def seen_question_ids(conn, student_id):
    """Every question already put on one of the student's worksheets."""
    sql = text(
        "SELECT DISTINCT wi.question_id FROM worksheet_items wi "
        "JOIN worksheets w ON w.id = wi.worksheet_id WHERE w.student_id = :student_id"
    )
    return {row[0] for row in conn.execute(sql, {"student_id": student_id})}
