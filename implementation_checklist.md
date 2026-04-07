# ToolChain-Env — Implementation Progress Tracker

## Phase 1 — Stop the Bleeding (Disqualifiers)
- [x] Fix `inference.py` — correct port, endpoints, OpenAI client, env vars.
- [x] Fix `openenv.yaml` — `app: app:app`, port 8000, full spec.
- [x] Fix `baseline/run_baseline.py` — `json=action` (not wrapped), add `task_id` query param.
- [x] Align all task IDs — environment uses `task1`/`task2`/`task3`/`task4` everywhere.
- [x] Fix `Dockerfile` — port 8000, `app:app`, install `requests`.
- [x] Verify server starts — `/health` returns 200.

## Phase 2 — Spec Compliance (Interface Score)
- [x] Add `/reset`, `/step`, `/state` route aliases in `app.py`.
- [x] Add `/action_schema`, `/observation_schema` endpoints in `app.py`.
- [x] Beef up `api_docs` — make them LLM-solvable with exact signatures.
- [x] Fix `run_baseline.py` credentials & logic — match actual env creds.
- [x] Fix lingering `rate_limit_graphql` reference in `_is_terminal()`.

## Phase 3 — Gap-Opening Moves (Win by Distance)
- [x] Implement Task 4 — Webhook Verification + HMAC (`mock_api` + environment + grader).
- [x] Update `openenv.yaml` with `task4`.
- [x] Update `inference.py` with `task4`.
- [x] Update `run_baseline.py` with `task4` heuristic.
- [x] Rewrite `README.md` — compelling research narrative.
- [x] Rewrite `walkthrough.md` — research-grade design document.
- [x] Create proper `output.txt` — shows scored run proof.
- [x] Grader isolation — ensure `grade_episode` captures state correctly.

## Phase 4 — Polish and Submission
- [x] Verify server starts and all endpoints work.
- [x] Update `README.md` API reference with correct task IDs.
- [x] Final review of all files.

## Notes
- Items are marked complete only when the current workspace state shows the feature already implemented and/or has been verified locally.