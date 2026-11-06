from fastapi import APIRouter, Depends, Request

from skill_dag.pipeline import load_dags
from skill_dag.navigator import SkillNavigator

from .. import deps
from ..schemas import Skill

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[Skill])
def list_skills(nav=Depends(deps.navigator)):
    return [
        Skill(id=n, topic=d["topic"], sub_topic=d["sub_topic"], skill=d["skill"])
        for n in nav.order(nav.prerequisites) for d in [nav.node(n)]
    ]


@router.get("/skills/topics", response_model=list[str])
def list_topics(nav=Depends(deps.navigator)):
    """Topics in curriculum order: the choices of the placement form."""
    return nav.topics()


@router.post("/admin/reload-graph")
def reload_graph(request: Request):
    """Reload the skill graph after scripts/import_skills.py."""
    request.app.state.navigator = SkillNavigator(load_dags())
    return {"skills": request.app.state.navigator.prerequisites.number_of_nodes()}
