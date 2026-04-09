import os
import json
import re
import requests

BASE = os.environ.get("ENV_BASE_URL", "http://localhost:8000")
TASKS = ["task1", "task2", "task3", "task4", "task5"]


def _extract_episode_targets(reset_obs: dict) -> tuple[str | None, str | None]:
    task_description = reset_obs.get("task_description", "")
    user_match = re.search(r"user ID\s+(\d+)", task_description)
    order_match = re.search(r"order\s+(ORD-[A-Z]{2}\d{4})", task_description)
    target_user_id = user_match.group(1) if user_match else None
    target_order_id = order_match.group(1) if order_match else None
    return target_user_id, target_order_id

def run_heuristic_episode(task_id: str) -> float:
    """
    Rule-based agent. Guaranteed nonzero scores.
    Knows the exact correct sequence for each task.
    """
    # Use a seed for reproducibility in the baseline
    reset_resp = requests.post(f"{BASE}/reset_task", params={"task_id": task_id, "seed": 42})
    if reset_resp.status_code != 200:
        print(f"  [RESET FAILED] Status: {reset_resp.status_code}, Response: {reset_resp.text}")
        return 0.0
    
    # The initial observation after reset is in a different format
    # for some reason, so we need to handle that.
    initial_data = reset_resp.json()
    obs = initial_data if "task_description" in initial_data else initial_data.get("observation", {})
    
    target_user_id, target_order_id = _extract_episode_targets(obs)
    done = False
    token = None
    step = 0
    next_cursor = None
    task4_state: dict = {}

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
                if not target_user_id:
                    raise ValueError("Missing task1 target user id in reset observation")
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
                if not target_order_id:
                    raise ValueError("Missing task2 target order id in reset observation")
                action = {
                    "method": "GET",
                    "endpoint": f"/api/orders/{target_order_id}",
                    "headers": {"Authorization": f"Bearer {token}"},
                    "body": None
                }
            else:
                if not target_order_id:
                    raise ValueError("Missing task2 target order id in reset observation")
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
            elif not task4_state.get("wh_id"):
                action = {
                    "method": "POST",
                    "endpoint": "/api/webhooks/register",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    "body": {"callback_url": "https://agent.example.com/webhook"}
                }
            elif not task4_state.get("event_triggered"):
                wh_id = task4_state.get("wh_id", "")
                action = {
                    "method": "POST",
                    "endpoint": "/api/events/trigger",
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    "body": {"event_type": "order.completed", "webhook_id": wh_id}
                }
            elif not task4_state.get("delivery"):
                wh_id = task4_state.get("wh_id", "")
                action = {
                    "method": "GET",
                    "endpoint": f"/api/webhooks/{wh_id}/deliveries",
                    "headers": {"Authorization": f"Bearer {token}"},
                    "body": None
                }
            elif not task4_state.get("verified"):
                d = task4_state.get("delivery")
                if not d:
                    action = {"method": "WAIT", "endpoint": "", "headers": {}, "body": None}
                else:
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
            elif not task4_state.get("acknowledged"):
                wh_id = task4_state.get("wh_id", "")
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

        elif task_id == "task5":
            resp_data = obs.get("response_data", {})
            # Task5 state machine:
            # - start with discovery probe
            # - exchange pkce_verifier for access token
            # - call admin export with Bearer token
            # Check access_token first so we don't regress to probe after OAuth.
            if resp_data.get("access_token"):
                dark_token = resp_data.get("access_token", "")
                action = {
                    "method": "GET",
                    "endpoint": "/api/admin/export",
                    "headers": {"Authorization": f"Bearer {dark_token}"},
                    "body": None,
                }
            elif resp_data.get("pkce_verifier"):
                pkce_verifier = resp_data.get("pkce_verifier", "")
                action = {
                    "method": "POST",
                    "endpoint": "/api/dark/oauth/token",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"pkce_verifier": pkce_verifier},
                }
            else:
                action = {"method": "GET", "endpoint": "/api/dark/probe", "headers": {}, "body": None}

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

        if task_id == "task4" and isinstance(resp_data, dict):
            if "webhook_id" in resp_data:
                task4_state["wh_id"] = resp_data["webhook_id"]
            if obs.get("status_code") == 200 and "events/trigger" in action.get("endpoint", ""):
                task4_state["event_triggered"] = True
            deliveries = resp_data.get("deliveries", [])
            if deliveries and not task4_state.get("delivery"):
                task4_state["delivery"] = deliveries[0]
            if resp_data.get("verified") is True:
                task4_state["verified"] = True
            if resp_data.get("acknowledged") is True:
                task4_state["acknowledged"] = True

        if task_id == "task5" and isinstance(resp_data, dict):
            hints = resp_data.get("hints", [])
            if hints and "pkce_verifier" not in resp_data:
                m = re.search(r"pkce_([a-f0-9]{10})", json.dumps(resp_data))
                if m:
                    obs.setdefault("response_data", {})["pkce_verifier"] = f"pkce_{m.group(1)}"

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