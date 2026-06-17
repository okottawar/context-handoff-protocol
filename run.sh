#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "  ╔════════════════════════════════════════╗"
echo "  ║   Context Handoff Protocol — CHP v1.0  ║"
echo "  ╚════════════════════════════════════════╝"
echo ""

#  Bootstrap .env 
if [ ! -f .env ]; then
  echo "  [setup] No .env found — copying .env.example"
  cp .env.example .env
fi

#  Virtual environment 
if [ ! -d .venv ]; then
  echo "  [setup] Creating virtual environment…"
  python3 -m venv .venv
fi

echo "  [setup] Activating virtual environment…"
# shellcheck disable=SC1091
source .venv/bin/activate

#  Install dependencies 
echo "  [setup] Installing dependencies (first run may take a few minutes)…"
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

#  Provider check 
EMBED_PROVIDER=$(grep -E '^EMBEDDING_PROVIDER' .env | cut -d= -f2 | tr -d ' ')
LLM_PROVIDER=$(grep -E '^LLM_PROVIDER' .env | cut -d= -f2 | tr -d ' ')
OLLAMA_MODEL=$(grep -E '^OLLAMA_LLM_MODEL' .env | cut -d= -f2 | tr -d ' ')

echo ""
echo "  Active providers:"
echo "    Embedding : ${EMBED_PROVIDER:-sentence_transformer}"
echo "    LLM       : ${LLM_PROVIDER:-ollama}"

if [[ "${LLM_PROVIDER:-ollama}" == "ollama" ]]; then
  echo ""
  echo "  [check] Pinging Ollama at http://localhost:11434…"
  if curl -sf http://localhost:11434/ > /dev/null 2>&1; then
    echo "  [check] Ollama is running ✓"
    # Check if model is pulled
    if ! ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL:-llama3.2}"; then
      echo ""
      echo "  [setup] Model '${OLLAMA_MODEL:-llama3.2}' not found — pulling now…"
      ollama pull "${OLLAMA_MODEL:-llama3.2}"
    fi
  else
    echo "  [warn]  Ollama not running. Start it with: ollama serve"
    echo "          The server will start but LLM features will use fallback."
  fi
fi

#  Start server 
echo ""
echo "  [start] Starting CHP server…"
echo "  [start] Open: http://localhost:8000"
echo ""

uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info
