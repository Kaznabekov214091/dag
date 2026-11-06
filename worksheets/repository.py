from sqlalchemy import text


def fetch_assignment(conn, assignment_id):
    row = conn.execute(
        text("SELECT id, class_id, teacher_id, title, num_questions, due_at FROM assignments WHERE id = :id"),
        {"id": assignment_id},
    ).mappings().first()
    if row is None:
        raise LookupError(f"assignment {assignment_id} not found")
    return dict(row)


def create_assignment(conn, class_id, teacher_id, title, num_questions, due_at=None):
    return conn.execute(
        text(
            "INSERT INTO assignments (class_id, teacher_id, title, num_questions, due_at) "
            "VALUES (:class_id, :teacher_id, :title, :num_questions, :due_at) RETURNING id"
        ),
        {"class_id": class_id, "teacher_id": teacher_id, "title": title,
         "num_questions": num_questions, "due_at": due_at},
    ).scalar_one()


def class_student_ids(conn, class_id):
    sql = text("SELECT student_id FROM class_students WHERE class_id = :class_id ORDER BY student_id")
    return [row[0] for row in conn.execute(sql, {"class_id": class_id})]


def create_worksheet(conn, assignment_id, student_id, items):
    worksheet_id = conn.execute(
        text("INSERT INTO worksheets (assignment_id, student_id) VALUES (:a, :s) RETURNING id"),
        {"a": assignment_id, "s": student_id},
    ).scalar_one()
    if items:
        conn.execute(
            text("INSERT INTO worksheet_items (worksheet_id, position, question_id) VALUES (:w, :p, :q)"),
            [{"w": worksheet_id, "p": it.position, "q": it.question_id} for it in items],
        )
    return worksheet_id


def fetch_worksheet(conn, worksheet_id):
    """Worksheet header plus its items with each question's skill node."""
    ws = conn.execute(
        text("SELECT id, assignment_id, student_id, status FROM worksheets WHERE id = :id"),
        {"id": worksheet_id},
    ).mappings().first()
    if ws is None:
        raise LookupError(f"worksheet {worksheet_id} not found")
    items = conn.execute(
        text(
            "SELECT wi.position, wi.question_id, q.node_id, q.difficulty, wi.score, wi.feedback "
            "FROM worksheet_items wi JOIN questions q ON q.id = wi.question_id "
            "WHERE wi.worksheet_id = :id ORDER BY wi.position"
        ),
        {"id": worksheet_id},
    ).mappings().all()
    return {**ws, "items": [dict(i) for i in items]}


def save_scores(conn, worksheet_id, scores):
    """`scores`: {position: score 0..1}; marks the worksheet submitted."""
    conn.execute(
        text("UPDATE worksheet_items SET score = :score WHERE worksheet_id = :w AND position = :p"),
        [{"w": worksheet_id, "p": p, "score": s} for p, s in scores.items()],
    )
    conn.execute(
        text("UPDATE worksheets SET status = 'submitted', submitted_at = COALESCE(submitted_at, now()) "
             "WHERE id = :id AND status = 'generated'"),
        {"id": worksheet_id},
    )


def mark_evaluated(conn, worksheet_id):
    conn.execute(text("UPDATE worksheets SET status = 'evaluated' WHERE id = :id"), {"id": worksheet_id})


def graded_rounds(conn, student_id):
    """Every evaluated worksheet of a student, oldest first, as [(node_id, score), ...]."""
    rows = conn.execute(
        text(
            "SELECT w.id, q.node_id, wi.score FROM worksheets w "
            "JOIN worksheet_items wi ON wi.worksheet_id = w.id "
            "JOIN questions q ON q.id = wi.question_id "
            "WHERE w.student_id = :s AND w.status = 'evaluated' AND wi.score IS NOT NULL "
            "ORDER BY w.created_at, w.id, wi.position"
        ),
        {"s": student_id},
    ).all()
    rounds = {}
    for worksheet_id, node_id, score in rows:
        rounds.setdefault(worksheet_id, []).append((node_id, score))
    return list(rounds.values())


def answer_history(conn, student_id, node_ids):
    """{node_id: [(question difficulty, score), ...]} every graded answer on these nodes, oldest first."""
    if not node_ids:
        return {}
    rows = conn.execute(
        text(
            "SELECT q.node_id, q.difficulty, wi.score FROM worksheets w "
            "JOIN worksheet_items wi ON wi.worksheet_id = w.id "
            "JOIN questions q ON q.id = wi.question_id "
            "WHERE w.student_id = :s AND w.status = 'evaluated' AND wi.score IS NOT NULL "
            "AND q.node_id = ANY(:nodes) "
            "ORDER BY w.created_at, w.id, wi.position"
        ),
        {"s": student_id, "nodes": list(node_ids)},
    ).all()
    history = {}
    for node_id, difficulty, score in rows:
        history.setdefault(node_id, []).append((difficulty, score))
    return history
