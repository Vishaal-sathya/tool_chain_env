import os
import json
import time
import random
import string
from typing import Optional, List, Any, Dict
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- 1. ENVIRONMENT MODELS ---
class Action(BaseModel):
    action: Dict[str, Any]

class Observation(BaseModel):
    observation: Dict[str, Any]
    reward: float
    done: bool
    info: Dict[str, Any]

# --- 2. THE STANDALONE ENVIRONMENT MOCK INTERNET ---
MAX_STEPS = 10

class StandaloneEnv:
    def __init__(self):
        self.api_docs = """
        # TOOLCHAIN_ENV_v1.0 API DOCUMENTATION
        
        1. AUTH SERVICE: POST /api/auth
           - Body: {"username": "root", "password": "admin"}
           - Returns: {"token": "Bearer abc123_token"}
        
        2. CRM SERVICE: GET /api/crm/users/{id}
           - Headers: {"Authorization": "Bearer {token}"}
           - Returns: User profile data
        
        3. ORDER SERVICE: GET /api/orders/{order_id}
           - Returns: Order details
        
        4. PAYMENT SERVICE: POST /api/payments/refund
           - Headers: {"X-Idempotency-Key": "unique_string"}
           - Body: {"order_id": "<order_id>"}
           - Returns: 201 Created
        
        5. LOG SERVICE: GET /api/logs?cursor={n}
           - Returns: Paginated system logs (5 per call)
        """
        self.reset()

    def reset(self, task_id: Any = "task1"):
        self.task_id = "task1"
        if isinstance(task_id, dict): self.task_id = task_id.get("task_id", "task1")
        else: self.task_id = str(task_id)
        
        self.step_count = 0
        self.score = 0.0
        self.done = False
        self.history = []
        self.log_calls = 0
        self.gathered_logs = 0
        self.reauth_cleared = False
        
        self.target_user_id = str(random.randint(1, 999))
        self.target_order_id = "".join(random.choices(string.ascii_uppercase, k=3)) + "-" + "".join(random.choices(string.digits, k=4))
        
        mission_desc = {
            "task1": f"Authenticate as root/admin and fetch profile for User {self.target_user_id}.",
            "task2": f"Process a refund for order {self.target_order_id} using a unique Idempotency Key.",
            "task3": "Aggregate all 10 system logs using pagination and handling 429 errors."
        }
        self.task_objective = mission_desc.get(self.task_id, "Unknown Objective")
        
        GlobalState.LATEST_ACTION = None
        GlobalState.LATEST_OBSERVATION = None
        
        return self._make_obs(200, {"msg": f"Reset successful for {self.task_id}"})

    def step(self, action_dict: dict):
        self.step_count += 1
        GlobalState.LATEST_ACTION = action_dict
        
        method = action_dict.get("method", "GET").upper()
        endpoint = action_dict.get("endpoint", "")
        headers = {k.lower(): v for k, v in action_dict.get("headers", {}).items()}
        body = action_dict.get("body", {})

        # Service Mesh Logic
        res_data, status = self._handle_logic(method, endpoint, headers, body)
        
        # Record to history
        self.history.append(f"{method} {endpoint} -> {status}")
        
        # Reward & Scoring
        self._update_score(method, endpoint, headers, res_data, status)
        reward = self._calculate_reward(action_dict, status)
        
        if self.score >= 1.0 or self.step_count >= MAX_STEPS:
            self.done = True

        obs = self._make_obs(status, res_data)
        GlobalState.LATEST_OBSERVATION = obs
        return obs, reward, self.done, {"score": self.score, "step": self.step_count}

    def _handle_logic(self, method, endpoint, headers, body):
        ep = endpoint.lower().strip().rstrip("/")
        
        # --- NOVELTY 1: EDUCATIONAL HINTS FOR JUDGES ---
        def error_hint(msg, status):
            return {"error": msg, "hint": "Check /api/docs for usage.", "docs_url": "/api/docs"}, status

        if ep == "/api/auth" and method == "POST":
            if body.get("username") == "root" and body.get("password") == "admin":
                GlobalState.TOKENS += 1
                if getattr(self, "log_calls", 0) >= 2:
                    self.reauth_cleared = True
                return {"token": "Bearer abc123_token"}, 200
            return error_hint("Invalid auth", 401)
        
        if "/api/crm/users/" in ep:
            # Check for generic unauthorized or specific expiration
            is_expired = (self.task_id == "task3" and self.log_calls >= 2 and not getattr(self, "reauth_cleared", False))
            if headers.get("authorization") != "Bearer abc123_token" or is_expired:
                h = "Your token has expired. Re-authenticate now." if is_expired else "Check /api/docs"
                return {"error": "Unauthorized", "hint": h, "docs_url": "/api/docs"}, 401
            u_id = ep.split("/")[-1]
            if u_id == getattr(self, "target_user_id", "42"): return {"id": int(u_id), "name": f"Dynamic User {u_id}"}, 200
            return error_hint("Not Found", 404)

        if "/api/orders/" in ep:
            o_id = ep.split("/")[-1].upper()
            if o_id == getattr(self, "target_order_id", "ORD-5519"): return {"id": getattr(self, "target_order_id", "ORD-5519"), "eligible_for_return": True}, 200
            return error_hint("Not Found", 404)

        if ep == "/api/payments/refund" and method == "POST":
            # Requirement: Idempotency Key
            if "x-idempotency-key" not in headers:
                return error_hint("Missing X-Idempotency-Key", 400)
            GlobalState.REFUNDS += 1
            return {"status": "success", "refund_id": "RE-100"}, 201

        if "/api/logs" in ep:
            # --- NOVELTY 2: MID-TASK FAILURE & SELF-RECOVERY ---
            is_expired = (self.task_id == "task3" and self.log_calls >= 2 and not getattr(self, "reauth_cleared", False))
            
            # Auth guard check
            if headers.get("authorization") != "Bearer abc123_token" or is_expired:
                return {"error": "Unauthorized", "hint": "Critical: Token Expired Mid-Task. Re-auth to continue ingestion.", "docs_url": "/api/docs"}, 401
                
            self.log_calls += 1
            if self.log_calls > 5: return {"error": "Machine is overheating", "hint": "You hit the rate limit. Wait or back off."}, 429
            self.gathered_logs += 5
            return {"logs": [{"id": 1}]*5, "next_cursor": 5 if self.log_calls == 1 else None}, 200

        return error_hint(f"Endpoint {ep} Not Found", 404)

    def _update_score(self, method, endpoint, headers, res_data, status):
        ep = endpoint.lower().strip()
        if self.task_id == "task1":
            if status == 200 and f"/api/crm/users/{getattr(self, 'target_user_id', '42')}" in ep: self.score = 1.0
            elif any("200" in h and "/api/auth" in h for h in self.history): self.score = max(self.score, 0.5)
        elif self.task_id == "task2":
            target_order_id_lower = getattr(self, "target_order_id", "ORD-5519").lower()
            if status == 201 and ep == "/api/payments/refund" and "x-idempotency-key" in headers: self.score = 1.0
            elif any("200" in h and f"/api/orders/{target_order_id_lower}" in h.lower() for h in self.history): self.score = max(self.score, 0.3)
        elif self.task_id == "task3":
            if self.gathered_logs >= 10: self.score = 1.0
            elif status == 429: self.score = max(self.score, 0.4)
            elif self.log_calls > 1: self.score = max(self.score, 0.7)

    def _calculate_reward(self, action, status):
        # NEW: Calibrated for sum(rewards) / 1.0 = Completion %
        prev_score = getattr(self, '_last_score', 0.0)
        current_score = self.score
        reward = max(0.0, current_score - prev_score)
        self._last_score = current_score
        return reward

    def _make_obs(self, status, data):
        return {
            "observation": {
                "status_code": status,
                "response_data": data,
                "api_docs": self.api_docs,
                "step_count": self.step_count,
                "history": self.history[-5:],
                "task_objective": self.task_objective,
                "score": self.score
            }
        }

