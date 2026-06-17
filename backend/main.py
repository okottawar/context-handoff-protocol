"""
main.py

FastAPI application entry point.

On startup:
  1. Creates the SQLite schema (idempotent)
  2. Seeds demo users — from the synthetic dataset if present,
     otherwise a small hardcoded fallback list
  3. Warms up the embedding model (sentence-transformers)

Run:
  uvicorn backend.main:app --reload --port 8000
  or just:  ./run.sh
"""
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router, _dataset_connector
from backend.config import settings
from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import User
from backend.registry import get_embedder, provider_info

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream = sys.stdout,
)
log = logging.getLogger(__name__)

# Fallback users if no synthetic dataset is present
_FALLBACK_USERS = [
    {"id": "priya", "name": "Priya Nair", "email": "priya@company.com", "avatar": "PN"},
    {"id": "alex",  "name": "Alex Chen",  "email": "alex@company.com",  "avatar": "AC"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    #  Startup 
    log.info("CHP server starting up…")
    await init_db()
    log.info("Database initialised at: %s", settings.database_url)

    # Seed users — prefer the synthetic dataset's user list
    dc = _dataset_connector()
    seed_users = dc.list_users() if dc else _FALLBACK_USERS
    if dc:
        log.info("Synthetic dataset found — seeding %d users", len(seed_users))
    else:
        log.info("No synthetic dataset found — seeding %d fallback users", len(seed_users))

    async with AsyncSessionLocal() as session:
        for u in seed_users:
            existing = await session.get(User, u["id"])
            if not existing:
                session.add(User(
                    id     = u["id"],
                    name   = u["name"],
                    email  = u.get("email"),
                    avatar = u.get("avatar") or u["name"][:2].upper(),
                ))
        await session.commit()
    log.info("Demo users ready: %s", [u["id"] for u in seed_users])

    # Warm up embedding model (downloads model on first run)
    info = provider_info()
    log.info("Active providers: %s", info)
    if settings.embedding_provider == "sentence_transformer":
        log.info("Warming up sentence-transformers model '%s'…", settings.st_model)
        try:
            embedder = get_embedder()
            await embedder.embed(["warmup"])
            log.info("Embedding model ready (dim=%d)", embedder.dimension())
        except Exception as exc:
            log.warning("Embedding warm-up failed: %s", exc)

    log.info("CHP ready — http://%s:%d", settings.host, settings.port)

    yield

    #  Shutdown 
    log.info("CHP server shutting down.")


app = FastAPI(
    title       = "Context Handoff Protocol",
    description = "AI-powered living handoff briefs for engineering teams.",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# CORS — allow the bundled frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# API routes
app.include_router(router)

# Serve the frontend from /frontend/
import pathlib
_frontend = pathlib.Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host    = settings.host,
        port    = settings.port,
        reload  = True,
        log_level = "info",
    )
