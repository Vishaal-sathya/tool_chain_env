from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse
from server.tool_chain_env_environment import ToolChainEnvironment, TASKS
from server.mock_api import router as mock_router
from server.grader import grade_episode
from models import ToolChainAction, ToolChainObservation
import subprocess, json

app = FastAPI(title="ToolChain-Env")

_envs: dict = {}

def _get_or_create(task_id: str) -> ToolChainEnvironment:
    if task_id not in _envs:
        _envs[task_id] = ToolChainEnvironment(task_id=task_id)
    return _envs[task_id]

app.include_router(mock_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
@app.get("/web")
def index():
    return RedirectResponse(url="/docs")

@app.get("/tasks")
def list_tasks():
    return JSONResponse(content=[
        {
            "id": tid,
            "difficulty": ["easy", "medium", "hard", "expert"][i] if i < 4 else "expert",
            "description": cfg["description"],
            "max_steps": cfg["max_steps"],
            "action_schema": ToolChainAction.model_json_schema(),
        }
        for i, (tid, cfg) in enumerate(TASKS.items())
    ])

@app.post("/reset_task")
def reset_task(task_id: str = Query("task1")):
    env = ToolChainEnvironment(task_id=task_id)
    _envs[task_id] = env
    obs = env.reset()
    return JSONResponse(content=obs.model_dump())

@app.post("/step_task")
def step_task(action: ToolChainAction, task_id: str = Query("task1")):
    env = _get_or_create(task_id)
    obs, reward, done, info = env.step(action)
    return JSONResponse(content={
        "observation": obs.model_dump(),
        "reward": reward,
        "done": done,
        "info": info
    })

@app.get("/state_task")
def state_task(task_id: str = Query("task1")):
    return JSONResponse(content=_get_or_create(task_id).state().model_dump())

@app.post("/grader")
def grader(task_id: str = Query("task1")):
    env = _get_or_create(task_id)
    score = grade_episode(env)
    return JSONResponse(content={"score": round(score, 4), "task_id": task_id})

@app.post("/baseline")
def baseline():
    result = subprocess.run(
        ["python", "-m", "baseline.run_baseline"],
        capture_output=True, text=True, timeout=300
    )
    scores = {}
    for line in result.stdout.splitlines():
        if line.startswith("SCORE:"):
            parts = line.split(":")
            scores[parts[1]] = float(parts[2])
    return JSONResponse(content={"scores": scores})

# OpenEnv spec aliases
@app.post("/reset")
def reset(task_id: str = Query("task1")):
    return reset_task(task_id=task_id)

@app.post("/step")
def step(action: ToolChainAction, task_id: str = Query("task1")):
    return step_task(action=action, task_id=task_id)

@app.get("/state")
def state(task_id: str = Query("task1")):
    return state_task(task_id=task_id)

@app.get("/action_schema")
def action_schema():
    return JSONResponse(content=ToolChainAction.model_json_schema())

@app.get("/observation_schema")
def observation_schema():
    return JSONResponse(content=ToolChainObservation.model_json_schema())

def main():
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()