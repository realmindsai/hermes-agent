"""E2E contract tests for nutrition-service persisted correction flows."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from nutrition_service.api import create_app
from nutrition_service.db import create_schema
from nutrition_service.models import MealLog, SourceFoodUsda


def test_analyze_then_correct_logs_manual_meal_entry(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'nutrition.sqlite3'}"
    engine = create_engine(database_url)
    create_schema(engine)
    with Session(engine) as session:
        session.add(SourceFoodUsda(description="Chicken salad", energy_kcal=205.0, raw_payload={}))
        session.commit()
    client = TestClient(create_app(database_url=database_url))

    analyze = client.post(
        "/api/nutrition/v1/analyze",
        json={
            "session_id": "telegram:dm:1",
            "caption_text": "lunch",
            "image_paths": ["/tmp/lunch.jpg"],
        },
    )

    assert analyze.status_code == 200
    candidate_set_id = analyze.json()["candidate_set_id"]

    correct = client.post(
        "/api/nutrition/v1/correct",
        json={
            "session_id": "telegram:dm:1",
            "candidate_set_id": candidate_set_id,
            "correction_text": "two eggs and toast",
        },
    )

    assert correct.status_code == 200
    assert correct.json() == {"logged": True, "message": "Logged corrected meal."}

    with Session(engine) as session:
        meal_log = session.scalar(select(MealLog))
        assert meal_log is not None
        assert meal_log.title == "two eggs and toast"
        assert meal_log.calories is None
