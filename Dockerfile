
# Dockerfile — Context Handoff Protocol
# Target: HuggingFace Spaces (Docker SDK) + general Docker deployment
#
# Build:  docker build -t chp .
# Run:    docker run -p 7860:7860 --env-file .env chp


FROM python:3.11-slim

# System dependencies 
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      git \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

# Working directory 
WORKDIR /app

# Python dependencies (cached layer — only re-runs when requirements change) ─
COPY requirements.txt requirements.hfspaces.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.hfspaces.txt

# Pre-download the default embedding model so startup is instant 
# This bakes the model weights into the image (~90 MB).
# Remove this RUN block if you want a smaller image and are OK with first-run delay.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Application source ─
COPY backend/  ./backend/
COPY frontend/ ./frontend/

# HuggingFace Spaces persistent storage lives at /data 
# Free tier: ephemeral  |  Persistent Storage addon: survives restarts
# The DATABASE_URL env var points here (set in Space secrets or .env).
RUN mkdir -p /data

# Non-root user (required by HF Spaces) 
RUN useradd -m -u 1000 chpuser \
 && chown -R chpuser:chpuser /app /data
USER chpuser

# Runtime configuration
# HF Spaces routes external HTTPS → container port 7860
ENV PORT=7860
ENV HOST=0.0.0.0
ENV DATABASE_URL=sqlite+aiosqlite:////data/chp.db

# Sentence-transformers model cache (baked in above; also honoured at runtime)
ENV SENTENCE_TRANSFORMERS_HOME=/app/.st_cache
ENV HF_HOME=/app/.hf_cache
ENV TRANSFORMERS_CACHE=/app/.hf_cache

EXPOSE 7860

# Entrypoint 
CMD ["python", "-m", "uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", "--port", "7860", \
     "--workers", "1", "--log-level", "info"]
