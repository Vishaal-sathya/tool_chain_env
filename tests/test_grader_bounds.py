from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_grader_bounds_for_all_tasks():
    for task in ["task1", "task2", "task3", "task4", "task5"]:
        client.post("/reset_task", params={"task_id": task})
        # Take at least one step so grader gate does not force 0.0 by reason.
        client.post(
            "/step_task",
            params={"task_id": task},
            json={
                "method": "POST",
                "endpoint": "/api/auth",
                "headers": {"Content-Type": "application/json"},
                "body": {"username": "agent", "password": "secret123"},
            },
        )
        grade = client.post("/grader", params={"task_id": task}).json()
        score = float(grade.get("score", 0.0))
        assert 0.0 <= score <= 1.0
