"""
Inference Script — ToolChain-Env
===================================
MANDATORY ENV VARS:
    API_BASE_URL   The LLM inference endpoint (default: HuggingFace router)
    MODEL_NAME     The model identifier
    HF_TOKEN       Your HuggingFace / API key
    ENV_BASE_URL   The ToolChain-Env server URL (default: localhost:8000)

STDOUT FORMAT (mandatory — do not modify field names or order):
    [START] task=<task_name> env=tool_chain_env model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import os
import json
import time
import requests
from openai import OpenAI

# ── Required env vars ─────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN", "")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")

BENCHMARK    = "tool_chain_env"
MAX_STEPS    = 30   # hard cap; each task has its own budget via step_budget_remaining

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "no-key",
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


def _llm_action(obs: dict) -> dict:
    """Call the LLM and return a parsed action dict."""
    user_content = json.dumps({
        "task_description":    obs.get("task_description", ""),
        "api_docs":            obs.get("api_docs", ""),
        "status_code":         obs.get("status_code", 0),
        "response_data":       obs.get("response_data", {}),
        "step_budget_remaining": obs.get("step_budget_remaining", 0),
        "rate_limit_reset_in": obs.get("rate_limit_reset_in", 0),
        "episode_log":         obs.get("episode_log", [])[-3:],
    }, indent=2)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=512,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
    )
    content = response.choices[0].message.content.strip()
    # Strip markdown fences if model wraps JSON
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


def run_task(task_id: str) -> float:
    """Run one full episode for task_id. Returns final score 0.0–1.0."""

    # ── reset ────────────────────────────────────────────────
    try:
        res = requests.post(
            f"{ENV_BASE_URL}/reset_task",
            params={"task_id": task_id},
            timeout=30,
        )
        obs = res.json()
    except Exception as e:
        print(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}")
        print(f"[END] success=false steps=0 score=0.00 rewards=")
        return 0.0

    # ── mandatory START line ─────────────────────────────────
    print(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}")

    step_count  = 0
    done        = False
    score       = 0.0
    all_rewards: list[float] = []
    last_error  = None

    try:
        while not done and step_count < MAX_STEPS:
            # Get action from LLM (or use WAIT on parse error)
            try:
                action = _llm_action(obs)
                last_error = None
            except Exception as e:
                last_error = str(e)
                action = {"method": "WAIT", "endpoint": "", "headers": {}, "body": None}

            # Submit action to environment
            try:
                result = requests.post(
                    f"{ENV_BASE_URL}/step_task",
                    params={"task_id": task_id},
                    json=action,
                    timeout=30,
                ).json()
            except Exception as e:
                last_error = str(e)
                step_count += 1
                print(
                    f"[STEP] step={step_count} "
                    f"action={json.dumps(action, separators=(',', ':'))} "
                    f"reward=0.00 done=false error={last_error}"
                )
                break

            obs    = result.get("observation", {})
            reward = result.get("reward", 0.0)
            done   = result.get("done", False)
            step_count += 1
            all_rewards.append(reward)

            # ── mandatory STEP line ──────────────────────────────
            action_str  = json.dumps(action, separators=(',', ':'))
            error_field = last_error if last_error else "null"
            done_str    = "true" if done else "false"
            print(
                f"[STEP] step={step_count} "
                f"action={action_str} "
                f"reward={reward:.2f} "
                f"done={done_str} "
                f"error={error_field}"
            )

            if done:
                break
            time.sleep(0.1)

        # ── final grader call ────────────────────────────────────
        try:
            grade_res = requests.post(
                f"{ENV_BASE_URL}/grader",
                params={"task_id": task_id},
                timeout=10,
            )
            score = grade_res.json().get("score", score)
        except Exception:
            pass

    except Exception as e:
        # Catch-all: record the error so [END] is still guaranteed below
        last_error = str(e)

    finally:
        # ── mandatory END line — ALWAYS emitted even on exception ──
        success_str  = "true" if score >= 1.0 else "false"
        rewards_str  = ",".join(f"{r:.2f}" for r in all_rewards)
        print(
            f"[END] success={success_str} "
            f"steps={step_count} "
            f"score={score:.2f} "
            f"rewards={rewards_str}"
        )

    return score


if __name__ == "__main__":
    tasks  = ["task1", "task2", "task3", "task4"]
    scores = {}
    for task in tasks:
        scores[task] = run_task(task)

    avg = sum(scores.values()) / len(scores) if scores else 0.0
    print(f"\nAll scores: {scores}")
    print(f"Average:    {avg:.4f}")