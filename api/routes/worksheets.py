from fastapi import APIRouter, Depends, HTTPException

from placement.form import PlacementForm
from worksheets import repository as repo

from .. import deps
from ..schemas import (AssignmentIn, EvaluationOut, GenerateIn, GeneratedWorksheetOut, ScoresIn,
                       WorksheetOut)

router = APIRouter(tags=["assignments & worksheets"])


@router.post("/assignments", response_model=int)
def create_assignment(body: AssignmentIn, engine=Depends(deps.engine)):
    with engine.begin() as conn:
        return repo.create_assignment(conn, body.class_id, body.teacher_id, body.title, body.due_at)


@router.post("/assignments/{assignment_id}/worksheets", response_model=list[GeneratedWorksheetOut])
def generate_worksheets(assignment_id: int, body: GenerateIn, service=Depends(deps.worksheet_service)):
    """One worksheet per chosen student (default: the whole class); the engine decides what is on it."""
    try:
        forms = {sid: PlacementForm(dict(f.answers)) for sid, f in body.placement_forms.items()}
        generated = service.generate(assignment_id, body.student_ids, forms)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return [GeneratedWorksheetOut(**vars(g)) for g in generated]


@router.get("/worksheets/{worksheet_id}", response_model=WorksheetOut)
def get_worksheet(worksheet_id: int, engine=Depends(deps.engine)):
    try:
        with engine.connect() as conn:
            return repo.fetch_worksheet(conn, worksheet_id)
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.post("/worksheets/{worksheet_id}/scores", response_model=EvaluationOut)
def submit_scores(worksheet_id: int, body: ScoresIn, service=Depends(deps.worksheet_service)):
    """Store graded scores (from scan reading or the teacher) and update mastery."""
    if any(not 0 <= v <= 1 for v in body.scores.values()):
        raise HTTPException(422, "scores must be between 0 and 1")
    try:
        with service.engine.begin() as conn:
            ws = repo.fetch_worksheet(conn, worksheet_id)
            if ws["status"] == "evaluated":
                raise ValueError(f"worksheet {worksheet_id} is already evaluated")
            positions = {it["position"] for it in ws["items"]}
            if set(body.scores) != positions:
                raise HTTPException(422, f"send a score for every position: {sorted(positions)}")
            repo.save_scores(conn, worksheet_id, body.scores)
        evaluation = service.evaluate(worksheet_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return EvaluationOut(**vars(evaluation))
