import os
import json
import requests

BASE = os.environ.get("ENV_BASE_URL", "http://localhost:8000")
TASKS = ["task1", "task2", "task3"]

def run_heuristic_episode(task_id: str) -> float:
    """
    Rule-based agent. Guaranteed nonzero scores.
    Knows the exact correct sequence for each task.
    """
    obs_resp = requests.post(f"{BASE}/reset_task", params={"task_id": task_id})
    obs = obs_resp.json().get("observation", {})
    done = False
    token = None
    step = 0

    while not done and step < 10:
        step += 1
        action = {}

        if task_id == "task1":
            if token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "root", "password": "admin"}
                }
            else:
                action = {
                    "method": "GET",
                    "endpoint": "/api/crm/users/42",
                    "headers": {"Authorization": token},
                    "body": {}
                }

        elif task_id == "task2":
            history = obs.get("history", [])
            got_order = any("orders" in h for h in history)
            got_auth = any("api/auth" in h and "200" in h for h in history)
            if not got_auth or token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "root", "password": "admin"}
                }
            elif not got_order:
                action = {
                    "method": "GET",
                    "endpoint": "/api/orders/ORD-5519",
                    "headers": {"Authorization": token},
                    "body": {}
                }
            else:
                action = {
                    "method": "POST",
                    "endpoint": "/api/payments/refund",
                    "headers": {
                        "Authorization": token,
                        "X-Idempotency-Key": "heuristic-key-001",
                        "Content-Type": "application/json"
                    },
                    "body": {"order_id": "ORD-5519"}
                }

        elif task_id == "task3":
            history = obs.get("history", [])
            got_auth = any("api/auth" in h and "200" in h for h in history)
            last_cursor = obs.get("response_data", {}).get("next_cursor", 0) or 0
            if not got_auth or token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "root", "password": "admin"}
                }
            else:
                status = obs.get("status_code", 200)
                if status == 429:
                    action = {
                        "method": "GET",
                        "endpoint": f"/api/logs?cursor={last_cursor}",
                        "headers": {"Authorization": token},
                        "body": {}
                    }
                else:
                    action = {
                        "method": "GET",
                        "endpoint": f"/api/logs?cursor={last_cursor}",
                        "headers": {"Authorization": token},
                        "body": {}
                    }

        result = requests.post(
            f"{BASE}/step_task",
            json={"action": action}
        ).json()

        obs = result.get("observation", {})
        done = result.get("done", False)

        resp_data = obs.get("response_data", {})
        if "token" in str(resp_data):
            token = resp_data.get("token", token)

    score_resp = requests.post(f"{BASE}/grader", params={"task_id": task_id})
    score = score_resp.json().get("score", 0.0)
    return score


if __name__ == "__main__":
    print("Running ToolChain-Env baseline...\n")
    all_scores = {}
    for task in TASKS:
        try:
            score = run_heuristic_episode(task)
            all_scores[task] = score
            print(f"SCORE:{task}:{score:.4f}")
        except Exception as e:
            print(f"SCORE:{task}:0.0000")
            print(f"  ERROR: {e}")

    avg = sum(all_scores.values()) / len(all_scores)
    print(f"\nAverage score: {avg:.4f}")