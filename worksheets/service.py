"""Teacher decides WHEN (an assignment, for some or all students); the engine decides WHAT."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from mastery.apply import apply_practice
from mastery.repository import fetch_profile, save_states
from placement.form import PlacementForm, placement_window
from placement.rounds import beginner_states, finish, placement_state

from . import repository as repo
from .builder import build_items
from .selector import plan_worksheet
from .settings import WorksheetSettings


@dataclass
class GeneratedWorksheet:
    student_id: int
    worksheet_id: int
    kind: str
    num_questions: int
    short_skills: list = field(default_factory=list)


@dataclass
class Evaluation:
    worksheet_id: int
    student_id: int
    kind: str                       # "placement" | "practice"
    placement_finished: bool = False
    gaps: list = field(default_factory=list)
    updated_skills: list = field(default_factory=list)


class WorksheetService:
    def __init__(self, engine, navigator):
        self.engine = engine
        self.navigator = navigator

    def generate(self, assignment_id, student_ids=None, settings=None, forms=None, now=None):
        """One worksheet per student. `student_ids=None` -> the whole class.

        `forms`: {student_id: PlacementForm} questionnaire for students starting placement
        (missing or nothing known -> beginner: no test, starts at the roots).
        """
        now = now or datetime.now(timezone.utc)
        forms = forms or {}
        results = []
        with self.engine.begin() as conn:
            assignment = repo.fetch_assignment(conn, assignment_id)
            if student_ids is None:
                student_ids = repo.class_student_ids(conn, assignment["class_id"])
            settings = settings or WorksheetSettings(num_questions=assignment["num_questions"])

            for student_id in student_ids:
                profile = fetch_profile(conn, student_id)
                rounds = [] if profile.placed else repo.graded_rounds(conn, student_id)
                if not profile.placed and not rounds \
                        and placement_window(self.navigator, forms.get(student_id) or PlacementForm()).beginner:
                    # beginner: no placement test, start at the roots; this sheet is already practice
                    updates = beginner_states(self.navigator)
                    save_states(conn, student_id, updates)
                    profile = profile.with_states(updates)
                plan = plan_worksheet(self.navigator, profile, settings, rounds, forms.get(student_id), now)
                items, short = build_items(conn, self.navigator, profile, plan)
                worksheet_id = repo.create_worksheet(conn, assignment_id, student_id, items)
                results.append(GeneratedWorksheet(student_id, worksheet_id, plan.kind, len(items), short))
        return results

    def evaluate(self, worksheet_id, now=None):
        """Scores are in worksheet_items -> update mastery (placement round, or levels + rate in practice)."""
        now = now or datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            ws = repo.fetch_worksheet(conn, worksheet_id)
            if ws["status"] == "evaluated":
                raise ValueError(f"worksheet {worksheet_id} is already evaluated")
            if any(i["score"] is None for i in ws["items"]):
                raise ValueError(f"worksheet {worksheet_id} has unscored items")

            student_id = ws["student_id"]
            profile = fetch_profile(conn, student_id)
            repo.mark_evaluated(conn, worksheet_id)

            if not profile.placed:
                state = placement_state(self.navigator, profile, repo.graded_rounds(conn, student_id))
                updates = finish(self.navigator, profile, state, now) if state.finished else {}
                save_states(conn, student_id, updates)
                return Evaluation(worksheet_id, student_id, "placement", state.finished,
                                  list(state.walk.gaps), sorted(updates))

            items = [(i["node_id"], i["score"]) for i in ws["items"]]
            history = repo.answer_history(conn, student_id, {node for node, _ in items})
            updates = apply_practice(profile, items, history, now)
            save_states(conn, student_id, updates)
            return Evaluation(worksheet_id, student_id, "practice", updated_skills=sorted(updates))
