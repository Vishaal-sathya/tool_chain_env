# ToolChain-Env: An RL Environment for Real-World API Orchestration

Training agents to reliably use external APIs is one of the most significant challenges in agentic AI. While existing benchmarks evaluate agents on static datasets, they lack the episodic, feedback-driven structure necessary for reinforcement learning. **ToolChain-Env** bridges this gap by providing a fully episodic RL environment designed around the real-world API challenges that production systems face, including complex authentication, idempotent transactions, rate-limited pagination, and webhook-driven events.

Built for the **Meta × HuggingFace OpenENV Hackathon**.

---

## Why This Environment Matters

Today's LLM agents often fail in multi-step API workflows because they:
- **Hallucinate** non-existent endpoints.
- **Forget** authentication tokens between steps.
- **Fail to grasp idempotency**, leading to errors like double-charging.
- **Cannot handle rate limits**, spamming endpoints until they are blocked.
- **Lack a concept of webhooks**, making them incompatible with event-driven architectures.

These are not edge cases; they are the primary failure modes that prevent LLM agents from being deployed in production. ToolChain-Env is the first RL environment that allows agents to learn and overcome these challenges through shaped reward signals and an episodic training structure.

ToolChain-Env is the first RL environment where the reward signal is derived entirely from real-world software engineering correctness criteria—not human preferences or proxy metrics. The idempotency reward cliff at 0.8/1.0 is not arbitrary: it encodes the exact production failure mode (double-charge due to a missing deduplication key) that costs payment companies millions annually.

We provide a `train_with_trl.py` script demonstrating GRPO fine-tuning of a language model directly against ToolChain-Env's episode reward signal—showing that environments built on sound engineering principles can serve as the reward model for the next generation of tool-use agents.

---

## Comparison to Prior Work

| Environment | Episodic | Shaped Reward | Auth Flow | Idempotency | Rate Limits | Webhooks |
|---|---|---|---|---|---|---|
| ToolBench | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| APIBench | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| WebArena | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **ToolChain-Env** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Task Overview

| Task | Difficulty | Max Steps | Key Skill |
|---|---|---|---|
| **Task 1 — The Data Fetch** | Easy | 8 | Bearer token auth → CRM data retrieval |
| **Task 2 — The Distributed Transaction** | Medium | 12 | Idempotency-key protected payment refund |
| **Task 3 — Rate-Limit Evasion & Pagination** | Hard | 30 | GraphQL cursor pagination under rate limits |
| **Task 4 — Webhook Verification** | Expert | 15 | HMAC-SHA256 signature verification + event lifecycle |
| **Task 5 — The Dark API** | Expert | 20 | Undocumented API discovery and OAuth2 PKCE |

---

## Action Space

Every action is a JSON object with four fields:

| Field | Type | Description |
|---|---|---|
| `method` | `string` | One of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `WAIT` |
| `endpoint` | `string` | Target path, e.g., `/api/auth` or `/api/orders/ORD-AA1234` |
| `headers` | `dict` | Key-value pairs for headers like Authorization, Content-Type, etc. |
| `body` | `dict` or `null` | JSON payload for POST/PUT/PATCH requests |

`WAIT` is a special no-op action for handling rate limiting. The agent is rewarded for using `WAIT` correctly after a 429 response.

> **Per-episode randomization:** On every `reset()`, Task 1 assigns a random user ID (1–999) and Task 2 assigns a random order ID (`ORD-XX####`). These IDs are embedded in the `task_description` and `api_docs` of the observation, requiring the agent to parse them dynamically rather than hardcoding values. This prevents memorization and encourages generalization.

