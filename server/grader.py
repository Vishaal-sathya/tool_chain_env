from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .tool_chain_env_environment import ToolChainEnvironment
from . import mock_api

def grade_episode(env: "ToolChainEnvironment") -> float:
    task = env.task_id
    log  = env._log
    store = mock_api._store

    raw_score = 0.01
    if task == "task1":
        raw_score = _grade_data_fetch(log, store, env._episode_data)
    elif task == "task2":
        raw_score = _grade_transaction(log, store)
    elif task == "task3":
        raw_score = _grade_graphql(log, store, env._episode_data)
    elif task == "task4":
        raw_score = _grade_webhook(log, store)
    
    return max(0.01, min(0.99, float(raw_score)))

def _grade_data_fetch(log, store, episode_data) -> float:
    """
    0.0 — never authenticated
    0.3 — got token but never called CRM
    0.5 — called CRM but got 400/404 (wrong user_id or forgot token)
    1.0 — got correct user profile (status 200 + email in response)
    """
    got_token = any(e["status_code"] in (200,201) and "auth" in e["endpoint"] for e in log)
    if not got_token:
        return 0.0
    crm_calls = [e for e in log if "crm/users" in e["endpoint"]]
    if not crm_calls:
        return 0.3
    success_crm = [e for e in crm_calls if e["status_code"] == 200]
    if not success_crm:
        return 0.5
    # Check they retrieved the correct user
    target_id = str(episode_data.get("target_user_id", 42))
    correct = any(target_id in e["endpoint"] for e in success_crm)
    return 1.0 if correct else 0.7

def _grade_transaction(log, store) -> float:
    """
    0.0 — nothing or crash
    0.3 — got order data but never attempted refund
    0.8 — refund processed but no Idempotency-Key header
    1.0 — refund processed with Idempotency-Key
    """
    got_order = any("orders" in e["endpoint"] and e["status_code"] == 200 for e in log)
    if not got_order:
        return 0.0
    refund_attempted = any("payments/refund" in e["endpoint"] for e in log)
    if not refund_attempted:
        return 0.3
    refund_ok = store.get("refund_processed", False)
    if not refund_ok:
        return 0.3
    had_idempotency = not store.get("refund_missing_idempotency", False)
    return 1.0 if had_idempotency else 0.8

def _grade_graphql(log, store, episode_data) -> float:
    """
    0.0 — spammed, got blocked, never paginated
    0.4 — used WAIT correctly but stopped paginating early
    0.7 — paginated but missed final page
    1.0 — collected all log entries
    """
    total_logs = len(episode_data.get("system_logs", []))
    collected  = len(store.get("collected_log_ids", set()))

    used_wait = any(e["method"] == "WAIT" for e in log)
    got_429   = any(e["status_code"] == 429 for e in log)

    if collected == 0:
        return 0.0
    if collected < total_logs * 0.4:
        # Some collection but poor rate-limit handling
        return 0.2 if (got_429 and not used_wait) else 0.25
    if collected < total_logs * 0.8:
        return 0.4 if used_wait else 0.3
    if collected < total_logs:
        return 0.7
    return 1.0


def _grade_webhook(log, store) -> float:
    """
    0.0 — nothing or crash
    0.2 — authenticated but never registered webhook
    0.4 — registered webhook but never triggered event
    0.6 — triggered event and polled deliveries
    0.8 — verified HMAC signature
    1.0 — acknowledged webhook delivery (full lifecycle)
    """
    got_auth = any(
        e["status_code"] in (200, 201) and "auth" in e["endpoint"]
        for e in log
    )
    if not got_auth:
        return 0.0

    registered = store.get("webhook_registered", False)
    if not registered:
        return 0.2

    triggered = store.get("event_triggered", False)
    if not triggered:
        return 0.4

    polled = store.get("deliveries_polled", False)
    if not polled:
        return 0.5

    verified = store.get("signature_verified", False)
    if not verified:
        return 0.6

    acknowledged = store.get("webhook_acknowledged", False)
    if not acknowledged:
        return 0.8

    return 1.0