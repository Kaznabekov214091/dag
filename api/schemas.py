"""Request/response shapes: the contract with the frontend (also shown at /docs)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Skill(BaseModel):
    id: int
    topic: str
    sub_topic: str | None
    skill: str


class SkillMastery(BaseModel):
    node_id: int
    mastery: float
    difficulty: int          # current level: 1 easy, 2 medium, 3 hard
    status: str
    mastered_at: datetime | None
    next_review_at: datetime | None
    review_level: int
    flags: list[str]


class Profile(BaseModel):
    student_id: int
    placed: bool
    skills: list[SkillMastery]


class GapReport(BaseModel):
    skill_id: int
    gaps: list[int]          # deepest failing prerequisites: fix first
    to_assess: list[int]     # prerequisites with no data yet
    weak_path: list[int]     # every failing skill found on the way


class PlacementFormIn(BaseModel):
    """Questionnaire: {topic: how well the student knows it}. Missing topics = dont_know.
    Nothing known -> beginner (no placement test, starts at the roots)."""
    answers: dict[str, Literal["dont_know", "partly", "well"]] = {}


class AssignmentIn(BaseModel):
    class_id: int
    teacher_id: int
    title: str
    due_at: datetime | None = None


class GenerateIn(BaseModel):
    student_ids: list[int] | None = None                  # None -> whole class
    placement_forms: dict[int, PlacementFormIn] = {}      # per student starting placement


class GeneratedWorksheetOut(BaseModel):
    student_id: int
    worksheet_id: int
    kind: str
    num_questions: int
    short_skills: list[int]


class WorksheetItemOut(BaseModel):
    position: int
    question_id: int
    node_id: int
    difficulty: int
    score: float | None
    feedback: str | None


class WorksheetOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    status: str
    items: list[WorksheetItemOut]


class ScoresIn(BaseModel):
    scores: dict[int, float]    # {position: score 0..1}


class EvaluationOut(BaseModel):
    worksheet_id: int
    student_id: int
    kind: str
    placement_finished: bool
    gaps: list[int]
    updated_skills: list[int]
