---
title: Context Handoff Protocol
emoji: 🔄
colorFrom: red
colorTo: orange
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI-powered living handoff briefs for engineering teams
---

# Context Handoff Protocol (CHP)

> Passive, always-on context briefs — powered by HuggingFace Inference API and sentence-transformers.

CHP reads signals from the tools your team uses every day and synthesises
them into a structured **living handoff brief** so no context is ever lost
when someone goes on leave or transfers work.

## Running on this Space

1. Click **Run** — the app starts automatically.
2. Select a demo user (Priya Nair or Alex Chen) in the sidebar.
3. Click **Ingest → Cluster → Generate Brief** to see the pipeline in action.

## Connecting real data sources

Add the following **Space Secrets** (Settings → Variables and Secrets):

| Secret | Description |
|---|---|
| `HF_TOKEN` | HuggingFace token for Inference API (required for LLM) |
| `SLACK_BOT_TOKEN` | Slack bot token (`xoxb-...`) |
| `GITHUB_TOKEN` | GitHub personal access token |

## Providers used in this Space

| Component | Provider | Model |
|---|---|---|
| Embeddings | sentence-transformers (local) | `all-MiniLM-L6-v2` |
| LLM | HuggingFace Inference API | `HuggingFaceH4/zephyr-7b-beta` |
| Database | SQLite | `/data/chp.db` |

## Tech stack

All free and open-source: FastAPI · SQLAlchemy · sentence-transformers ·
HDBSCAN · HuggingFace Hub · Python 3.11
