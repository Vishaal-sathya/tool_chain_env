import uuid, time, random, re, string
from typing import Any, Dict, Tuple
from models import ToolChainAction, ToolChainObservation, State
from server import mock_api
from server.grader import grade_episode

# ── Task definitions ──────────────────────────────────────────
TASKS = {
    "task1": {
        "description": "Authenticate with /api/auth using the credentials provided, then retrieve the profile for the episode-specific user ID from /api/crm/users/{id}.",
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
            "Goal: Authenticate first, then GET /api/crm/users/{id} with the Bearer token."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
            "token": "tok_" + uuid.uuid4().hex[:12],
            "users": {},
        },
    },
    "task2": {
        "description": "Use the token from /api/auth to get the episode-specific order from /api/orders/{order_id}, verify it is eligible for refund, then POST to /api/payments/refund with an Idempotency-Key header to prevent double-charging.",
        "max_steps": 12,
        "api_docs": (
            "POST /api/auth\n"
            "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
            "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
            "\n"
            "GET /api/orders/{order_id}\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
            "  Returns: {\"id\": string, \"amount\": float, \"eligible_for_refund\": bool, \"customer_id\": int}\n"
            "\n"
            "POST /api/payments/refund\n"
            "  Headers: {\"Authorization\": \"Bearer <token>\", \"Idempotency-Key\": \"<unique-string>\", \"Content-Type\": \"application/json\"}\n"
            "  Body: {\"order_id\": \"ORD-AA1234\"}\n"
            "  Returns: {\"success\": bool, \"refund_id\": string, \"amount\": float, \"status\": string}\n"
            "\n"
            "Goal: Auth → GET the assigned order → POST refund with Idempotency-Key header."
        ),
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
            "token": "tok_" + uuid.uuid4().hex[:12],
            "orders": {},
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
            "token": "tok_" + uuid.uuid4().hex[:12],
            "system_logs": [{"id": f"log_{i:03d}", "level": random.choice(["INFO","WARN","ERROR"]), "message": f"Event {i}", "ts": 1700000000 + i*60} for i in range(18)],
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
            "token": "tok_" + uuid.uuid4().hex[:12],
            "webhook_id": "wh_" + uuid.uuid4().hex[:12],
            "webhook_secret": "whsec_" + uuid.uuid4().hex[:24],
        },
    },
    "task5": {
        "description": "No docs. Discover auth and hidden export endpoints, then retrieve admin export.",
        "max_steps": 20,
        "api_docs": "",
        "episode_data": {
            "valid_user": "agent",
            "valid_pass": "secret123",
            "token": "tok_" + uuid.uuid4().hex[:12],
        },
    },
}

