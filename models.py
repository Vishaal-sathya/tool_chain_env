from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, List


class ToolChainAction(BaseModel):
    """
    Represents one HTTP call the agent wants to make.
    WAIT is a no-op used for rate-limit backoff.
    """
    method: Literal["GET","POST","PUT","PATCH","DELETE","WAIT"] = Field(
        ..., description="HTTP method or WAIT for backoff"
    )
    endpoint: str = Field(
        default="", description="Target path e.g. /api/auth or /api/orders/ORD-001"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers including Authorization, Content-Type, Idempotency-Key"
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON body for POST/PUT/PATCH"
    )

class ToolChainObservation(BaseModel):
    """What the agent sees after each step."""
    status_code: int = Field(default=0, description="HTTP status: 200,201,400,401,404,429,500")
    response_data: Dict[str, Any] = Field(
        default_factory=dict, description="Parsed JSON response body"
    )
    simulated_latency_ms: float = Field(
        default=0.0, description="Simulated call latency — reward penalises high values"
    )
    task_description: str = Field(
        default="", description="Natural language goal for this episode"
    )
    api_docs: str = Field(
        default="", description="Available endpoints and their schemas"
    )
    step_budget_remaining: int = Field(default=0)
    rate_limit_reset_in: int = Field(
        default=0, description="Steps until rate limit resets (0 = not limited)"
    )
    episode_log: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of all calls made this episode"
    )


class State(BaseModel):
    """Minimal state object for the environment."""
    episode_id: str = ""
    step_count: int = 0