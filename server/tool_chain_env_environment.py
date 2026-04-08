import uuid, time, random, re
from typing import Any, Dict, Tuple
from models import ToolChainAction, ToolChainObservation, State
from . import mock_api

# ── Task definitions ──────────────────────────────────────────
TASKS = {
    "task1": {
        "description": "Authenticate with /api/auth using the credentials provided, then retrieve the profile for user ID {user_id} from /api/crm/users/{user_id}.",
        "max_steps": 8,
        "api_docs": (
            "POST /api/auth\n"
            "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
            "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
            "\n"
            "GET /api/crm/users/{id}\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
            "  Returns: {\"id\": int, \"name\": string, \"email\": string, \"plan\": string}\n"
            "\n"
            "Goal: Authenticate first, then GET /api/crm/users/{user_id} with the Bearer token."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
        },
    },
    "task2": {
        "description": "Use the token from /api/auth to get order {order_id} from /api/orders/{order_id}, verify it is eligible for refund, then POST to /api/payments/refund with an Idempotency-Key header to prevent double-charging.",
        "max_steps": 12,
        "api_docs": (
            "POST /api/auth\n"
            "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
            "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
            "\n"
            "GET /api/orders/{id}\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
            "  Returns: {\"id\": string, \"amount\": float, \"eligible_for_refund\": bool, \"customer_id\": int}\n"
            "\n"
            "POST /api/payments/refund\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\", \"Idempotency-Key\": \"<unique-string>\", \"Content-Type\": \"application/json\"}\n"
            "  Body: {\"order_id\": \"{order_id}\"}\n"
            "  Returns: {\"success\": bool, \"refund_id\": string, \"amount\": float, \"status\": string}\n"
            "\n"
            "Goal: Auth → GET order {order_id} → POST refund with Idempotency-Key header."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
        },
    },
    "task3": {
        "description": "Authenticate, then extract ALL system logs from /api/graphql using cursor-based pagination. The server rate-limits to 3 calls per 5 steps — use WAIT actions to back off on 429 responses. Collect every log entry.",
        "max_steps": 30,
        "api_docs": (
            "POST /api/auth\n"
            "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
            "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
            "\n"
            "POST /api/graphql\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
            "  Body: {\"query\": \"{ systemLogs }\", \"variables\": {\"cursor\": null}}\n"
            "  Returns: {\"data\": {\"systemLogs\": {\"edges\": [...], \"pageInfo\": {\"nextCursor\": string|null, \"hasNextPage\": bool}}}}\n"
            "\n"
            "Rate limit: max 3 calls per 5-step window. On 429, use WAIT action to back off.\n"
            "Pagination: pass the nextCursor value as variables.cursor to get the next page.\n"
            "Continue until hasNextPage is false and nextCursor is null.\n"
            "\n"
            "Goal: Auth → paginate ALL system logs via GraphQL, respecting rate limits."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
        },
    },
    "task4": {
        "description": "Register a webhook, trigger an event to fire it, poll for the delivery, verify the HMAC-SHA256 signature, and acknowledge receipt. This tests event-driven architecture understanding and cryptographic verification.",
        "max_steps": 15,
        "api_docs": (
            "POST /api/auth\n"
            "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
            "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
            "\n"
            "POST /api/webhooks/register\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\", \"Content-Type\": \"application/json\"}\n"
            "  Body: {\"callback_url\": \"https://agent.example.com/webhook\"}\n"
            "  Returns: {\"webhook_id\": string, \"secret\": string, \"callback_url\": string, \"status\": \"active\"}\n"
            "  IMPORTANT: Save the 'secret' — you need it to verify signatures later.\n"
            "\n"
            "POST /api/events/trigger\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\", \"Content-Type\": \"application/json\"}\n"
            "  Body: {\"event_type\": \"order.completed\", \"webhook_id\": \"<webhook_id>\"}\n"
            "  Returns: {\"event_id\": string, \"event_type\": string, \"webhook_id\": string, \"status\": \"dispatched\"}\n"
            "\n"
            "GET /api/webhooks/{webhook_id}/deliveries\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
            "  Returns: {\"deliveries\": [{\"delivery_id\": string, \"payload\": object, \"signature\": \"sha256=<hex>\", \"status\": string}]}\n"
            "\n"
            "POST /api/webhooks/verify\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\", \"Content-Type\": \"application/json\"}\n"
            "  Body: {\"delivery_id\": string, \"signature\": \"sha256=<hex>\", \"payload\": object}\n"
            "  Returns: {\"verified\": bool, \"delivery_id\": string, \"status\": string}\n"
            "  NOTE: Pass the exact signature string from the delivery response.\n"
            "\n"
            "POST /api/webhooks/{webhook_id}/acknowledge\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\", \"Content-Type\": \"application/json\"}\n"
            "  Body: {\"confirmed\": true}\n"
            "  Returns: {\"acknowledged\": true, \"webhook_id\": string, \"status\": \"confirmed\"}\n"
            "\n"
            "Goal: Auth → Register webhook → Trigger event → Poll deliveries → Verify HMAC signature → Acknowledge."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
        },
    },
}

