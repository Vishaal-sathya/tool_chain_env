"""Minimal TRL/GRPO training scaffold for ToolChain-Env.

This script is intentionally lightweight for hackathon demonstration.
It verifies environment wiring and shows where GRPOTrainer hooks in.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def run_probe_episode(base_url: str, task_id: str = "task1") -> float:
    reset = requests.post(f"{base_url}/reset_task", params={"task_id": task_id}, timeout=20).json()
    token = None

    # Very small scripted trajectory just to produce a reward signal.
    for _ in range(3):
        if token is None:
            action = {
                "method": "POST",
                "endpoint": "/api/auth",
                "headers": {"Content-Type": "application/json"},
                "body": {"username": "agent", "password": "secret123"},
            }
        else:
            # Use task description to find user id dynamically.
            desc = reset.get("task_description", "")
            user_id = "42"
            import re

            m = re.search(r"user ID\s+(\d+)", desc)
            if m:
                user_id = m.group(1)
            action = {
                "method": "GET",
                "endpoint": f"/api/crm/users/{user_id}",
                "headers": {"Authorization": f"Bearer {token}"},
                "body": None,
            }

        step = requests.post(
            f"{base_url}/step_task",
            params={"task_id": task_id},
            json=action,
            timeout=20,
        ).json()
        response_data = step.get("observation", {}).get("response_data", {})
        if isinstance(response_data, dict) and "token" in response_data:
            token = response_data["token"]
        if step.get("done"):
            break

    grade = requests.post(f"{base_url}/grader", params={"task_id": task_id}, timeout=20).json()
    return float(grade.get("score", 0.0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-base-url", default="http://localhost:8000")
    parser.add_argument("--task-id", default="task1")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--out", default="docs/training_probe.json")
    args = parser.parse_args()

    history = []
    for i in range(args.steps):
        score = run_probe_episode(args.env_base_url, args.task_id)
        history.append({"step": i + 1, "score": score})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"task_id": args.task_id, "history": history}, indent=2), encoding="utf-8")
    print(f"Wrote training probe to {out_path}")


if __name__ == "__main__":
    main()
