from fastapi import APIRouter, Depends, HTTPException

from mastery.repository import fetch_profile

from .. import deps
from ..schemas import GapReport, Profile, SkillMastery

router = APIRouter(prefix="/students/{student_id}", tags=["students"])


def load_profile(engine, student_id):
    with engine.connect() as conn:
        return fetch_profile(conn, student_id)


@router.get("/profile", response_model=Profile)
def get_profile(student_id: int, engine=Depends(deps.engine), nav=Depends(deps.navigator)):
    profile = load_profile(engine, student_id)
    return Profile(
        student_id=student_id,
        placed=profile.placed,
        skills=[
            SkillMastery(node_id=s, mastery=st.mastery, difficulty=st.difficulty, status=profile.status(s), mastered_at=st.mastered_at,
                         next_review_at=st.next_review_at, review_level=st.review_level, flags=sorted(st.flags))
            for s in nav.order(profile.skills) for st in [profile.skills[s]]
        ],
    )


@router.get("/next-skills", response_model=list[int])
def next_skills(student_id: int, engine=Depends(deps.engine), nav=Depends(deps.navigator)):
    return nav.next_skills(load_profile(engine, student_id))


@router.get("/path/{target_id}", response_model=list[int])
def path_to(student_id: int, target_id: int, engine=Depends(deps.engine), nav=Depends(deps.navigator)):
    if target_id not in nav.prerequisites:
        raise HTTPException(404, f"skill {target_id} not found")
    return nav.path_to(load_profile(engine, student_id), target_id)


@router.get("/gaps/{skill_id}", response_model=GapReport)
def gaps(student_id: int, skill_id: int, engine=Depends(deps.engine), nav=Depends(deps.navigator)):
    """Why is the student failing `skill_id`? Backward walk over what the profile already knows."""
    if skill_id not in nav.prerequisites:
        raise HTTPException(404, f"skill {skill_id} not found")
    walk = nav.gap_walk(load_profile(engine, student_id), [skill_id], {skill_id: False})
    return GapReport(skill_id=skill_id, gaps=list(walk.gaps), to_assess=list(walk.pending),
                     weak_path=nav.order(walk.failed))

