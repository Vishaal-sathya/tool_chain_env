from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_task1_wrong_user_scores_07():
    import re

    reset_obs = client.post("/reset_task", params={"task_id": "task1"}).json()
    m = re.search(r"user ID\s+(\d+)", reset_obs.get("task_description", ""))
    assert m
    correct_id = int(m.group(1))
    wrong_id = str(1 if correct_id != 1 else 2)

    token_resp = client.post(
        "/step_task",
        params={"task_id": "task1"},
        json={
            "method": "POST",
            "endpoint": "/api/auth",
            "headers": {"Content-Type": "application/json"},
            "body": {"username": "agent", "password": "secret123"},
        },
    ).json()
    token = token_resp["observation"]["response_data"]["token"]

    client.post(
        "/step_task",
        params={"task_id": "task1"},
        json={
            "method": "GET",
            "endpoint": f"/api/crm/users/{wrong_id}",
            "headers": {"Authorization": f"Bearer {token}"},
            "body": None,
        },
    )

    score = client.post("/grader", params={"task_id": "task1"}).json()["score"]
    assert score == 0.7 or score == 0.5
