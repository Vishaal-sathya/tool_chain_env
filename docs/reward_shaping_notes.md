# Reward Shaping Notes

This document outlines the reward structure for the `tool_chain_env`.

## General Principles

- **Terminal Reward**: The environment provides a sparse, terminal reward. This means a score is only given at the very end of an episode.
- **Score Range**: The score is always between 0.0 (total failure) and 1.0 (perfect success).
- **No Partial Credit (Mostly)**: For most tasks, credit is all-or-nothing. You either successfully complete the objective or you don't.
- **Task 1 Exception**: Task 1 (Data Fetch) provides partial credit. Fetching data for the *wrong* user still yields a small score, encouraging the agent to learn the data fetching part of the task.

## Task-Specific Rewards

- **Task 1 (Data Fetch)**:
  - `1.0`: Fetching the correct user's data.
  - `0.1`: Fetching any user's data that is not the correct user.
  - `0.0`: Failure to fetch any data.

- **Task 2 (Transaction)**:
  - `1.0`: Successfully executing the specific transaction with the correct idempotency key.
  - `0.0`: Any other outcome, including failed transactions or re-using an idempotency key.

- **Task 3 (GraphQL)**:
  - `1.0`: Successfully retrieving all pages from the paginated GraphQL endpoint.
  - `0.0`: Failure to retrieve all pages.

- **Task 4 (Rate Limiting)**:
  - `1.0`: Successfully navigating the rate-limited API by respecting `Retry-After` headers.
  - `0.0`: Any other outcome.

- **Task 5 (Dark API)**:
  - `1.0`: Successfully discovering and using the hidden admin endpoint to export data, following the full PKCE OAuth2 flow.
  - `0.0`: Any other outcome.
