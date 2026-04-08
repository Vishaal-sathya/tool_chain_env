import os
import json
import requests

BASE = os.environ.get("ENV_BASE_URL", "http://localhost:8000")
TASKS = ["task1", "task2", "task3", "task4"]

def run_heuristic_episode(task_id: str) -> float:
    """
    Rule-based agent. Guaranteed nonzero scores.
    Knows the exact correct sequence for each task.
    """
    reset_resp = requests.post(f"{BASE}/reset_task", params={"task_id": task_id})
    obs = reset_resp.json()
    done = False
    token = None
    step = 0
    next_cursor = None
    
    import re
    task_desc = obs.get("task_description", "")
    target_user_id = "42"
    if task_id == "task1":
        match = re.search(r"user ID (\d+)", task_desc)
        if match: target_user_id = match.group(1)
        
    target_order_id = "ORD-5519"
    if task_id == "task2":
        match = re.search(r"order ([A-Z]{3}-\d{4})", task_desc)
        if match: target_order_id = match.group(1)

    while not done and step < 30:
        step += 1
        action = {}

        if task_id == "task1":
            if token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "agent", "password": "secret123"}
                }
            else:
                action = {
                    "method": "GET",
                    "endpoint": f"/api/crm/users/{target_user_id}",
                    "headers": {"Authorization": f"Bearer {token}"},
                    "body": None
                }

        elif task_id == "task2":
            if token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "agent", "password": "secret123"}
                }
            elif step == 2:
                action = {
                    "method": "GET",
                    "endpoint": f"/api/orders/{target_order_id}",
                    "headers": {"Authorization": f"Bearer {token}"},
                    "body": None
                }
            else:
                action = {
                    "method": "POST",
                    "endpoint": "/api/payments/refund",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": f"idem-{task_id}-{step}",
                        "Content-Type": "application/json"
                    },
                    "body": {"order_id": target_order_id}
                }

        elif task_id == "task3":
            status_code = obs.get("status_code", 0)
            if token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "agent", "password": "secret123"}
                }
            elif status_code == 429:
                action = {
                    "method": "WAIT",
                    "endpoint": "",
                    "headers": {},
                    "body": None
                }
            else:
                action = {
                    "method": "POST",
                    "endpoint": "/api/graphql",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    "body": {
                        "query": "{ systemLogs }",
                        "variables": {"cursor": next_cursor}
                    }
                }

        elif task_id == "task4":
            status_code = obs.get("status_code", 0)
            resp_data = obs.get("response_data", {})
            if token is None:
                action = {
                    "method": "POST",
                    "endpoint": "/api/auth",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"username": "agent", "password": "secret123"}
                }
            elif not hasattr(run_heuristic_episode, '_wh_id') or step == 2:
                if step == 2 and resp_data.get("webhook_id"):
                    run_heuristic_episode._wh_id = resp_data["webhook_id"]
                action = {
                    "method": "POST",
                    "endpoint": "/api/webhooks/register",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    "body": {"callback_url": "https://agent.example.com/webhook"}
                }
            elif step == 3:
                wh_id = resp_data.get("webhook_id", getattr(run_heuristic_episode, '_wh_id', ''))
                run_heuristic_episode._wh_id = wh_id
                action = {
                    "method": "POST",
                    "endpoint": "/api/events/trigger",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    "body": {"event_type": "order.completed", "webhook_id": wh_id}
                }
            elif step == 4:
                wh_id = getattr(run_heuristic_episode, '_wh_id', '')
                action = {
                    "method": "GET",
                    "endpoint": f"/api/webhooks/{wh_id}/deliveries",
                    "headers": {"Authorization": f"Bearer {token}"},
                    "body": None
                }
            elif step == 5:
                deliveries = resp_data.get("deliveries", [])
                if deliveries:
                    d = deliveries[0]
                    run_heuristic_episode._delivery = d
                    action = {
                        "method": "POST",
                        "endpoint": "/api/webhooks/verify",
                        "headers": {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        },
                        "body": {
                            "delivery_id": d.get("delivery_id", ""),
                            "signature": d.get("signature", ""),
                            "payload": d.get("payload", {})
                        }
                    }
                else:
                    action = {"method": "WAIT", "endpoint": "", "headers": {}, "body": None}
            elif step == 6:
                wh_id = getattr(run_heuristic_episode, '_wh_id', '')
                action = {
                    "method": "POST",
                    "endpoint": f"/api/webhooks/{wh_id}/acknowledge",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    "body": {"confirmed": True}
                }
            else:
                action = {"method": "WAIT", "endpoint": "", "headers": {}, "body": None}

        result = requests.post(
            f"{BASE}/step_task",
            params={"task_id": task_id},
            json=action
        ).json()

        obs = result.get("observation", {})
        done = result.get("done", False)

        resp_data = obs.get("response_data", {})
        if isinstance(resp_data, dict) and "token" in resp_data:
            token = resp_data.get("token", token)

        # Track GraphQL pagination cursor
        if task_id == "task3" and isinstance(resp_data, dict):
            page_info = resp_data.get("data", {}).get("systemLogs", {}).get("pageInfo", {})
            next_cursor = page_info.get("nextCursor", next_cursor)

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

    avg = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0
    print(f"\nAverage score: {avg:.4f}")