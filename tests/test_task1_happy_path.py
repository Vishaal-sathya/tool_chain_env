import re
from starlette.testclient import TestClient
from app import app

client = TestClient(app)

def test_task1_happy_path():
    """
    Tests the ideal, straight-path scenario for task1:
    1. Reset
    2. Authenticate
    3. Get user profile
    4. Grade
    """
    # 1. Reset and get initial observation
    reset_resp = client.post("/reset_task", params={"task_id": "task1", "seed": 1337})
    assert reset_resp.status_code == 200
    obs = reset_resp.json()
    assert "task_description" in obs
    match = re.search(r"user ID (\d+)", obs["task_description"])
    assert match, "Could not find user ID in task description"
    target_user_id = match.group(1)

    # 2. Authenticate
    auth_action = {
        "method": "POST",
        "endpoint": "/api/auth",
        "headers": {"Content-Type": "application/json"},
        "body": {"username": "agent", "password": "secret123"}
    }
    auth_resp = client.post("/step_task", params={"task_id": "task1"}, json=auth_action)
    assert auth_resp.status_code == 200
    auth_obs = auth_resp.json()["observation"]
    token = auth_obs["response_data"]["token"]

    # 3. Get user's profile
    crm_action = {
        "method": "GET",
        "endpoint": f"/api/crm/users/{target_user_id}",
        "headers": {"Authorization": f"Bearer {token}"},
        "body": None
    }
    crm_resp = client.post("/step_task", params={"task_id": "task1"}, json=crm_action)
    assert crm_resp.status_code == 200
    
    # 4. Grade the episode
    grade_resp = client.post("/grader", params={"task_id": "task1"})
    assert grade_resp.status_code == 200
    grade_data = grade_resp.json()
    assert grade_data["score"] == 1.0
