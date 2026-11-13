from fastapi import Request

from db.connection import get_engine
from worksheets.service import WorksheetService


def engine():
    return get_engine()


def navigator(request: Request):
    """The skill graph is loaded once at startup (see api.main) and shared by every request."""
    return request.app.state.navigator


def worksheet_service(request: Request):
    return WorksheetService(get_engine(), request.app.state.navigator)
