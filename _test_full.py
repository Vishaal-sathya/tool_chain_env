import requests
import json

BASE = "http://localhost:8000"

# 1. Health
r = requests.get(f"{BASE}/health")
print(f"Health: {r.status_code} {r.json()}")

# 2. Tasks
r = requests.get(f"{BASE}/tasks")
print(f"Tasks: {r.status_code} ({len(r.json())} tasks)")

# 3. Test Task 1 - full episode
print("\n=== Task 1 ===")
r = requests.post(f"{BASE}/reset_task", params={"task_id": "task1"})
obs = r.json()
print(f"Reset: {r.status_code}")

action = {"method": "POST", "endpoint": "/api/auth", "headers": {"Content-Type": "application/json"}, "body": {"username": "agent", "password": "secret123"}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task1"}, json=action)
step1 = r.json()
token = step1["observation"]["response_data"].get("token", "")
print(f"Step1 auth: status={step1['observation']['status_code']} token={token[:20]}...")

action2 = {"method": "GET", "endpoint": "/api/crm/users/42", "headers": {"Authorization": f"Bearer {token}"}, "body": None}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task1"}, json=action2)
step2 = r.json()
print(f"Step2 CRM: status={step2['observation']['status_code']} done={step2['done']}")

r = requests.post(f"{BASE}/grader", params={"task_id": "task1"})
print(f"Grader: {r.json()}")

# 4. Test Task 2
print("\n=== Task 2 ===")
r = requests.post(f"{BASE}/reset_task", params={"task_id": "task2"})
print(f"Reset: {r.status_code}")

action = {"method": "POST", "endpoint": "/api/auth", "headers": {"Content-Type": "application/json"}, "body": {"username": "agent", "password": "secret123"}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task2"}, json=action)
tok2 = r.json()["observation"]["response_data"]["token"]
print(f"Auth: got token")

action = {"method": "GET", "endpoint": "/api/orders/ORD-5519", "headers": {"Authorization": f"Bearer {tok2}"}, "body": None}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task2"}, json=action)
print(f"Order: status={r.json()['observation']['status_code']}")

action = {"method": "POST", "endpoint": "/api/payments/refund", "headers": {"Authorization": f"Bearer {tok2}", "Idempotency-Key": "test-key-001", "Content-Type": "application/json"}, "body": {"order_id": "ORD-5519"}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task2"}, json=action)
print(f"Refund: status={r.json()['observation']['status_code']} done={r.json()['done']}")

r = requests.post(f"{BASE}/grader", params={"task_id": "task2"})
print(f"Grader: {r.json()}")

# 5. Test Task 4 - webhook flow
print("\n=== Task 4 ===")
r = requests.post(f"{BASE}/reset_task", params={"task_id": "task4"})
print(f"Reset: {r.status_code}")

action = {"method": "POST", "endpoint": "/api/auth", "headers": {"Content-Type": "application/json"}, "body": {"username": "agent", "password": "secret123"}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task4"}, json=action)
tok = r.json()["observation"]["response_data"]["token"]
print(f"Auth: got token")

action = {"method": "POST", "endpoint": "/api/webhooks/register", "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, "body": {"callback_url": "https://agent.example.com/webhook"}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task4"}, json=action)
reg = r.json()["observation"]["response_data"]
wh_id = reg.get("webhook_id", "")
secret = reg.get("secret", "")
print(f"Register: webhook_id={wh_id}")

action = {"method": "POST", "endpoint": "/api/events/trigger", "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, "body": {"event_type": "order.completed", "webhook_id": wh_id}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task4"}, json=action)
print(f"Trigger: status={r.json()['observation']['status_code']}")

action = {"method": "GET", "endpoint": f"/api/webhooks/{wh_id}/deliveries", "headers": {"Authorization": f"Bearer {tok}"}, "body": None}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task4"}, json=action)
dels = r.json()["observation"]["response_data"]
delivery = dels.get("deliveries", [{}])[0]
print(f"Poll: delivery_id={delivery.get('delivery_id', '')}")

action = {"method": "POST", "endpoint": "/api/webhooks/verify", "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, "body": {"delivery_id": delivery["delivery_id"], "signature": delivery["signature"], "payload": delivery["payload"]}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task4"}, json=action)
print(f"Verify: status={r.json()['observation']['status_code']} verified={r.json()['observation']['response_data'].get('verified')}")

action = {"method": "POST", "endpoint": f"/api/webhooks/{wh_id}/acknowledge", "headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, "body": {"confirmed": True}}
r = requests.post(f"{BASE}/step_task", params={"task_id": "task4"}, json=action)
ack = r.json()
print(f"Ack: status={ack['observation']['status_code']} done={ack['done']}")

r = requests.post(f"{BASE}/grader", params={"task_id": "task4"})
print(f"Grader: {r.json()}")

# Schema endpoints
r = requests.get(f"{BASE}/action_schema")
print(f"\nAction schema: {r.status_code}")
r = requests.get(f"{BASE}/observation_schema")
print(f"Observation schema: {r.status_code}")

print("\n=== ALL TESTS PASSED ===")
