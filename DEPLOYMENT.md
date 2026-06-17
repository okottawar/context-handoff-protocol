# CHP — Deployment Guide

## Contents

- [Part 1 — Local Deployment](#part-1--local-deployment)
  - [Prerequisites](#prerequisites)
  - [Step-by-step setup](#step-by-step-setup)
  - [Choosing your LLM backend](#choosing-your-llm-backend)
  - [Connecting real data sources](#connecting-real-data-sources)
  - [Swapping providers at runtime](#swapping-providers-at-runtime)
  - [Troubleshooting](#troubleshooting)
- [Part 2 — HuggingFace Spaces Deployment](#part-2--huggingface-spaces-deployment)
  - [Architecture decisions](#architecture-decisions)
  - [File checklist](#file-checklist)
  - [Step-by-step deployment](#step-by-step-deployment)
  - [Setting secrets](#setting-secrets)
  - [Persistent storage](#persistent-storage)
  - [Choosing the LLM model](#choosing-the-lm-model)
  - [Updating the Space](#updating-the-space)
  - [Limitations and mitigations](#limitations-and-mitigations)
- [Part 3 — Provider matrix](#part-3--provider-matrix)

---

# Part 1 — Local Deployment

## Prerequisites

| Tool | Version | Why | Install |
|------|---------|-----|---------|
| Python | 3.11+ | Runtime | [python.org](https://python.org) |
| pip | 23+ | Package manager | bundled with Python |
| Ollama | latest | Local LLM inference | [ollama.com](https://ollama.com) |
| git | any | Cloning (optional) | [git-scm.com](https://git-scm.com) |

Ollama is **only required if you use the default Ollama LLM provider**.
You can skip it and use `hf_inference` instead (see [Choosing your LLM backend](#choosing-your-llm-backend)).

---

## Step-by-step setup

### 1. Unzip the project

```bash
unzip chp.zip
cd chp
```

### 2. Copy and review the config

```bash
cp .env.example .env
```

Open `.env` in any editor. The defaults work out of the box for a
local Ollama setup. Minimum changes needed:

```env
# If you have Ollama installed and running — no changes needed.

# If you prefer HuggingFace Inference API (no Ollama required):
LLM_PROVIDER=hf_inference
HF_TOKEN=hf_your_token_here
HF_LLM_MODEL=HuggingFaceH4/zephyr-7b-beta
```

### 3. Install Ollama and pull a model (skip if using hf_inference)

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows — download the installer from https://ollama.com/download

# Start Ollama (it runs as a background service)
ollama serve &

# Pull the default model (2 GB download, one-time)
ollama pull llama3.2

# Verify
ollama list
```

### 4. Run CHP

```bash
chmod +x run.sh
./run.sh
```

`run.sh` will:
- Create a Python virtual environment in `.venv/`
- Install all dependencies (first run: ~3–5 min)
- Auto-download the `all-MiniLM-L6-v2` embedding model (~90 MB, one-time)
- Start the FastAPI server at **http://localhost:8000**

### 5. Use the app

1. Open **http://localhost:8000**
2. Click **Priya Nair** in the sidebar
3. Click **Ingest** — pulls 16 pre-seeded mock events
4. Click **Cluster** — HDBSCAN groups them into work threads
5. Click **Generate Brief** — your LLM writes the handoff narrative
6. Click any thread card to see its raw signals

---

## Choosing your LLM backend

### Option A — Ollama (default, fully offline)

Best if: you want everything to run locally with no external calls.

```bash
# Install Ollama, then pick a model based on your RAM:

# 8 GB RAM
ollama pull llama3.2          # 2B params, fastest
ollama pull phi3              # Microsoft Phi-3, excellent quality for size

# 16 GB RAM
ollama pull llama3.1:8b       # best balance of speed and quality
ollama pull mistral           # Mistral 7B, very capable

# 32 GB+ RAM
ollama pull llama3.1:70b      # near-GPT-4 quality
ollama pull mixtral           # Mixtral 8x7B MoE
```

Set in `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_LLM_MODEL=llama3.2         # or whichever you pulled
OLLAMA_BASE_URL=http://localhost:11434
```

### Option B — HuggingFace Inference API (no local GPU needed)

Best if: your machine has limited RAM or you want a quick no-install setup.

1. Create a free account at https://huggingface.co
2. Go to https://huggingface.co/settings/tokens → New token → Read
3. Copy the token

```env
LLM_PROVIDER=hf_inference
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
HF_LLM_MODEL=HuggingFaceH4/zephyr-7b-beta
```

Free tier limits: ~1,000 requests/day per model. Plenty for development.

### Option C — LM Studio / LocalAI / vLLM (OpenAI-compatible)

Best if: you already have LM Studio or another local inference server.

```env
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=http://localhost:1234/v1
OPENAI_COMPAT_API_KEY=not-needed
OPENAI_COMPAT_MODEL=lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF
```

---

## Connecting real data sources

### Slack

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name: `CHP Bot` — pick your workspace
3. **OAuth & Permissions** → Bot Token Scopes — add all of these:

   ```
   channels:history    channels:read
   groups:history      groups:read
   im:history          mpim:history
   users:read
   ```

4. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
5. Invite the bot to any channels it should read:
   `/invite @CHP Bot`

```env
SLACK_BOT_TOKEN=xoxb-your-token-here
```

> The user_id passed to the connector should be the Slack user's **email** or
> **Slack UID** (e.g. `U012AB3CD`). The connector auto-resolves emails to UIDs.

### GitHub

1. Go to https://github.com/settings/tokens → **Generate new token (classic)**
2. Scopes needed: `repo` (or `public_repo` for public repos only)
3. Copy the token

```env
GITHUB_TOKEN=ghp_your_token_here
```

> The user_id passed to the GitHub connector must be the GitHub **username**
> (e.g. `priya-nair`), not email.

---

## Swapping providers at runtime

All provider swaps are `.env` only — restart the server after changing.

```bash
# Edit .env, then:
uvicorn backend.main:app --reload --port 8000
# or just:
./run.sh
```

The `registry.py` file is the single place to add new providers.
See the comments inside it for a 3-step guide.

---

## Troubleshooting

### `Ollama not running` warning at startup

```bash
ollama serve          # start in a separate terminal
```

CHP starts anyway and uses the rule-based fallback brief until Ollama is up.

### Slow first startup

The `all-MiniLM-L6-v2` embedding model downloads on first run (~90 MB).
This is a one-time operation; subsequent starts are instant.
To pre-download manually:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### `No threads found` after ingest

The mock connector seeds 16 events for `priya` and 5 for `alex`.
HDBSCAN requires `HDBSCAN_MIN_CLUSTER_SIZE` events to form a cluster (default: 2).
If you see 0 threads, try lowering the setting:

```env
HDBSCAN_MIN_CLUSTER_SIZE=2
```

### Port 8000 already in use

```bash
# Change the port
PORT=8080 uvicorn backend.main:app --port 8080
```

Or set `PORT=8080` in `.env`.

### `aiosqlite` / `greenlet` errors

```bash
pip install --upgrade aiosqlite greenlet
```

---

# Part 2 — HuggingFace Spaces Deployment

## Architecture decisions

HF Spaces free tier has constraints that require a few adjustments from
the local setup:

| Constraint | Local workaround | HF Spaces solution |
|---|---|---|
| No Ollama daemon | Ollama runs locally | HF Inference API (`hf_inference` provider) |
| No GPU (free tier) | Local GPU | CPU-only torch + small embedding model |
| Limited RAM (16 GB) | Any RAM | `all-MiniLM-L6-v2` (22 MB), keeps headroom |
| Port must be 7860 | Any port | `PORT=7860` in Dockerfile ENV |
| Non-root user required | Run as any user | `USER chpuser` in Dockerfile |
| Storage is ephemeral | Local SSD | `/data` mount (add Persistent Storage for £5/mo) |

The full pipeline still runs identically. Only the LLM provider changes.

```
Local:         ST embeddings  +  Ollama LLM       (fully offline)
HF Spaces:     ST embeddings  +  HF Inference API (free, cloud LLM)
```

---

## File checklist

Before deploying, ensure your project has these files at the root level:

```
chp/
├── Dockerfile              ← HF Spaces reads this automatically
├── README_SPACES.md        ← rename to README.md before pushing
├── requirements.hfspaces.txt
├── .env.hfspaces           ← values go into Space Secrets, not committed
├── backend/                ← unchanged from local
└── frontend/               ← unchanged from local
```

**Critical**: HF Spaces looks for `README.md` (not `README_SPACES.md`).
Rename it before pushing:

```bash
mv README_SPACES.md README.md
```

---

## Step-by-step deployment

### Step 1 — Create a HuggingFace account

Go to https://huggingface.co/join and create a free account.

### Step 2 — Create a new Space

1. Go to https://huggingface.co/new-space
2. Fill in the form:

   | Field | Value |
   |---|---|
   | Space name | `context-handoff-protocol` (or any name) |
   | License | `MIT` |
   | **SDK** | **Docker** ← important |
   | Visibility | Public (free) or Private (Pro plan) |

3. Click **Create Space** — HF creates an empty git repo.

### Step 3 — Get the repo URL

After creation, HF shows a git clone URL like:

```
https://huggingface.co/spaces/YOUR_USERNAME/context-handoff-protocol
```

### Step 4 — Push the project via git

```bash
cd chp

# Initialise git if not already done
git init
git add .
git commit -m "Initial CHP deployment"

# Add the HF Space as a remote
git remote add hfspace https://huggingface.co/spaces/YOUR_USERNAME/context-handoff-protocol

# Push (HF will ask for your username + password / token)
# Use your HF username and a token with WRITE access as the password
git push hfspace main
```

If your local branch is called `master`:

```bash
git push hfspace master:main
```

### Step 5 — Watch the build

Go to your Space URL → **App** tab.
HF builds the Docker image automatically. The build log is visible in the
**Logs** tab. First build takes ~5–8 minutes (downloads torch + models).

Subsequent pushes only rebuild changed layers — usually under 2 minutes.

### Step 6 — Verify the app is running

Once the build finishes, the App tab shows the CHP UI.
The green **Running** badge confirms the container is healthy.

---

## Setting secrets

**Never commit API tokens to the git repo.**
Use HF Space Secrets instead — they're injected as environment variables
at container startup.

1. Go to your Space → **Settings** tab → **Variables and Secrets**
2. Click **New secret** for each of the following:

```
Name                    Value
─────────────────────   ──────────────────────────────────────
HF_TOKEN                hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_PROVIDER            hf_inference
HF_LLM_MODEL            HuggingFaceH4/zephyr-7b-beta
EMBEDDING_PROVIDER      sentence_transformer
ST_MODEL                all-MiniLM-L6-v2
DATABASE_URL            sqlite+aiosqlite:////data/chp.db
```

Optional (add if you have them):

```
SLACK_BOT_TOKEN         xoxb-...
GITHUB_TOKEN            ghp_...
```

After saving secrets, click **Factory reboot** to apply them.

> Secrets are encrypted at rest by HF and never exposed in build logs.
> Variables (non-secret) are visible in the Settings tab.

---

## Persistent storage

By default, HF Spaces free tier has **ephemeral storage** — the SQLite
database resets whenever the Space restarts or is rebuilt.

### Free tier workaround (ephemeral is fine for demos)

The mock connector re-seeds data on every run, so the demo always works.
For real usage without persistence, run the full pipeline each session.

### Paid option — Persistent Storage addon

1. Space → Settings → **Persistent storage** → Enable (~$5/month for 20 GB)
2. HF mounts a volume at `/data` that survives restarts and rebuilds
3. Set your secret: `DATABASE_URL=sqlite+aiosqlite:////data/chp.db`

### Free alternative — use a remote database

Swap SQLite for a free hosted PostgreSQL:

**Neon** (https://neon.tech) — free tier: 512 MB, always-on

```bash
pip install asyncpg
```

```env
DATABASE_URL=postgresql+asyncpg://user:password@ep-xxx.neon.tech/chp
```

No code changes required — SQLAlchemy handles both dialects.

---

## Choosing the LLM model

HF Inference API model selection affects quality, speed, and whether
a token is required.

### Tier 1 — No HF token needed (public, rate-limited)

| Model | Quality | Speed | Notes |
|---|---|---|---|
| `HuggingFaceH4/zephyr-7b-beta` | ★★★★☆ | Fast | Best free no-auth model |
| `microsoft/Phi-3-mini-4k-instruct` | ★★★☆☆ | Very fast | Tiny, surprisingly capable |
| `google/gemma-2-2b-it` | ★★★☆☆ | Very fast | Good for short outputs |

### Tier 2 — HF token required (still free)

| Model | Quality | Speed | Notes |
|---|---|---|---|
| `mistralai/Mistral-7B-Instruct-v0.3` | ★★★★★ | Fast | Best overall recommendation |
| `Qwen/Qwen2.5-7B-Instruct` | ★★★★★ | Fast | Strong on structured output |
| `meta-llama/Meta-Llama-3-8B-Instruct` | ★★★★★ | Moderate | Requires model access request |

Set via Space Secret:
```
HF_LLM_MODEL    mistralai/Mistral-7B-Instruct-v0.3
```

---

## Updating the Space

Every `git push` to the `main` branch triggers a rebuild.

```bash
# Make your changes, then:
git add .
git commit -m "Update pipeline scoring weights"
git push hfspace main
```

Docker layer caching means only changed layers rebuild.
The model pre-download layer is cached after the first build.

To force a full rebuild (clears all cache):

Space → Settings → **Factory reboot**

---

## Limitations and mitigations

| Limitation | Impact | Mitigation |
|---|---|---|
| Free tier: 2 vCPU, 16 GB RAM | Clustering 1000+ events may be slow | HDBSCAN on CPU is fast; 16 GB handles ~5,000 events comfortably |
| Free tier: ephemeral storage | DB resets on restart | Use Persistent Storage addon or Neon PostgreSQL |
| Free tier: Space sleeps after 48h inactivity | Cold start ~30s | Pin the Space (Settings → Pin) — costs one ZeroGPU credit |
| HF Inference API rate limits | ~1,000 req/day free | Fine for dev; upgrade to PRO ($9/mo) for higher limits |
| No background tasks on cold start | Pipeline runs synchronously | The 4 pipeline stages run in ~10–20s per user |
| Single worker (--workers 1) | No parallel pipeline runs | Sufficient for team use; scale with Docker replicas if needed |

---

# Part 3 — Provider matrix

Complete reference of every supported combination.

## Embedding providers

| Provider key | Class | Install | Needs key | Offline | Notes |
|---|---|---|---|---|---|
| `sentence_transformer` | `SentenceTransformerEmbedder` | `sentence-transformers` | No | ✓ | **Default. Recommended.** |
| `ollama` | `OllamaEmbedder` | Ollama + `ollama pull nomic-embed-text` | No | ✓ | Requires Ollama daemon |
| `hf_inference_embed` | `HFInferenceEmbedder` | `huggingface_hub` | HF token | ✗ | Good for constrained envs |

## LLM providers

| Provider key | Class | Install | Needs key | Offline | Notes |
|---|---|---|---|---|---|
| `ollama` | `OllamaLLM` | Ollama + `ollama pull <model>` | No | ✓ | **Default. Best for local.** |
| `openai_compat` | `OpenAICompatLLM` | httpx | Optional | ✓ | LM Studio, LocalAI, vLLM, Jan |
| `hf_inference` | `HFInferenceLLM` | `huggingface_hub` | HF token | ✗ | **Best for HF Spaces.** |

## Recommended combinations

| Scenario | EMBEDDING_PROVIDER | LLM_PROVIDER | Notes |
|---|---|---|---|
| Local, has GPU | `sentence_transformer` | `ollama` | Best quality |
| Local, CPU only, 8 GB RAM | `sentence_transformer` | `ollama` (phi3) | phi3 is very RAM-efficient |
| Local, LM Studio user | `sentence_transformer` | `openai_compat` | Point to LM Studio |
| HuggingFace Spaces (free) | `sentence_transformer` | `hf_inference` | Recommended for deployment |
| HuggingFace Spaces + no token | `sentence_transformer` | `hf_inference` (zephyr) | zephyr-7b works without HF_TOKEN |
| Air-gapped / no internet | `sentence_transformer` | `ollama` | 100% offline |
| CI / testing | `sentence_transformer` | *(stub in tests)* | Swap in StubLLM |
