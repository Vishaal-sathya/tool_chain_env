---
title: ToolChain-Env
emoji: 🔧
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
---

# ToolChain-Env: API Orchestration RL Environment

Training agents to reliably use external APIs is one of the hardest open problems in agentic AI. Current benchmarks like ToolBench and APIBench evaluate agents on static datasets — they offer no episodic loop, no shaped reward, and no way to train with reinforcement learning. **ToolChain-Env** fills that gap: a fully episodic RL environment built around real-world API orchestration patterns including authentication flows, idempotent distributed transactions, rate-limited pagination, and webhook-driven event verification.

Built for the **Meta × HuggingFace OpenENV Hackathon**.

---

## Why This Domain

LLM agents routinely fail at multi-step API workflows because they:
- **Hallucinate endpoint names** that don't exist
- **Forget auth tokens** between steps
- **Don't understand idempotency** — they retry payments without deduplication keys, causing double-charges
- **Cannot handle rate limits** — they spam endpoints until they get blocked
- **Have no concept of webhooks** — event-driven architectures are completely foreign to language models

These are not edge cases. They are the core failure modes that prevent LLM agents from being deployed in production API integrations. ToolChain-Env provides the first RL training environment where agents can learn to overcome each of these failure modes through shaped reward signals and episodic structure.

---

## Task Overview

| Task | Difficulty | Max Steps | Key Skill |
|------|-----------|-----------|-----------|
| **Task 1 — The Data Fetch** | Easy | 8 | Bearer token auth → CRM data retrieval |
| **Task 2 — The Distributed Transaction** | Medium | 12 | Idempotency-key protected payment refund |
| **Task 3 — Rate-Limit Evasion & Pagination** | Hard | 30 | GraphQL cursor pagination under rate limits |
| **Task 4 — Webhook Verification** | Expert | 15 | HMAC-SHA256 signature verification + event lifecycle |

---

## Action Space

Every action is a JSON object with four fields:

| Field | Type | Description |
|-------|------|-------------|
| `method` | `string` | One of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `WAIT` |
| `endpoint` | `string` | Target path, e.g. `/api/auth` or `/api/orders/ORD-5519` |
| `headers` | `dict` | Key-value pairs — Authorization, Content-Type, Idempotency-Key |
| `body` | `dict` or `null` | JSON payload for POST/PUT/PATCH requests |

`WAIT` is a special no-op action used to back off during rate limiting. The agent receives a positive reward for using WAIT correctly after a 429 response.

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
    "order_id": "ORD-5519"
  }
}
```

---

## Observation Space

After each step the agent receives:

| Field | Type | Description |
|-------|------|-------------|
| `status_code` | `int` | HTTP status — 200, 201, 400, 401, 404, 429 |
| `response_data` | `dict` | Parsed JSON response body |
| `simulated_latency_ms` | `float` | Artificial latency injected by the environment |
| `task_description` | `string` | Natural language goal for this episode |
| `api_docs` | `string` | Available endpoints with exact request/response schemas |
| `step_budget_remaining` | `int` | Steps left before forced episode termination |
| `rate_limit_reset_in` | `int` | Steps to wait before rate limit resets (0 = clear) |
| `episode_log` | `list` | Last 5 actions and their outcomes |

---

## Task Details

### Task 1 — The Data Fetch `[easy]`

Authenticate against `/api/auth` with provided credentials, obtain a Bearer token, and retrieve a specific user profile from `/api/crm/users/{id}`.

| Score | Condition |
|-------|-----------|
| 0.0 | Failed to authenticate or retrieve a token |
| 0.3 | Obtained token but never called the CRM endpoint |
| 0.5 | Called CRM but received 400/404 (wrong URL or missing token) |
| 0.7 | Retrieved a user profile but wrong user ID |
| 1.0 | Retrieved the correct user profile successfully |

### Task 2 — The Distributed Transaction `[medium]`

Authenticate, retrieve order details from `/api/orders/{order_id}`, verify refund eligibility, then POST to `/api/payments/refund` with an `Idempotency-Key` header.

| Score | Condition |
|-------|-----------|
| 0.0 | Did nothing meaningful or crashed |
| 0.3 | Retrieved order data but never attempted refund |
| 0.8 | Refund processed but Idempotency-Key was missing |
| 1.0 | Refund processed with correct Idempotency-Key |

The 0.8 → 1.0 gap specifically tests distributed systems safety. Processing payments without idempotency protection is a real production risk.

### Task 3 — Rate-Limit Evasion & GraphQL Pagination `[hard]`

Authenticate and extract all system logs from a GraphQL endpoint that enforces strict rate limiting (max 3 calls per 5-step window) and requires cursor-based pagination.

| Score | Condition |
|-------|-----------|
| 0.0 | Spammed endpoint, collected nothing |
| 0.2–0.3 | Collected some logs but poor rate-limit handling |
| 0.4 | Used WAIT correctly but stopped paginating early |
| 0.7 | Paginated most pages but missed the final cursor |
| 1.0 | Collected every log entry across all pages |

### Task 4 — Webhook Verification `[expert]`

Register a webhook endpoint, trigger an event to fire it, poll for the delivery, verify the HMAC-SHA256 signature, and acknowledge receipt. This tests understanding of event-driven architectures and cryptographic verification — skills no toy environment can teach.

| Score | Condition |
|-------|-----------|
| 0.0 | Failed to authenticate |
| 0.2 | Authenticated but never registered webhook |
| 0.4 | Registered webhook but never triggered event |
| 0.6 | Triggered event and polled deliveries |
| 0.8 | Verified HMAC-SHA256 signature correctly |
| 1.0 | Completed full webhook lifecycle with acknowledgement |

---

## Reward Function

Reward is shaped at every step — not just at episode end.

| Signal | Reward |
|--------|--------|
| Successful API call (200/201) | +0.15 |
| Correct Idempotency-Key on refund | +0.20 |
| HMAC signature verified | +0.25 |
| Webhook acknowledged | +0.15 |
| WAIT used correctly after 429 | +0.05 |
| Rate limited (429) — should have waited | −0.10 |
| Auth error (401) — forgot token | −0.08 |
| Malformed request (400/404) | −0.05 |
| WAIT used when not rate-limited | −0.05 |
| Time step cost (every step) | −0.01 |
| Terminal bonus | `grade_score × 0.5` |

The terminal bonus is a scaled version of the episode grader score, ensuring shaped rewards and final grades are always consistent.

---

## Setup

**Requirements:** Python 3.11+

```bash
# Clone and install
git clone https://github.com/Vishaal-sathya/tool_chain_env
cd tool_chain_env
pip install -r requirements.txt

