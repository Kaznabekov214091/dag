from functools import lru_cache

from sqlalchemy import create_engine

from config import settings as cfg


@lru_cache
def get_engine(url=cfg.DB_URL):
    """One shared engine (and connection pool) per URL for the whole project."""
    return create_engine(url)
