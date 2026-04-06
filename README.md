# ToolChain-Env

A reinforcement learning environment for training and evaluating LLM agents on real-world API orchestration tasks. The agent interacts with a mock internet — a set of REST and GraphQL endpoints — by composing HTTP requests, handling authentication, managing distributed transactions, and navigating rate limits with pagination.

Built for the Meta x HuggingFace OpenENV Hackathon.

---

## Why this exists

Training agents to use external tools reliably is one of the hardest open problems in LLM research right now. Benchmarks like ToolBench and APIBench evaluate agents on fixed datasets, but they cannot be used as RL training environments — there is no step/reset loop, no shaped reward, no episodic structure.

ToolChain-Env fills that gap. Every task runs against a deterministic mock API server, so episodes are reproducible, graders are exact, and there is no rate-limit cost or API key required to train at scale. The environment is language-agnostic: any agent that can emit a JSON payload can participate.

---

## Environment overview

The agent acts as a client navigating a network of mock REST and GraphQL services. On each step it outputs a structured HTTP action. The environment routes that action to the mock server, returns the response as an observation, and computes a shaped reward based on correctness, efficiency, and security hygiene.

The mock server runs inside the same process — no external services, no Docker-compose, no network calls outside the container.

---

## Action space

Every action is a dictionary with four fields:

| Field | Type | Description |
|---|---|---|
| `method` | string | One of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `WAIT` |
| `endpoint` | string | Target path, e.g. `/api/auth` or `/api/orders/ORD-5519` |
| `headers` | dict | Key-value pairs — Authorization, Content-Type, Idempotency-Key |
| `body` | dict or null | JSON payload for POST/PUT/PATCH requests |

`WAIT` is a no-op action used to back off during rate limiting. The agent receives a small positive reward for using WAIT correctly after a 429 response.

**Example action:**
```json
{
  "method": "POST",
  "endpoint": "/api/payments/refund",
  "headers": {
    "Authorization": "Bearer tok_abc123",
    "Idempotency-Key": "req_9982",
    "Content-Type": "application/json"
  },
  "body": {
    "order_id": "ORD-5519",
    "reason": "customer_requested"
  }
}
```

---

## Observation space

After each step the agent receives:

| Field | Type | Description |
|---|---|---|
| `status_code` | int | HTTP status — 200, 201, 400, 401, 404, 429 |
| `response_data` | dict | Parsed JSON response body |
| `simulated_latency_ms` | float | Artificial latency injected by the environment |
| `task_description` | string | Natural language goal for this episode |
| `api_docs` | string | Available endpoints and their request schemas |
| `step_budget_remaining` | int | Steps left before forced episode termination |
| `rate_limit_reset_in` | int | Steps to wait before rate limit resets (0 = clear) |
| `episode_log` | list | Last 5 actions and their outcomes |

**Example observation:**
```json
{
  "status_code": 201,
  "response_data": {
    "success": true,
    "refund_id": "REF-ORD-5519",
    "amount": 49.99,
    "status": "processing"
  },
  "simulated_latency_ms": 142.5,
  "task_description": "Process a refund for order ORD-5519 with idempotency guarantees.",
  "step_budget_remaining": 6,
  "rate_limit_reset_in": 0
}
```

---

## Tasks

### Task 1 — The Data Fetch `[easy]`

The agent must authenticate against `/api/auth` using provided credentials, obtain a Bearer token, and use it to retrieve a specific user profile from `/api/crm/users/{id}`.

**Grader checkpoints:**

| Score | Condition |
|---|---|
| 0.0 | Failed to authenticate or retrieve a token |
| 0.3 | Obtained token but never called the CRM endpoint |
| 0.5 | Called CRM but received 400 or 404 (wrong URL or missing token) |
| 1.0 | Retrieved the correct user profile successfully |

**Max steps:** 8

---

### Task 2 — The Distributed Transaction `[medium]`

The agent must authenticate, query `/api/orders/{order_id}` to retrieve an order and verify refund eligibility, then POST to `/api/payments/refund` with the correct JSON body **and** an `Idempotency-Key` header to prevent double-charging.

**Grader checkpoints:**

| Score | Condition |
|---|---|
| 0.0 | Did nothing meaningful or crashed on first call |
| 0.3 | Retrieved order data but never attempted a refund |
| 0.8 | Refund processed successfully but Idempotency-Key was missing |
| 1.0 | Refund processed with correct Idempotency-Key header |

The 0.8 checkpoint specifically tests whether the agent understands distributed systems safety — processing a payment without idempotency protection is a real production risk.

**Max steps:** 12

---

### Task 3 — Rate-Limit Evasion and GraphQL Pagination `[hard]`

The agent must authenticate and then extract the full set of system logs from a GraphQL endpoint that enforces strict rate limiting (maximum 3 calls per 5-step window, returning 429 on violation) and requires cursor-based pagination to retrieve all records.

**Grader checkpoints:**

| Score | Condition |
|---|---|
| 0.0 | Spammed the endpoint and got blocked, collected no logs |
| 0.4 | Handled rate limiting with WAIT actions but failed to paginate |
| 0.7 | Paginated through some pages but stopped before the final cursor |
| 1.0 | Collected every log entry across all pages |

**Max steps:** 30

---

## Reward function

Reward is shaped at every step — not just at episode end.

| Signal | Reward |
|---|---|
| Successful API call (200/201) | +0.15 |
| Correct Idempotency-Key on refund | +0.20 |
| WAIT used correctly after 429 | +0.05 |
| Rate limited (429) — should have waited | -0.10 |
| Auth error (401) — forgot token | -0.08 |
| Malformed request (400/404) | -0.05 |
| WAIT used when not rate-limited | -0.05 |
| Time step cost (every step) | -0.01 |
| Terminal bonus | grade_score × 0.5 |

The terminal bonus is a scaled version of the episode grader score, so the shaped reward and final grade are always consistent.

---

## Setup

**Requirements:** Python 3.11, Docker
```bash
# Clone and set up environment
git clone https://github.com/Vishaal-sathya/tool_chain_env
cd tool_chain_env

py -3.11 -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

**Run locally:**
```bash
uvicorn server.app:app --reload --port 8000
```

**Run with Docker:**
```bash
docker build -t tool-chain-env -f server/Dockerfile .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... tool-chain-env
```

---

## API reference

Once running, all endpoints are available at `http://localhost:8000`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check — returns `{"status":"ok"}` |
| GET | `/tasks` | List all tasks with action schema |
| POST | `/reset_task?task_id=data_fetch` | Start a new episode |
| POST | `/step_task?task_id=data_fetch` | Submit one action |
| GET | `/state_task?task_id=data_fetch` | Current episode state |
| POST | `/grader?task_id=data_fetch` | Episode score (0.0–1.0) |
| POST | `/baseline` | Run full baseline script, returns all scores |

**Full API docs** (Swagger UI): `http://localhost:8000/docs`

---

## Running the baseline
```bash
export OPENAI_API_KEY=sk-your-key-here
export ENV_BASE_URL=http://localhost:8000

python -m baseline.run_baseline
```

**Expected output:**