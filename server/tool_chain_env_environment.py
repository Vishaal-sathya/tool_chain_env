import uuid, time, random, re
from typing import Any, Dict, Tuple
from models import ToolChainAction, ToolChainObservation, State
from . import mock_api

# ── Task definitions ──────────────────────────────────────────
TASKS = {
    "data_fetch": {
        "description": "Authenticate with /api/auth using the credentials provided, then retrieve the profile for user ID 42 from /api/crm/users/42.",
        "max_steps": 8,
        "api_docs": (
            "POST /api/auth  body:{username,password}  → {token}\n"
            "GET  /api/crm/users/{id}  header:Authorization:Bearer <token>  → user JSON"
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
            "token": "tok_" + uuid.uuid4().hex[:12],
            "users": {"42": {"id": 42, "name": "Jane Doe", "email": "jane@acme.com", "plan": "enterprise"}},
        },
        "target_user_id": 42,
    },
    "distributed_transaction": {
        "description": "Use the token from /api/auth to get order ORD-5519 from /api/orders/ORD-5519, verify it is eligible for refund, then POST to /api/payments/refund with an Idempotency-Key header to prevent double-charging.",
        "max_steps": 12,
        "api_docs": (
            "POST /api/auth  body:{username,password}  → {token}\n"
            "GET  /api/orders/{order_id}  header:Authorization  → order JSON\n"
            "POST /api/payments/refund  headers:Authorization,Idempotency-Key  body:{order_id,reason}  → {refund_id}"
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
            "token": "tok_" + uuid.uuid4().hex[:12],
            "orders": {
                "ORD-5519": {"id": "ORD-5519", "amount": 49.99, "eligible_for_refund": True, "customer_id": 42}
            },
        },
    },
    "rate_limit_graphql": {
        "description": "Authenticate, then extract ALL system logs from /api/graphql using cursor-based pagination. The server rate-limits to 3 calls per 5 steps — use WAIT actions to back off on 429 responses. Collect every log entry.",
        "max_steps": 30,
        "api_docs": (
            "POST /api/auth  body:{username,password}  → {token}\n"
            "POST /api/graphql  header:Authorization  body:{query:'{ systemLogs }',variables:{cursor:null}}  → {data:{systemLogs:{edges:[],pageInfo:{nextCursor,hasNextPage}}}}\n"
            "Use WAIT method to back off when you receive 429."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
            "token": "tok_" + uuid.uuid4().hex[:12],
            "system_logs": [{"id": f"log_{i:03d}", "level": random.choice(["INFO","WARN","ERROR"]), "message": f"Event {i}", "ts": 1700000000 + i*60} for i in range(18)],
        },
    },
}

