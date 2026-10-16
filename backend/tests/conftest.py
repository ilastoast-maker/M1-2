import os

os.environ["APP_ENV"] = "test"
os.environ["AUTH_MODE"] = "dev"
os.environ["USE_IN_MEMORY_DB"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.store import reset_store_cache


@pytest.fixture(autouse=True)
def reset_state():
    get_settings.cache_clear()
    reset_store_cache()
    yield
    reset_store_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), headers={"X-Debug-User": "user-a"})


@pytest.fixture
def profile(client: TestClient) -> dict:
    response = client.put(
        "/api/profile",
        json={
            "age": 30,
            "sex": "prefer_not_to_say",
            "height_cm": 170,
            "current_weight_kg": 70,
            "target_weight_kg": 65,
            "low_bmi_goal_confirmed": False,
        },
    )
    assert response.status_code == 200
    return response.json()
