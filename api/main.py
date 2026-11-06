"""Run from the project root:  uvicorn api.main:app --reload   ->  http://localhost:8000/docs"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings as cfg
from skill_dag.navigator import SkillNavigator
from skill_dag.pipeline import load_dags

from .routes import skills, students, worksheets


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.navigator = SkillNavigator(load_dags())
    yield


app = FastAPI(title="Adaptive math practice", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(skills.router)
app.include_router(students.router)
app.include_router(worksheets.router)
