from config import settings as cfg
from db.connection import get_engine

from .db.repository import fetch_prerequisites, fetch_skills
from .graph.builder import build_dag, check_dag


def load_dags(engine=None):
    """Fetch skills from the DB and return {edge_type: DiGraph}, one validated DAG per type."""
    engine = engine or get_engine()
    skills = fetch_skills(engine)
    skill_prerequisites = fetch_prerequisites(engine)

    dags = {}
    for edge_type in cfg.DAG_EDGE_TYPES:
        G = build_dag(skills, skill_prerequisites, edge_type)
        check_dag(G, edge_type)
        dags[edge_type] = G
    return dags