**Example action** (order ID is episode-specific):
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
    "order_id": "ORD-KP7821"
  }
}
```

> ⚠️ The `order_id` above is an example. The actual ID is provided in the `task_description` and `api_docs` of the observation.

---

## Observation Space

After each step, the agent receives:

| Field | Type | Description |
|---|---|---|
| `status_code` | `int` | HTTP status (e.g., 200, 404, 429) |
| `response_data` | `dict` | Parsed JSON response body |
| `simulated_latency_ms` | `float` | Environment-injected latency |
| `task_description` | `string` | Natural language goal for the episode |
| `api_docs` | `string` | Available endpoints and schemas |
| `step_budget_remaining` | `int` | Steps left before episode termination |
| `rate_limit_reset_in` | `int` | Steps to wait before rate limit reset |
| `episode_log` | `list` | The last 5 actions and their outcomes |

---

## Task Details

### Task 1 — The Data Fetch `[easy]`
Authenticate, obtain a Bearer token, and retrieve a specific user profile.

| Score | Condition |
|---|---|
| 1.0 | Retrieved the correct user profile successfully |
| 0.7 | Retrieved a user profile but for the wrong user ID |
| 0.5 | Called CRM but received 400/404 |
| 0.3 | Obtained token but never called the CRM endpoint |
| 0.0 | Failed to authenticate |

### Task 2 — The Distributed Transaction `[medium]`
Authenticate, retrieve an order, and process a refund with an `Idempotency-Key`.

| Score | Condition |
|---|---|
| 1.0 | Refund processed with correct Idempotency-Key |
| 0.8 | Refund processed but Idempotency-Key was missing |
| 0.3 | Retrieved order data but never attempted refund |
| 0.0 | Did nothing meaningful |

The 0.8 → 1.0 gap teaches a critical concept in distributed systems: ensuring safety with idempotency.

### Task 3 — Rate-Limit Evasion & GraphQL Pagination `[hard]`
Extract all logs from a GraphQL endpoint with strict rate limiting and cursor-based pagination.

| Score | Condition |
|---|---|
| 1.0 | Collected every log entry |
| 0.7 | Paginated most pages but missed the final one |
| 0.4 | Used WAIT correctly but stopped paginating early |
| 0.2–0.3 | Collected some logs but handled rate-limiting poorly |
| 0.0 | Spammed the endpoint and collected nothing |

### Task 4 — Webhook Verification `[expert]`
Register a webhook, trigger an event, poll for delivery, verify the HMAC-SHA256 signature, and acknowledge receipt.

| Score | Condition |
|---|---|
| 1.0 | Completed full webhook lifecycle with acknowledgement |
| 0.8 | Verified HMAC-SHA256 signature correctly |
| 0.6 | Triggered event and polled deliveries |
| 0.4 | Registered webhook but never triggered the event |
| 0.2 | Authenticated but never registered the webhook |
| 0.0 | Failed to authenticate |

### Task 5 — The Dark API `[expert]`
No API docs are provided. The agent must discover endpoints, deduce an OAuth2 PKCE authentication flow, and access a hidden admin export. This task is designed to challenge even frontier models.

---

## Reward Function

Reward is shaped at every step to provide continuous feedback.

| Signal | Reward |
|---|---|
| Successful API call (200/201) | +0.15 |
| Correct Idempotency-Key on refund | +0.20 |
| HMAC signature verified | +0.25 |
| Webhook acknowledged | +0.15 |
| `WAIT` used correctly after 429 | +0.05 |
| Rate limited (429) | −0.10 |
| Auth error (401) | −0.08 |
| Malformed request (400/404) | −0.05 |
| `WAIT` used unnecessarily | −0.05 |
| Time step cost (every step) | −0.01 |
| Terminal bonus | `grade_score × 0.5` |

The terminal bonus scales with the final grade, ensuring that step-level rewards and the overall objective are aligned.

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
|---|---|---|
| GET | `/health` | Health check |
| GET | `/tasks` | List all tasks |
| POST | `/reset_task` | Start a new episode |
| POST | `/step_task` | Submit an action |
| GET | `/state_task` | Get current episode state |
| POST | `/grader` | Get episode score (0.0–1.0) |
| GET | `/action_schema` | Get the action schema |
| GET | `/observation_schema` | Get the observation schema |

**Swagger UI:** `http://localhost:8000/docs`

---

## Running the Baseline

```bash
export ENV_BASE_URL=http://localhost:8000
python -m tool_chain_env.baseline.run_baseline
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
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
export HF_TOKEN=hf_your_token_here
export ENV_BASE_URL=http://localhost:8000

python inference.py
```

The script emits logs in the required structured format:
```
[START] task=task1 env=tool_chain_env model=meta-llama/Llama-3.3-70B-Instruct
[STEP] step=1 action={...} reward=0.14 done=false error=null
[STEP] step=2 action={...} reward=0.14 done=true error=null
[END] success=true steps=2 score=1.00 rewards=0.14,0.14
```

---

## Architecture

The environment is designed with a clean, 4-layer separation:

```
tool_chain_env/
├── app.py                          # FastAPI application
├── models.py                       # Pydantic models
├── inference.py                    # LLM agent inference script
├── openenv.yaml                    # OpenEnv specification
├── server/
│   ├── tool_chain_env_environment.py  # Core RL environment
│   ├── mock_api.py                    # Mock API server
│   └── grader.py                      # Episode grading logic
└── baseline/
    └── run_baseline.py                # Heuristic baseline agent
```

The mock API runs in the same process, ensuring deterministic and reproducible episodes with no network latency.

---

## License

This project is licensed under the BSD 3-Clause License. See the `LICENSE` file for details.
