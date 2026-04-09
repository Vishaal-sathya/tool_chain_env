import gymnasium as gym
from gymnasium import spaces

from models import ToolChainAction
from server.tool_chain_env_environment import ToolChainEnvironment


class ToolChainGymEnv(gym.Env):
    """Gymnasium wrapper around ToolChainEnvironment for RL library integration."""

    metadata = {"render_modes": []}

    def __init__(self, task_id: str = "task1"):
        super().__init__()
        self.task_id = task_id
        self._env = ToolChainEnvironment(task_id=task_id)

        self.action_space = spaces.Dict(
            {
                "method": spaces.Text(max_length=8),
                "endpoint": spaces.Text(max_length=256),
                "headers": spaces.Text(max_length=4096),
                "body": spaces.Text(max_length=4096),
            }
        )
        self.observation_space = spaces.Dict(
            {
                "status_code": spaces.Box(low=0, high=599, shape=(), dtype=int),
                "response_data": spaces.Text(max_length=20000),
                "simulated_latency_ms": spaces.Box(low=0.0, high=5000.0, shape=(), dtype=float),
                "task_description": spaces.Text(max_length=4096),
                "api_docs": spaces.Text(max_length=20000),
                "step_budget_remaining": spaces.Box(low=0, high=1000, shape=(), dtype=int),
                "rate_limit_reset_in": spaces.Box(low=0, high=100, shape=(), dtype=int),
                "episode_log": spaces.Text(max_length=20000),
            }
        )

    def reset(self, *, seed=None, options=None):
        obs = self._env.reset(seed=seed)
        return obs.model_dump(), {}

    def step(self, action):
        action_model = ToolChainAction(**action)
        obs, reward, done, info = self._env.step(action_model)
        return obs.model_dump(), float(reward), bool(done), False, info
