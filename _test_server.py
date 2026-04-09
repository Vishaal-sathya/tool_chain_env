import httpx, json

base = "http://localhost:8000"

print("=" * 50)
print("Testing tool_chain_env server (Python 3.11 venv)")
print("=" * 50)

# 1) GET /health
r = httpx.get(f"{base}/health")
print(f"\n1. GET /health => {r.status_code} {r.json()}")
assert r.status_code == 200 and r.json() == {"status": "ok"}

# 2) GET /tasks
r = httpx.get(f"{base}/tasks")
tasks = r.json()
print(f"2. GET /tasks => {r.status_code}, {len(tasks)} tasks:")
for t in tasks:
    print(f"   - {t['id']} ({t['difficulty']}, max_steps={t['max_steps']})")
assert r.status_code == 200 and len(tasks) == 3

# 3) POST /reset_task
r = httpx.post(f"{base}/reset_task?task_id=data_fetch")
obs = r.json()
print(f"3. POST /reset_task => {r.status_code}")
print(f"   task: {obs['task_description'][:70]}...")
print(f"   budget: {obs['step_budget_remaining']} steps")
assert r.status_code == 200 and obs["step_budget_remaining"] == 8

# 4) GET /docs (Swagger UI)
r = httpx.get(f"{base}/docs")
print(f"4. GET /docs => {r.status_code} (Swagger UI {'loaded' if r.status_code == 200 else 'FAILED'})")
assert r.status_code == 200

print("\n" + "=" * 50)
print("ALL TESTS PASSED")
print("=" * 50)