class ToolChainEnvironment:
    def __init__(self, task_id: str = "task1"):
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
        import string
        
        self._episode_data = copy.deepcopy(self.task["episode_data"])
        self._active_task = copy.deepcopy(self.task)
        
        self._episode_data["current_step"] = 0
        self._episode_data["token"] = "tok_" + uuid.uuid4().hex[:12]
        
        if self.task_id == "task1":
            user_id = random.randint(100, 999)
            self._episode_data["target_user_id"] = user_id
            self._episode_data["users"] = {str(user_id): {"id": user_id, "name": "Dynamic User", "email": "user@acme.com", "plan": "enterprise"}}
            
            self._active_task["description"] = self._active_task["description"].replace("{user_id}", str(user_id))
            self._active_task["api_docs"] = self._active_task["api_docs"].replace("{user_id}", str(user_id))
            
        elif self.task_id == "task2":
            order_alph = "".join(random.choices(string.ascii_uppercase, k=3))
            order_num = random.randint(1000, 9999)
            order_id = f"{order_alph}-{order_num}"
            self._episode_data["target_order_id"] = order_id
            self._episode_data["orders"] = {order_id: {"id": order_id, "amount": round(random.uniform(10, 500), 2), "eligible_for_refund": True, "customer_id": random.randint(100, 999)}}
            
            self._active_task["description"] = self._active_task["description"].replace("{order_id}", str(order_id))
            self._active_task["api_docs"] = self._active_task["api_docs"].replace("{order_id}", str(order_id))
            
        elif self.task_id == "task3":
            self._episode_data["system_logs"] = [{"id": f"log_{i:03d}", "level": random.choice(["INFO","WARN","ERROR"]), "message": f"Event {i}", "ts": 1700000000 + i*60} for i in range(18)]

        elif self.task_id == "task4":
            self._episode_data["webhook_id"] = "wh_" + uuid.uuid4().hex[:12]
            self._episode_data["webhook_secret"] = "whsec_" + uuid.uuid4().hex[:24]

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

        # ── Task 4: Webhook endpoints ─────────────────────────
        # POST /api/webhooks/register
        elif method == "POST" and endpoint == "/api/webhooks/register":
            status, resp = mock_api._webhook_register_handler(body, headers)

        # POST /api/events/trigger
        elif method == "POST" and endpoint == "/api/events/trigger":
            status, resp = mock_api._event_trigger_handler(body, headers)

        # GET /api/webhooks/{webhook_id}/deliveries
        elif method == "GET" and re.match(r"/api/webhooks/[^/]+/deliveries", endpoint):
            webhook_id = endpoint.split("/api/webhooks/")[1].split("/deliveries")[0]
            status, resp = mock_api._webhook_deliveries_handler(webhook_id, headers)

        # POST /api/webhooks/verify
        elif method == "POST" and endpoint == "/api/webhooks/verify":
            status, resp = mock_api._webhook_verify_handler(body, headers)

        # POST /api/webhooks/{webhook_id}/acknowledge
        elif method == "POST" and re.match(r"/api/webhooks/[^/]+/acknowledge", endpoint):
            webhook_id = endpoint.split("/api/webhooks/")[1].split("/acknowledge")[0]
            status, resp = mock_api._webhook_acknowledge_handler(webhook_id, body, headers)

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
            if action.headers.get("Idempotency-Key") or action.headers.get("X-Idempotency-Key"):
                r += 0.20
        # Webhook-specific rewards
        if "webhooks/verify" in action.endpoint and status == 200:
            r += 0.25  # big reward for correct HMAC verification
        if "webhooks" in action.endpoint and "acknowledge" in action.endpoint and status == 200:
            r += 0.15  # reward for completing the full webhook lifecycle
        return r

    def _terminal_reward(self) -> float:
        from .grader import grade_episode
        score = grade_episode(self)
        return score * 0.5

    def _is_terminal(self, status: int, resp: dict) -> bool:
        task = self.task_id
        if task == "task1":
            return status == 200 and "email" in resp
        if task == "task2":
            return mock_api._store.get("refund_processed", False)
        if task == "task3":
            collected = len(mock_api._store.get("collected_log_ids", set()))
            total = len(self._episode_data.get("system_logs", []))
            return collected >= total
        if task == "task4":
            return mock_api._store.get("webhook_acknowledged", False)
        return False

    def _make_obs(self, status_code, response_data, latency) -> ToolChainObservation:
        rl_reset = 0
        if status_code == 429:
            rl_reset = response_data.get("retry_after_steps", 5)
        
        active = getattr(self, "_active_task", self.task)
        
        return ToolChainObservation(
            status_code=status_code,
            response_data=response_data,
            simulated_latency_ms=latency,
            task_description=active["description"],
            api_docs=active["api_docs"],
            step_budget_remaining=active["max_steps"] - self._step,
            rate_limit_reset_in=rl_reset,
            episode_log=self._log[-5:],
        )