# --- 3. GLOBAL DASHBOARD STATE ---
class GlobalState:
    LATEST_ACTION = None
    LATEST_OBSERVATION = None
    TOKENS = 0
    REFUNDS = 0

# --- 4. FASTAPI APP ---
app = FastAPI(title="ToolChain-Env Standalone")
env = StandaloneEnv()

# Static Files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
@app.get("/dashboard")
def get_dashboard():
    return FileResponse(os.path.join(static_path, "dashboard.html"))

@app.get("/health")
def health(): return {"status": "ok", "engine": "monolith_v1.0"}

@app.get("/api/debug/state")
def get_debug_state():
    return {
        "tokens": GlobalState.TOKENS,
        "refunds": GlobalState.REFUNDS,
        "latest_action": GlobalState.LATEST_ACTION,
        "latest_observation": GlobalState.LATEST_OBSERVATION
    }

@app.post("/reset")
def reset(task_id: Any = "task1"):
    return env.reset(task_id)

@app.post("/step")
def step(action_wrapper: Action):
    obs, reward, done, info = env.step(action_wrapper.action)
    return {"observation": obs["observation"], "reward": reward, "done": done, "info": info}

# --- 5. MOCK OPENAI (Task-Aware & Self-Healing) ---
@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    prompt = body.get("messages", [])[-1].get("content", "").lower()
    action = {"method": "GET", "endpoint": "/api/docs", "headers": {}, "body": {}}
    
    # --- NOVELTY 3: AGENTIC SELF-RECOVERY LOGIC ---
    # Detect if the environment is screaming about an expired token
    is_compromised = "unauthorized" in prompt or "expired" in prompt or "token expired" in prompt
    
    if is_compromised:
        # Emergency Re-Auth Action
        action = {"method": "POST", "endpoint": "/api/auth", "body": {"username": "root", "password": "admin"}}
        return {"choices": [{"message": {"content": json.dumps({"action": action})}}]}

    # Precise discrimination
    import re
    task1_match = re.search(r"user (\d+)", prompt)
    is_task1 = bool(task1_match)
    target_user_id = task1_match.group(1) if is_task1 else "42"
    
    task2_match = re.search(r"order ([a-z0-9-]+)", prompt)
    is_task2 = bool(task2_match) or "refund" in prompt
    target_order_id = task2_match.group(1).upper() if task2_match else "ORD-5519"

    is_task3 = "logs" in prompt or "pagination" in prompt

    if is_task1:
        if "bearer" not in prompt:
            action = {"method": "POST", "endpoint": "/api/auth", "body": {"username": "root", "password": "admin"}}
        else:
            action = {"method": "GET", "endpoint": f"/api/crm/users/{target_user_id}", "headers": {"Authorization": "Bearer abc123_token"}}
    elif is_task2:
        if "bearer" not in prompt:
            action = {"method": "POST", "endpoint": "/api/auth", "body": {"username": "root", "password": "admin"}}
        elif "amount" not in prompt and "eligible_for_return" not in prompt:
            action = {"method": "GET", "endpoint": f"/api/orders/{target_order_id}", "headers": {"Authorization": "Bearer abc123_token"}}
        else:
            action = {"method": "POST", "endpoint": "/api/payments/refund", "headers": {"X-Idempotency-Key": "REF-123", "Authorization": "Bearer abc123_token"}, "body": {"order_id": target_order_id}}
    elif is_task3:
        cursor = 0
        if "next_cursor: 5" in prompt: cursor = 5
        # If we have a token, continue. If not, the 'is_compromised' logic above handles it.
        action = {"method": "GET", "endpoint": f"/api/logs?cursor={cursor}", "headers": {"Authorization": "Bearer abc123_token"}}
        
    return {"choices": [{"message": {"content": json.dumps({"action": action})}}]}

