import os
import json
import time
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
MODEL_NAME   = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN     = os.environ.get("HF_TOKEN", "")

ENV_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:8000")

import requests

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
)

SYSTEM_PROMPT = """You are an API orchestration agent. You will receive an observation from an environment and must respond with a single JSON action.

Your response must be ONLY valid JSON with these exact fields:
{
  "method": "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "WAIT",
  "endpoint": "/api/path",
  "headers": {"key": "value"},
  "body": {"key": "value"} or null
}

Read the task_description and api_docs carefully. Follow the correct sequence of API calls.
Never include any explanation — only the JSON object."""

def get_action_from_llm(obs: dict) -> dict:
    user_content = json.dumps({
        "task_description": obs.get("task_description", ""),
        "api_docs": obs.get("api_docs", ""),
        "status_code": obs.get("status_code", 0),
        "response_data": obs.get("response_data", {}),
        "step_budget_remaining": obs.get("step_budget_remaining", 0),
        "rate_limit_reset_in": obs.get("rate_limit_reset_in", 0),
        "episode_log": obs.get("episode_log", [])[-3:],  # last 3 steps only
    }, indent=2)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
    )
    content = response.choices[0].message.content.strip()
    # Strip markdown fences if model adds them
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())

def run_task(task_id: str) -> float:
    print(f"\n[START] Mission: {task_id}")

    try:
        res = requests.post(
            f"{ENV_BASE_URL}/reset_task",
            params={"task_id": task_id},
            timeout=30
        )
        obs = res.json()
    except Exception as e:
        print(f"[END] Mission {task_id} | Final Score: 0.0")
        return 0.0

    step_count = 0
    max_steps  = obs.get("step_budget_remaining", 10)
    score      = 0.0

    while step_count < max_steps:
        try:
            action = get_action_from_llm(obs)
        except Exception as e:
            print(f"[STEP] {step_count+1}: LLM error — {e}")
            break

        try:
            result = requests.post(
                f"{ENV_BASE_URL}/step_task",
                params={"task_id": task_id},
                json=action,
                timeout=30
            ).json()
        except Exception as e:
            print(f"[STEP] {step_count+1}: Env error — {e}")
            break

        obs    = result.get("observation", {})
        reward = result.get("reward", 0.0)
        done   = result.get("done", False)
        score  = result.get("info", {}).get("score", score)

        # MANDATORY LOG FORMAT — do not change field names or order
        print(
            f"[STEP] {step_count+1}: "
            f"{action.get('method')} {action.get('endpoint')} | "
            f"Status: {obs.get('status_code')} | "
            f"Local_Score: {score}"
        )

        step_count += 1
        if done:
            break
        time.sleep(0.3)

    # Final grader call
    try:
        grade_res = requests.post(
            f"{ENV_BASE_URL}/grader",
            params={"task_id": task_id},
            timeout=10
        )
        score = grade_res.json().get("score", score)
    except Exception:
        pass

    print(f"[END] Mission {task_id} | Final Score: {score}\n")
    return score

if __name__ == "__main__":
    tasks = ["task1", "task2", "task3"]
    scores = {}
    for task in tasks:
        scores[task] = run_task(task)

    avg = sum(scores.values()) / len(scores)
    print(f"\nAll scores: {scores}")
    print(f"Average: {avg:.4f}")