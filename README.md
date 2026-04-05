---
title: ToolChain-Env
emoji: 🔗
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - rl
  - agents
  - tool-calling
---

# 🛠️ ToolChain-Env (Agentic API Sandbox)

A high-fidelity RL environment where AI agents interact with a mock internet of REST APIs. Built to evaluate and train tool-calling agents on complex sequence-driven tasks.

## 🏗️ Architecture
Agents navigate a multi-service ecosystem (Auth, CRM, Payments, Orders) by reading dynamic documentation and managing stateful interactions.

### 🛰️ Observation Space
| Property | Type | Description |
| :--- | :--- | :--- |
| **status_code** | `int` | Standard HTTP result (200, 429, etc.) |
| **response_data** | `dict` | JSON payload from the mock service |
| **api_docs** | `str` | Dynamic registry of available endpoints |
| **history** | `list` | Recent action-status log for context |

### ⚡ Action Space
Structured JSON containing `method`, `endpoint`, `headers`, and `body`.

## 🏆 Benchmark Tasks

| Task | Difficulty | Objective | Grader |
| :--- | :--- | :--- | :--- |
| **The Data Fetch** | Easy | Authenticate and fetch User Profile 42. | 1.0 if JSON matches Alice Smith. |
| **The Distributed Transaction** | Medium | Verify Order ORD-5519 and process a refund. | 1.0 if refund + idempotency key used. |
| **Rate Limit and Pagination** | Hard | Aggregate all logs across rate limits. | 1.0 if all 10 logs are aggregated. |

## Baseline Scores

These scores are produced by running `inference.py` with the default model.
All scores are deterministic and reproducible.

| Task | Difficulty | Baseline Score |
|------|------------|----------------|
| The Data Fetch | Easy | 0.50 |
| The Distributed Transaction | Medium | 0.30 |
| Rate Limit and Pagination | Hard | 0.10 |

To reproduce:
```bash
export API_BASE_URL=your_api_base_url
export MODEL_NAME=your_model_name
export HF_TOKEN=your_hf_token
python inference.py
```

## 🚀 Getting Started

### Run with Docker
```bash
docker build -t toolchain-env .
docker run -p 7860:7860 toolchain-env
```

### Run Baseline Inference
```bash
# Set your OpenAI / HF keys
export OPENAI_API_KEY="sk-..."
export API_BASE_URL="http://localhost:7860"
python inference.py
```

*Validated with OpenEnv v1.0.0*
