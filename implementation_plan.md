# Implementation Plan: ToolChain-Env Perfection

## Phase 1 — Stop the Bleeding (Immediate Fixes)
- Fix `inference.py` completely:
  - Update model, ports, and fix endpoints.
  - Implement the OpenAI client correctly with `base_url` and `api_key`.
  - Implement the precise loop and `[START]`, `[STEP]`, `[END]` prints.
- Fix `openenv.yaml`:
  - Update the app descriptor from `server.main:app` to `app:app`.
  - Fill in tasks, action space, observation space, and environment variables block.
- Fix `baseline/run_baseline.py`:
  - Change `json={"action": action}` to `json=action`.
  - Add `params={"task_id": task_id}` for the step endpoint.
- Align all task IDs in `app.py`:
  - Update defaults from `"data_fetch"` to `"task1"`.
- Verify HF Space is live:
  - Ensure the server runs properly on port 8000.

## Phase 2 — Spec Compliance
- Add route aliases in `app.py`:
  - Adhere to the strict OpenEnv schema (`/reset`, `/step`, `/state`, `/action_schema`, `/observation_schema`).
- Pydantic model schemas:
  - Add model introspection endpoints to help validators.
- Environment audit (`tool_chain_env_environment.py`):
  - Confirm `TASKS` uses the correct keys (`task1`, `task2`, `task3`).
  - Validate that `api_docs` in observations are sufficiently descriptive.

## Phase 3 — Gap-Opening Moves (Win by Distance)
- Rewrite `README.md`:
  - Overhaul the narrative to make a compelling argument why episodic RL for APIs matters.
- Implement Task 4 (Hard++) - Webhook Verification:
  - Design a complex workflow involving `POST /api/webhooks/register`, triggering events, polling, and HMAC signature verification.
- Procedurally generated IDs:
  - Finalize procedural generation and avoid state memorization.
- Rewrite `walkthrough.md`:
  - Treat it as a research narrative detailing design decisions.
- Add `output.txt`:
  - Create a definitive log of a scored run.
- Grader isolation:
  - Solidify the grader behavior across resets.

## Phase 4 — Polish and Submission
- Pre-validation script:
  - Run the validator strictly.
- Docker build test:
  - Test docker build and run inference against it locally.
- Time inference script:
  - Verify execution time constraints (`< 20 mins`).
- Deploy:
  - Push updates and monitor the HF Space.