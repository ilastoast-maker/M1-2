import pytest

from app.safety import bmi_guidance, calculate_bmi


def test_bmi_boundaries():
    assert bmi_guidance(16.9) is not None
    assert bmi_guidance(17.0) is None
    assert bmi_guidance(29.9) is None
    assert bmi_guidance(30.0) is not None


def test_underweight_goal_requires_confirmation(client):
    response = client.put(
        "/api/profile",
        json={
            "age": 25,
            "sex": "prefer_not_to_say",
            "height_cm": 180,
            "current_weight_kg": 70,
            "target_weight_kg": 50,
            "low_bmi_goal_confirmed": False,
        },
    )
    assert response.status_code == 422
