import inspect
from typing import Any

from fastapi import FastAPI

from nutrition_service.db import create_engine_from_url, create_schema, create_session_factory
from nutrition_service.service import NutritionService


def _resolve_analysis_not_configured(payload: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("app.state.resolve_analysis must be configured before calling /analyze")


def _default_logged_response(payload: dict[str, Any]) -> dict[str, bool]:
    return {"logged": True}


def create_app(
    *,
    database_url: str | None = None,
    service: NutritionService | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.resolve_analysis = _resolve_analysis_not_configured
    app.state.select_candidate = _default_logged_response
    app.state.correct_candidate = _default_logged_response

    if service is None and database_url:
        engine = create_engine_from_url(database_url)
        create_schema(engine)
        service = NutritionService(create_session_factory(engine))

    if service is not None:
        app.state.resolve_analysis = service.analyze
        app.state.select_candidate = service.select_candidate
        app.state.correct_candidate = service.correct_candidate

    @app.get("/api/nutrition/v1/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/nutrition/v1/analyze")
    async def analyze(payload: dict[str, Any]) -> Any:
        result = app.state.resolve_analysis(payload)
        if inspect.isawaitable(result):
            result = await result
        return result

    @app.post("/api/nutrition/v1/select")
    async def select(payload: dict[str, Any]) -> Any:
        result = app.state.select_candidate(payload)
        if inspect.isawaitable(result):
            result = await result
        return result

    @app.post("/api/nutrition/v1/correct")
    async def correct(payload: dict[str, Any]) -> Any:
        result = app.state.correct_candidate(payload)
        if inspect.isawaitable(result):
            result = await result
        return result

    return app
