from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from typing import Optional

router = APIRouter(prefix="/api", tags=["mock-api"])

# ── Shared state (resets per episode via env.reset()) ─────────
_store: dict = {}

def reset_store(episode_data: dict):
    """Called by env.reset() to initialise episode-specific data."""
    _store.clear()
    _store.update(episode_data)

# ── Rate-limit counter ────────────────────────────────────────
_rate_limit_counter: dict = {"calls": 0, "window_start_step": 0}


# ══════════════════════════════════════════════════════════════
# Plain handler functions (callable directly, no Request needed)
# Return: (status_code, response_dict)
# ══════════════════════════════════════════════════════════════

def _auth_handler(body: dict, headers: dict) -> tuple:
    username = body.get("username", "")
    password = body.get("password", "")
    if username == _store.get("valid_user") and password == _store.get("valid_pass"):
        return 200, {"token": _store["token"], "expires_in": 3600}
    return 401, {"error": "Invalid credentials"}


def _get_user_handler(user_id: int, headers: dict) -> tuple:
    authorization = headers.get("authorization") or headers.get("Authorization")
    if not _valid_token(authorization):
        return 401, {"error": "Missing or invalid Bearer token"}
    user = _store.get("users", {}).get(str(user_id))
    if not user:
        return 404, {"error": f"User {user_id} not found"}
    return 200, user


def _get_order_handler(order_id: str, headers: dict) -> tuple:
    authorization = headers.get("authorization") or headers.get("Authorization")
    if not _valid_token(authorization):
        return 401, {"error": "Unauthorized"}
    order = _store.get("orders", {}).get(order_id)
    if not order:
        return 404, {"error": "Order not found"}
    return 200, order


def _refund_handler(body: dict, headers: dict) -> tuple:
    authorization = headers.get("authorization") or headers.get("Authorization")
    if not _valid_token(authorization):
        return 401, {"error": "Unauthorized"}
    idempotency_key = headers.get("Idempotency-Key") or headers.get("idempotency-key")
    order_id = body.get("order_id", "")
    order = _store.get("orders", {}).get(order_id, {})
    if not order.get("eligible_for_refund"):
        return 400, {"error": "Order not eligible for refund"}
    if not idempotency_key:
        _store["refund_missing_idempotency"] = True
    _store["refund_processed"] = True
    _store["refund_idempotency_key"] = idempotency_key
    return 200, {"success": True, "refund_id": f"REF-{order_id}", "amount": order.get("amount"), "status": "processing"}


def _graphql_handler(body: dict, headers: dict) -> tuple:
    authorization = headers.get("authorization") or headers.get("Authorization")
    if not _valid_token(authorization):
        return 401, {"error": "Unauthorized"}
    # Rate limit: max 3 calls per 5-step window
    current_step = _store.get("current_step", 0)
    if current_step - _rate_limit_counter["window_start_step"] >= 5:
        _rate_limit_counter["calls"] = 0
        _rate_limit_counter["window_start_step"] = current_step
    _rate_limit_counter["calls"] += 1
    if _rate_limit_counter["calls"] > 3:
        return 429, {"error": "Too Many Requests", "retry_after_steps": 5 - (current_step - _rate_limit_counter["window_start_step"])}

    query = body.get("query", "")
    cursor = body.get("variables", {}).get("cursor", None)

    all_logs = _store.get("system_logs", [])
    page_size = 5
    start = 0
    if cursor:
        for i, log in enumerate(all_logs):
            if log["id"] == cursor:
                start = i + 1
                break
    page = all_logs[start:start+page_size]
    next_cursor = page[-1]["id"] if len(page) == page_size and start+page_size < len(all_logs) else None
    _store.setdefault("collected_log_ids", set()).update(l["id"] for l in page)
    return 200, {
        "data": {"systemLogs": {"edges": page, "pageInfo": {"nextCursor": next_cursor, "hasNextPage": next_cursor is not None}}}
    }


# ══════════════════════════════════════════════════════════════
# FastAPI route wrappers (thin wrappers around the handlers)
# ══════════════════════════════════════════════════════════════

@router.post("/auth")
async def auth(request: Request):
    body = await request.json()
    headers = dict(request.headers)
    status, data = _auth_handler(body, headers)
    return JSONResponse(status_code=status, content=data)


@router.get("/crm/users/{user_id}")
async def get_user(user_id: int, request: Request):
    headers = dict(request.headers)
    status, data = _get_user_handler(user_id, headers)
    return JSONResponse(status_code=status, content=data)


@router.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    headers = dict(request.headers)
    status, data = _get_order_handler(order_id, headers)
    return JSONResponse(status_code=status, content=data)


@router.post("/payments/refund")
async def refund(request: Request):
    body = await request.json()
    headers = dict(request.headers)
    status, data = _refund_handler(body, headers)
    return JSONResponse(status_code=status, content=data)


@router.post("/graphql")
async def graphql(request: Request):
    body = await request.json()
    headers = dict(request.headers)
    status, data = _graphql_handler(body, headers)
    return JSONResponse(status_code=status, content=data)


# ── Helpers ───────────────────────────────────────────────────
def _valid_token(auth_header: Optional[str]) -> bool:
    if not auth_header:
        return False
    return auth_header == f"Bearer {_store.get('token', '')}"