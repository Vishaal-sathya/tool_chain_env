# ToolChain-Env: Design Decisions and Research Motivation

## Why API Orchestration Is Hard for LLMs

Large language models are increasingly deployed as autonomous agents that interact with external tools and APIs. Yet even state-of-the-art models fail systematically at multi-step API workflows. The failure modes are consistent and well-documented:

**Endpoint hallucination.** Models invent plausible-sounding API paths (`/api/get_user_profile`) instead of the actual endpoints specified in documentation (`/api/crm/users/{id}`). This happens because language models optimize for token-level fluency, not schema adherence.

**Token amnesia.** After receiving an authentication token from `/api/auth`, models frequently fail to include it in subsequent requests, or format it incorrectly (e.g., sending the raw token string instead of `Bearer <token>`). The context window contains the token, but the model fails to extract and reuse it as a structured header value.

**Idempotency blindness.** When processing financial transactions, models don't understand that retrying a POST request without an `Idempotency-Key` header can cause double-charging. This is a critical production safety concern — the difference between a 0.8 and 1.0 score in Task 2 maps directly to whether the agent would cause real monetary harm in deployment.

**Rate-limit ignorance.** Models typically respond to a 429 (Too Many Requests) response by immediately retrying the same request, triggering another 429. The correct behavior — waiting, then continuing — requires temporal reasoning that language models are not naturally trained to perform.

**Webhook confusion.** Event-driven architectures with webhooks, HMAC signature verification, and acknowledge/retry patterns are completely outside the model's training distribution for chat completion. Task 4 tests whether agents can learn this pattern through RL training signals alone.

---

## Why Episodic RL Structure Matters

Static benchmarks (ToolBench, APIBench, API-Bank) evaluate models on fixed input-output pairs. They answer the question: "Can this model produce the right API call given a prompt?" But they cannot answer: "Can this model learn to navigate a multi-step API workflow through trial and error?"

ToolChain-Env provides an episodic structure:
- **`reset()`** initializes a fresh episode with procedurally varied state
- **`step(action)`** returns `(observation, reward, done, info)` — the standard RL interface
- **`state()`** provides introspection into the current episode

This structure enables:
1. **Policy gradient training** — agents can learn from shaped reward signals over thousands of episodes
2. **Curriculum learning** — start with Task 1 (easy), progress to Task 4 (expert)
3. **Evaluation consistency** — graders produce deterministic scores from 0.0 to 1.0

No existing API evaluation framework provides this combination.

---

## How the Shaped Reward Function Guides Learning

A naive reward function would assign 0.0 for failure and 1.0 for success. This creates an extremely sparse signal that makes RL training impractical for multi-step tasks.

ToolChain-Env shapes the reward at every step:

**Positive signals:**
- +0.15 for any successful API call (200/201) — encourages the agent to make valid requests
- +0.20 for including an Idempotency-Key header on refund requests — teaches production safety
- +0.25 for correct HMAC signature verification — rewards cryptographic understanding
- +0.05 for using WAIT after receiving a 429 — teaches temporal reasoning

**Negative signals:**
- −0.10 for triggering rate limiting — penalizes impatient behavior
- −0.08 for auth errors — penalizes forgetting the token
- −0.05 for malformed requests — penalizes hallucinated endpoints
- −0.01 per step — encourages efficiency

**Terminal bonus:**
The grader score (0.0–1.0) is scaled by 0.5 and added as a terminal reward. This ensures the per-step shaped rewards and the final evaluation score are always aligned — an agent that scores well on shaped rewards will also score well on the grader.

---

## The Idempotency Checkpoint (Task 2): Why 0.8 vs 1.0 Matters

In production systems, a payment refund without an idempotency key is a ticking time bomb. If the network drops the response and the client retries, the payment gets processed twice. Real financial APIs (Stripe, PayPal, Square) all require idempotency keys for exactly this reason.

Task 2 deliberately scores agents who complete the refund without an idempotency key at 0.8 — not 0.0 or 0.5. The transaction succeeded, the order was correct, and the refund was processed. But the missing safety header means the agent would be dangerous in production. The 0.8 → 1.0 gap is the difference between "functionally correct" and "production-safe."

This scoring design teaches a nuanced lesson: correctness alone is insufficient. Agents must learn defensive programming patterns to achieve maximum scores.

---

## Rate Limiting as a Planning Problem (Task 3)

Most API errors (400, 401, 404) can be fixed by modifying the request. Rate limiting (429) cannot — the only valid response is to wait. This introduces a fundamentally different kind of reasoning:

The agent must:
1. Recognize that 429 means "you made too many requests"
2. Use the `WAIT` action to let the rate limit window expire
3. Resume pagination from where it left off (not restart from the beginning)
4. Continue this pattern until all pages are collected

The `WAIT` action is the only action in the environment that is not an HTTP method. It is a meta-action that models temporal planning. The environment rewards correct WAIT usage (+0.05) and penalizes unnecessary WAIT (−0.05), teaching the agent to wait only when rate-limited.

This transforms what appears to be a simple data collection task into a planning problem: the agent must interleave API calls and wait periods to collect all 18 log entries within 30 steps, respecting a limit of 3 calls per 5-step window.

---

## Webhook Verification: Event-Driven Architecture as RL Training (Task 4)

Task 4 is the most conceptually sophisticated task in the environment. The agent must:

1. **Register** a webhook callback URL
2. **Trigger** an event that fires the webhook
3. **Poll** for delivery notifications
4. **Verify** the HMAC-SHA256 signature of the payload
5. **Acknowledge** receipt to confirm the delivery lifecycle

This 6-step workflow mirrors real-world webhook implementations (GitHub, Stripe, Shopify). The cryptographic verification step is especially challenging: the agent must read the `signature` field from the delivery response and pass it back to the verify endpoint — a pattern that requires precise data extraction and reuse across steps.

The grader provides 6 graduated checkpoints (0.0, 0.2, 0.4, 0.6, 0.8, 1.0), giving the RL optimizer a rich signal to learn from.

---

## Procedural ID Generation: Preventing Episode Memorization

Every episode generates fresh UUIDs for tokens, episode IDs, and (in future iterations) user IDs and order IDs. This prevents agents from memorizing specific state sequences.

A model that has memorized "the token is always `tok_abc123`" will fail when it encounters `tok_7f2e9a3b1c4d`. The agent must learn the *pattern* (authenticate → extract token → include in headers) rather than memorizing specific values.

This is critical for RL training: without procedural variation, the policy would overfit to the training distribution and fail to generalize.

---

## Environment Architecture

The mock API server runs inside the same process as the RL environment. Each `reset()` call:
1. Generates fresh episode data (tokens, IDs)
2. Deep-copies it into the mock API store
3. Resets rate limiter counters
4. Returns the initial observation

The `step()` function routes actions directly to Python handler functions (no HTTP round-trip during training), making episodes extremely fast — a full 30-step episode completes in under 50ms.

For external evaluation, the same handlers are also exposed as FastAPI routes at `/api/*`, so the environment can be deployed as a standard web service and queried via HTTP.

---

## Conclusion

ToolChain-Env provides a structured, episodic, reward-shaped training environment for the specific skills that LLM agents need to operate reliably in production API ecosystems. Each task targets a distinct failure mode, and the graduated scoring ensures that partial progress is always rewarded. The environment is lightweight (single-process, no external dependencies), deterministic (reproducible episodes with procedural variation), and extensible (new tasks can be added by defining a new entry in `TASKS` and a corresponding grader function).