# Run the server
uvicorn app:app --host 0.0.0.0 --port 8000
```

**Docker:**
```bash
docker build -t tool-chain-env .
docker run -p 8000:8000 tool-chain-env
```

**Verify:**
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check — returns `{"status":"ok"}` |
| GET | `/tasks` | List all tasks with schemas |
| POST | `/reset_task?task_id=task1` | Start a new episode |
| POST | `/step_task?task_id=task1` | Submit one action |
| GET | `/state_task?task_id=task1` | Current episode state |
| POST | `/grader?task_id=task1` | Episode score (0.0–1.0) |
| POST | `/reset?task_id=task1` | Alias for reset_task |
| POST | `/step?task_id=task1` | Alias for step_task |
| GET | `/state?task_id=task1` | Alias for state_task |
| GET | `/action_schema` | JSON schema for ToolChainAction |
| GET | `/observation_schema` | JSON schema for ToolChainObservation |

**Swagger UI:** `http://localhost:8000/docs`

---

## Running the Baseline

```bash
export ENV_BASE_URL=http://localhost:8000
python -m baseline.run_baseline
```

**Expected output:**
```
Running ToolChain-Env baseline...

SCORE:task1:1.0000
SCORE:task2:1.0000
SCORE:task3:1.0000
SCORE:task4:1.0000

Average score: 1.0000
```

---

## Running Inference (LLM Agent)

```bash
export API_BASE_URL=https://api-inference.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
export HF_TOKEN=hf_your_token_here
export ENV_BASE_URL=http://localhost:8000

python inference.py
```

---

## Architecture

```
tool_chain_env/
├── app.py                          # FastAPI application entry point
├── models.py                       # Pydantic models (Action, Observation, State)
├── inference.py                    # LLM agent inference script
├── openenv.yaml                    # OpenEnv specification
├── Dockerfile                      # Container deployment
├── server/
│   ├── tool_chain_env_environment.py  # Core RL environment (reset/step/state)
│   ├── mock_api.py                    # Mock API server (auth, CRM, payments, webhooks)
│   └── grader.py                      # Episode grading (per-task scoring)
└── baseline/
    └── run_baseline.py                # Heuristic baseline agent
```

The mock API server runs **inside the same process** — no external services, no Docker-compose, no network latency. Episodes are deterministic and reproducible.

---

## License

BSD-style license. See LICENSE for details.