class ToolChainEnvironment:
    def __init__(self, task_id: str = "data_fetch"):
        self.task_id   = task_id
        self.task      = TASKS[task_id]
        self._episode_id = ""
        self._step     = 0
        self._log: list = []
        self._done     = False
        self._episode_data: dict = {}

    # ── OpenENV interface ─────────────────────────────────────
    def reset(self) -> ToolChainObservation:
        self._episode_id = str(uuid.uuid4())
        self._step       = 0
        self._log        = []
        self._done       = False
        import copy
        self._episode_data = copy.deepcopy(self.task["episode_data"])
        self._episode_data["current_step"] = 0
        mock_api.reset_store(self._episode_data)
        mock_api._rate_limit_counter.update({"calls":0,"window_start_step":0})
        return self._make_obs(status_code=0, response_data={"message":"Episode started. Read task_description and api_docs."}, latency=0.0)

    def step(self, action: ToolChainAction) -> Tuple[ToolChainObservation, float, bool, Dict]:
        if self._done:
            return self._make_obs(0, {}, 0.0), 0.0, True, {}

        self._step += 1
        self._episode_data["current_step"] = self._step
        mock_api._store["current_step"] = self._step

        reward = -0.01  # time cost every step

        if action.method == "WAIT":
            was_rate_limited = any(
                e.get("status_code") == 429
                for e in self._log[-3:]
            )
            reward += 0.05 if was_rate_limited else -0.05
            latency = 0.0
            status, resp = 0, {"message": "Waited one step"}
        else:
            status, resp, latency = self._call_mock(action)
            reward += self._step_reward(action, status, resp)

        self._log.append({
            "step": self._step,
            "method": action.method,
            "endpoint": action.endpoint,
            "headers": action.headers,
            "body": action.body,
            "status_code": status,
            "latency_ms": latency,
        })

        self._done = self._step >= self.task["max_steps"] or self._is_terminal(status, resp)
        if self._done:
            reward += self._terminal_reward()

        obs = self._make_obs(status, resp, latency)
        return obs, reward, self._done, {"episode_id": self._episode_id}

    def state(self) -> State:
        return State(episode_id=self._episode_id, step_count=self._step)

    # ── Internal helpers ──────────────────────────────────────
    def _call_mock(self, action: ToolChainAction):
        """Route action to mock_api handler functions directly (no HTTP)."""
        t0 = time.perf_counter()
        endpoint = action.endpoint
        method = action.method.upper()
        headers = action.headers or {}
        body = action.body or {}

        status, resp = 400, {"error": "Unknown endpoint"}

        # POST /api/auth
        if method == "POST" and endpoint == "/api/auth":
            status, resp = mock_api._auth_handler(body, headers)

        # GET /api/crm/users/{user_id}
        elif method == "GET" and endpoint.startswith("/api/crm/users/"):
            match = re.match(r"/api/crm/users/(\d+)", endpoint)
            if match:
                user_id = int(match.group(1))
                status, resp = mock_api._get_user_handler(user_id, headers)
            else:
                status, resp = 400, {"error": "Invalid user ID"}

        # GET /api/orders/{order_id}
        elif method == "GET" and endpoint.startswith("/api/orders/"):
            order_id = endpoint.split("/api/orders/")[-1]
            status, resp = mock_api._get_order_handler(order_id, headers)

        # POST /api/payments/refund
        elif method == "POST" and endpoint == "/api/payments/refund":
            status, resp = mock_api._refund_handler(body, headers)

        # POST /api/graphql
        elif method == "POST" and endpoint == "/api/graphql":
            status, resp = mock_api._graphql_handler(body, headers)

        latency = round((time.perf_counter() - t0) * 1000, 2)
        return status, resp, latency

    def _step_reward(self, action: ToolChainAction, status: int, resp: dict) -> float:
        r = 0.0
        if status in (200, 201):
            r += 0.15
        elif status == 429:
            r -= 0.10
        elif status in (400, 404):
            r -= 0.05
        elif status == 401:
            r -= 0.08
        if action.endpoint == "/api/payments/refund" and status == 200:
            if action.headers.get("Idempotency-Key"):
                r += 0.20
        return r

    def _terminal_reward(self) -> float:
        from .grader import grade_episode
        score = grade_episode(self)
        return score * 0.5

    def _is_terminal(self, status: int, resp: dict) -> bool:
        task = self.task_id
        if task == "data_fetch":
            return status == 200 and "email" in resp
        if task == "distributed_transaction":
            return mock_api._store.get("refund_processed", False)
        if task == "rate_limit_graphql":
            collected = len(mock_api._store.get("collected_log_ids", set()))
            total = len(self._episode_data.get("system_logs", []))
            return collected >= total
        return False

    def _make_obs(self, status_code, response_data, latency) -> ToolChainObservation:
        rl_reset = 0
        if status_code == 429:
            rl_reset = response_data.get("retry_after_steps", 5)
        return ToolChainObservation(
            status_code=status_code,
            response_data=response_data,
            simulated_latency_ms=latency,
            task_description=self.task["description"],
            api_docs=self.task["api_docs"],
            step_budget_remaining=self.task["max_steps"] - self._step,
            rate_limit_reset_in=rl_reset,
            episode_log=self._log[-5:],
        )