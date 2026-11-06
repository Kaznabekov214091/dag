from sqlalchemy import text

from .profile import SkillState, StudentProfile


def fetch_profile(conn, student_id):
    """A student's mastery rows; a student with no rows gets an empty (new) profile."""
    sql = text(
        "SELECT node_id, mastery, difficulty, mastered_at, next_review_at, review_level, flags "
        "FROM student_mastery WHERE student_id = :student_id"
    )
    rows = conn.execute(sql, {"student_id": student_id}).mappings().all()
    return StudentProfile(student_id, {
        r["node_id"]: SkillState(
            mastery=r["mastery"],
            difficulty=r["difficulty"],
            mastered_at=r["mastered_at"],
            next_review_at=r["next_review_at"],
            review_level=r["review_level"],
            flags=frozenset(r["flags"] or ()),
        )
        for r in rows
    })


def save_states(conn, student_id, updates):
    """Insert or update student_mastery rows from {node_id: SkillState}; runs inside the caller's transaction."""
    if not updates:
        return
    sql = text(
        "INSERT INTO student_mastery "
        "(student_id, node_id, mastery, difficulty, mastered_at, next_review_at, review_level, flags) "
        "VALUES (:student_id, :node_id, :mastery, :difficulty, :mastered_at, :next_review_at, :review_level, :flags) "
        "ON CONFLICT (student_id, node_id) DO UPDATE SET "
        "mastery = EXCLUDED.mastery, difficulty = EXCLUDED.difficulty, mastered_at = EXCLUDED.mastered_at, "
        "next_review_at = EXCLUDED.next_review_at, review_level = EXCLUDED.review_level, "
        "flags = EXCLUDED.flags"
    )
    conn.execute(sql, [
        {
            "student_id": student_id,
            "node_id": node_id,
            "mastery": min(max(st.mastery, 0.0), 1.0),
            "difficulty": st.difficulty,
            "mastered_at": st.mastered_at,
            "next_review_at": st.next_review_at,
            "review_level": st.review_level,
            "flags": sorted(st.flags),
        }
        for node_id, st in updates.items()
    ])
