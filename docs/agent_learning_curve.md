# Agent Learning Curve

This document outlines the expected learning progression for agents trained on ToolChain-Env, from a random baseline to a sophisticated RL-trained agent.

## Agent Performance Tiers

### 1. Random Agent

A random agent, which selects actions and parameters randomly, is expected to have a score of **0.0** on all tasks. It will fail to perform any meaningful actions, such as authenticating or making valid API requests.

### 2. Heuristic Agent

The heuristic agent, implemented in `baseline/run_baseline.py`, follows a set of hardcoded rules to solve each task. It represents a strong baseline and is expected to achieve the following scores:

| Task | Expected Score |
|---|---|
| Task 1 | 1.0 |
| Task 2 | 1.0 |
| Task 3 | ~0.9 |
| Task 4 | ~0.9 |
| Task 5 | ~0.5 |

### 3. LLM Agent (Zero-Shot)

A large language model (LLM) agent, such as one based on GPT-4 or Llama 3, is given the task description and API documentation and must generate the correct sequence of actions. The expected scores for a zero-shot LLM agent are:

| Task | Expected Score |
|---|---|
| Task 1 | 1.0 |
| Task 2 | 0.8 - 1.0 |
| Task 3 | 0.6 - 0.8 |
| Task 4 | 0.4 - 0.6 |
| Task 5 | 0.0 - 0.2 |

The performance on Task 5 is expected to be low, as it requires exploration and discovery of hidden information, which is a significant challenge for most current models.

### 4. Trained RL Agent (PPO/GRPO)

An RL agent trained using an algorithm like PPO (Proximal Policy Optimization) or GRPO (Group Relative Policy Optimization) is expected to learn from the environment's reward signals and improve its performance over time. The projected scores for a fully trained RL agent are:

| Task | Expected Score |
|---|---|
| Task 1 | 1.0 |
| Task 2 | 1.0 |
| Task 3 | 1.0 |
| Task 4 | 1.0 |
| Task 5 | 0.8 - 1.0 |

The trained agent is expected to master all tasks, including the challenging "Dark API" task, by learning effective exploration and problem-solving strategies. The reward curve below illustrates the projected improvement in performance during training.

![Reward Curve](https---)
*(Placeholder for the reward curve image to be added after training)*