class ToolChainEnvironment:
    def __init__(self, task_id: str = "task1"):
        self.task_id   = task_id
        self.task      = TASKS[task_id]
        self._task_description = self.task["description"]
        self._task_api_docs = self.task["api_docs"]
        self._episode_id = ""
        self._step     = 0
        self._log: list = []
        self._done     = False
        self._episode_data: dict = {}

    # ── OpenENV interface ─────────────────────────────────────
    def reset(self, seed: int | None = None) -> ToolChainObservation:
        if seed is not None:
            random.seed(seed)
        self._episode_id = str(uuid.uuid4())
        self._step       = 0
        self._log        = []
        self._done       = False
        import copy
        self._episode_data = copy.deepcopy(self.task["episode_data"])
        self._task_description = self.task["description"]
        self._task_api_docs = self.task["api_docs"]
        self._episode_data["start_time"] = time.time()

        if self.task_id == "task1":
            target_user_id = random.randint(1, 999)
            self._episode_data["target_user_id"] = target_user_id
            self._episode_data["users"] = {
                str(target_user_id): {
                    "id": target_user_id,
                    "name": f"User {target_user_id}",
                    "email": f"user{target_user_id}@acme.com",
                    "plan": "enterprise",
                }
            }
            self._task_description = (
                "Authenticate with /api/auth using the credentials provided, then retrieve the profile "
                f"for user ID {target_user_id} from /api/crm/users/{target_user_id}."
            )
            self._task_api_docs = (
                "POST /api/auth\n"
                "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
                "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
                "\n"
                "GET /api/crm/users/{id}\n"
                "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
                "  Returns: {\"id\": int, \"name\": string, \"email\": string, \"plan\": string}\n"
                "\n"
                f"Goal: Authenticate first, then GET /api/crm/users/{target_user_id} with the Bearer token."
            )
        elif self.task_id == "task2":
            target_order_id = "ORD-" + "".join(random.choices(string.ascii_uppercase, k=2)) + "".join(random.choices(string.digits, k=4))
            self._episode_data["target_order_id"] = target_order_id
            self._episode_data["orders"] = {
                target_order_id: {
                    "id": target_order_id,
                    "amount": 49.99,
                    "eligible_for_refund": True,
                    "customer_id": random.randint(1, 999),
                }
            }
            self._task_description = (
                "Use the token from /api/auth to get order "
                f"{target_order_id} from /api/orders/{target_order_id}, verify it is eligible for refund, then POST to "
                "/api/payments/refund with an Idempotency-Key header to prevent double-charging."
            )
            self._task_api_docs = (
                "POST /api/auth\n"
                "  Body: {\"username\": \"agent\", \"password\": \"secret123\"}\n"
                "  Returns: {\"token\": \"<bearer_token>\", \"expires_in\": 3600}\n"
                "\n"
                "GET /api/orders/{order_id}\n"
                "  Headers: {\"Authorization\": \"Bearer <token>\"}\n"
                "  Returns: {\"id\": string, \"amount\": float, \"eligible_for_refund\": bool, \"customer_id\": int}\n"
                "\n"
                "POST /api/payments/refund\n"
                "  Headers: {\"Authorization\": \"Bearer <token>\", \"Idempotency-Key\": \"<unique-string>\", \"Content-Type\": \"application/json\"}\n"
                f"  Body: {{\"order_id\": \"{target_order_id}\"}}\n"
                "  Returns: {\"success\": bool, \"refund_id\": string, \"amount\": float, \"status\": string}\n"
                "\n"
                f"Goal: Auth -> GET order {target_order_id} -> POST refund with Idempotency-Key header."
            )
        elif self.task_id == "task5":
            self._episode_data["dark_pkce_verifier"] = "pkce_" + uuid.uuid4().hex[:10]
            self._episode_data["dark_oauth_token"] = "dark_tok_" + uuid.uuid4().hex[:16]
            self._task_api_docs = "No API documentation is available for this task."

        # Critical: populate mock API store with this episode's data
        from server import mock_api as _mock_api
        _mock_api.reset_store(self._episode_data)

        return ToolChainObservation(
            task_description=self._task_description,
            api_docs=self._task_api_docs,
            step_budget_remaining=self.task["max_steps"] - self._step,
            rate_limit_reset_in=0,
            episode_log=self._log[-5:],
        )

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
            score = grade_episode(self)
            reward += score * 0.5

        partial_score = grade_episode(self)
        info = {
            "episode_id": self._episode_id,
            "step": self._step,
            "task_id": self.task_id,
            "partial_score": round(float(partial_score), 4),
            "rate_limit_calls_remaining": max(0, 3 - mock_api._rate_limit_counter.get("calls", 0)),
        }
        obs = self._make_obs(status, resp, latency)
        return obs, reward, self._done, info

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

        # Task 5 dark API discovery endpoints
        elif method == "GET" and endpoint == "/api/dark/probe":
            status, resp = mock_api._dark_probe_handler(headers)
        elif method == "POST" and endpoint == "/api/dark/oauth/token":
            status, resp = mock_api._dark_oauth_token_handler(body, headers)
        elif method == "GET" and endpoint == "/api/admin/export":
            status, resp = mock_api._dark_admin_export_handler(headers)

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
        """Shaped reward for each step."""
        reward = 0.0
        # Generic rewards/penalties
        if status in (200, 201):
            reward += 0.15
        elif status == 401:
            reward -= 0.08
        elif status in (400, 404):
            reward -= 0.05
        elif status == 429:
            reward -= 0.10

        # Task-specific rewards
        if self.task_id == "task2":
            idempotency_key = action.headers.get("Idempotency-Key") or action.headers.get("idempotency-key")
            if status == 200 and "payments/refund" in action.endpoint and idempotency_key:
                reward += 0.20
        elif self.task_id == "task4":
            if mock_api._store.get("signature_verified"):
                reward += 0.25
            if mock_api._store.get("webhook_acknowledged"):
                reward += 0.15
        return reward

    def _is_terminal(self, status: int, resp: dict) -> bool:
        """Terminal states: success, crash, or specific errors."""
        if self.task_id == "task1":
            return status == 200 and "crm/users" in self._log[-1]["endpoint"]
        if self.task_id == "task2":
            return status == 200 and "payments/refund" in self._log[-1]["endpoint"]
        if self.task_id == "task3":
            # Terminal if we've collected all logs
            return len(mock_api._store.get("collected_log_ids", set())) >= len(self._episode_data.get("system_logs", []))
        if self.task_id == "task4":
            return mock_api._store.get("webhook_acknowledged", False)
        if self.task_id == "task5":
            return mock_api._store.get("dark_export_retrieved", False)
        return False

    def _make_obs(self, status: int, resp: dict, latency: float) -> ToolChainObservation:
        rl_reset = 0
        if status == 429:
            rl_reset = resp.get("retry_after_steps", 5)
        return ToolChainObservation(
            status_code=status,
            response_data=resp,
            simulated_latency_ms=latency,
            task_description=self._task_description,
            api_docs=self._task_api_docs,
            step_budget_remaining=self.task["max_steps"] - self._step,
            rate_limit_reset_in=rl_reset,
            episode_log=self._log[-5:],
        )