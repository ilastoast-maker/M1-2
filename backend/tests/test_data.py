from datetime import date, timedelta


def test_activity_crud_and_summary(client, profile):
    start = date(2026, 1, 1)
    created_ids = []
    for index in range(100):
        response = client.post(
            "/api/data",
            json={
                "date": (start + timedelta(days=index)).isoformat(),
                "value": 4000 + index * 10,
                "memo": "테스트 기록",
                "record_type": "activity",
                "source": "manual",
                "active_minutes": 30,
                "activity_calories": 150,
                "distance_km": 3.2,
            },
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    summary = client.get("/api/data/summary")
    assert summary.status_code == 200
    assert summary.json()["activity_count"] == 100
    assert summary.json()["activity"]["max_steps"] == 4990

    updated = client.put(f"/api/data/{created_ids[0]}", json={"memo": "수정됨"})
    assert updated.status_code == 200
    assert updated.json()["memo"] == "수정됨"

    deleted = client.delete(f"/api/data/{created_ids[0]}")
    assert deleted.status_code == 204


def test_duplicate_date_requires_overwrite(client, profile):
    payload = {
        "date": "2026-10-16",
        "value": 505,
        "memo": "",
        "record_type": "activity",
        "source": "screenshot",
        "active_minutes": 5,
        "activity_calories": 15,
        "distance_km": 0.37,
    }
    assert client.post("/api/data", json=payload).status_code == 201
    assert client.post("/api/data", json=payload).status_code == 409
    payload["value"] = 600
    overwritten = client.post("/api/data?overwrite=true", json=payload)
    assert overwritten.status_code == 201
    assert overwritten.json()["value"] == 600


def test_zero_step_day_is_valid_but_zero_weight_is_not(client, profile):
    activity = client.post(
        "/api/data",
        json={
            "date": "2026-10-15",
            "value": 0,
            "record_type": "activity",
            "source": "screenshot",
            "active_minutes": 0,
            "activity_calories": 0,
            "distance_km": 0,
        },
    )
    assert activity.status_code == 201

    weight = client.post(
        "/api/data",
        json={
            "date": "2026-10-15",
            "value": 0,
            "record_type": "weight",
            "source": "manual",
        },
    )
    assert weight.status_code == 422


def test_user_isolation(client, profile):
    created = client.post(
        "/api/data",
        json={
            "date": "2026-10-16",
            "value": 505,
            "record_type": "activity",
            "source": "manual",
        },
    ).json()
    client.headers["X-Debug-User"] = "user-b"
    assert client.put(f"/api/data/{created['id']}", json={"value": 999}).status_code == 404
    assert client.delete(f"/api/data/{created['id']}").status_code == 404
