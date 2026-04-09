from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def _task2_order_id() -> str:
    import re

    obs = client.post("/reset_task", params={"task_id": "task2"}).json()
    m = re.search(r"order\s+(ORD-[A-Z]{2}\d{4})", obs.get("task_description", ""))
    assert m
    return m.group(1)


def _auth_token(task_id: str) -> str:
    r = client.post(
        "/step_task",
        params={"task_id": task_id},
        json={
            "method": "POST",
            "endpoint": "/api/auth",
            "headers": {"Content-Type": "application/json"},
            "body": {"username": "agent", "password": "secret123"},
        },
    ).json()
    return r["observation"]["response_data"]["token"]


def test_task2_scores_08_without_idempotency():
    order_id = _task2_order_id()
    token = _auth_token("task2")

    client.post(
        "/step_task",
        params={"task_id": "task2"},
        json={
            "method": "GET",
            "endpoint": f"/api/orders/{order_id}",
            "headers": {"Authorization": f"Bearer {token}"},
            "body": None,
        },
    )
    client.post(
        "/step_task",
        params={"task_id": "task2"},
        json={
            "method": "POST",
            "endpoint": "/api/payments/refund",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            "body": {"order_id": order_id},
        },
    )
    score = client.post("/grader", params={"task_id": "task2"}).json()["score"]
    assert score == 0.8


def test_task2_scores_10_with_idempotency():
    order_id = _task2_order_id()
    token = _auth_token("task2")

    client.post(
        "/step_task",
        params={"task_id": "task2"},
        json={
            "method": "GET",
            "endpoint": f"/api/orders/{order_id}",
            "headers": {"Authorization": f"Bearer {token}"},
            "body": None,
        },
    )
    client.post(
        "/step_task",
        params={"task_id": "task2"},
        json={
            "method": "POST",
            "endpoint": "/api/payments/refund",
            "headers": {
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "idem-test-1",
                "Content-Type": "application/json",
            },
            "body": {"order_id": order_id},
        },
    )
    score = client.post("/grader", params={"task_id": "task2"}).json()["score"]
    assert score == 1.0