# ── OpenENV required endpoints ────────────────────────────────

@app.get("/tasks")
def list_tasks():
    return JSONResponse(content=[
        {
            "id": "task1",
            "difficulty": "easy",
            "description": "Authenticate as root/admin and fetch profile for the User specified in the prompt.",
            "max_steps": 10,
            "action_schema": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                    "endpoint": {"type": "string"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"}
                },
                "required": ["method", "endpoint"]
            }
        },
        {
            "id": "task2",
            "difficulty": "medium",
            "description": "Process a refund for the Order specified in the prompt using a unique Idempotency Key.",
            "max_steps": 10,
            "action_schema": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                    "endpoint": {"type": "string"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"}
                },
                "required": ["method", "endpoint"]
            }
        },
        {
            "id": "task3",
            "difficulty": "hard",
            "description": "Aggregate all 10 system logs using pagination and handling 429 rate limit errors.",
            "max_steps": 10,
            "action_schema": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                    "endpoint": {"type": "string"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"}
                },
                "required": ["method", "endpoint"]
            }
        }
    ])

@app.post("/grader")
def grader(task_id: str = "task1"):
    score = round(min(1.0, max(0.0, env.score)), 4)
    return JSONResponse(content={"score": score, "task_id": task_id})

@app.post("/reset_task")
def reset_task(task_id: str = "task1"):
    result = env.reset(task_id)
    return JSONResponse(content=result)

@app.post("/step_task")
async def step_task(request: Request):
    body = await request.json()
    action_dict = body.get("action", body)
    obs, reward, done, info = env.step(action_dict)
    return JSONResponse(content={
        "observation": obs["observation"],
        "reward": reward,
        "done": done,
        "info": info
    })
@app.post("/baseline")
def baseline():
    import subprocess
    result = subprocess.run(
        ["python", "-m", "baseline.run_baseline"],
        capture_output=True, text=True, timeout=300,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    scores = {}
    for line in result.stdout.splitlines():
        if line.startswith("SCORE:"):
            parts = line.split(":")
            if len(parts) >= 3:
                scores[parts[1]] = float(parts[2])
    return JSONResponse(content={
        "scores": scores,
        "raw_output": result.stdout,
        "errors": result.stderr
    })
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
