"""
api/routes.py

All REST API endpoints for the CHP backend.

Endpoints

GET  /api/health               — liveness check
GET  /api/config               — active provider info
GET  /api/users                — list all users
POST /api/users                — create a user
GET  /api/users/{uid}/threads  — get threads for a user
GET  /api/users/{uid}/brief    — get latest handoff brief
POST /api/users/{uid}/run      — run full pipeline (background task)
POST /api/users/{uid}/ingest   — run ingestion only
POST /api/users/{uid}/cluster  — run cluster + score only
POST /api/users/{uid}/synthesise — run synthesis only
GET  /api/users/{uid}/events   — list raw events
"""
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings as cfg
from backend.connectors.dataset_connector import DatasetConnector, default_dataset_path
from backend.connectors.mock_connector import MockConnector
from backend.connectors.slack_connector import SlackConnector
from backend.connectors.github_connector import GitHubConnector
from backend.database.db import get_session
from backend.database.models import Event, HandoffBrief, Thread, User
from backend.pipeline import clustering, ingestion, scoring, synthesis
from backend.pipeline.orchestrator import run_pipeline
from backend.registry import get_embedder, get_llm, provider_info

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


#  Dependency helpers 

def _dataset_path() -> Path:
    return Path(cfg.dataset_path) if cfg.dataset_path else default_dataset_path()


def _connectors():
    """
    Return the list of active connectors based on config.

    Priority:
      1. DatasetConnector — if backend/data/synthetic_dataset.json (or
         DATASET_PATH) exists. This is the recommended demo connector.
      2. MockConnector — fallback with two hardcoded users (priya, alex).
      3. SlackConnector / GitHubConnector — added on top if tokens are set.
    """
    path = _dataset_path()
    conns: list = []
    if path.exists():
        conns.append(DatasetConnector(path))
    else:
        conns.append(MockConnector())

    if cfg.slack_bot_token:
        conns.append(SlackConnector(cfg.slack_bot_token))
    if cfg.github_token:
        conns.append(GitHubConnector(cfg.github_token))
    return conns


def _dataset_connector() -> DatasetConnector | None:
    """Return a DatasetConnector if the dataset file exists, else None."""
    path = _dataset_path()
    return DatasetConnector(path) if path.exists() else None


#  Schemas 

class CreateUserRequest(BaseModel):
    name:   str
    email:  str | None = None
    avatar: str | None = None   # initials or URL

class UserResponse(BaseModel):
    id:    str
    name:  str
    email: str | None
    avatar: str | None

class ThreadResponse(BaseModel):
    id:              str
    title:           str
    status:          str
    staleness_score: float
    confidence:      float
    inferred_count:  int
    blocker:         str | None
    next_action:     str | None
    last_activity:   str | None
    event_count:     int

class BriefResponse(BaseModel):
    id:           str
    user_id:      str
    generated_at: str
    summary:      str | None
    threads:      list[dict]
    llm_model:    str | None
    verified:     bool

class EventResponse(BaseModel):
    id:        str
    source:    str
    content:   str
    timestamp: str
    url:       str | None
    thread_id: str | None


#  Routes 

@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/config")
async def get_config():
    return provider_info()


#  Users 

@router.get("/users", response_model=list[UserResponse])
async def list_users(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).order_by(User.name))
    return [
        UserResponse(id=u.id, name=u.name, email=u.email, avatar=u.avatar)
        for u in result.scalars()
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
):
    uid  = body.name.lower().replace(" ", "_")
    user = User(
        id     = uid,
        name   = body.name,
        email  = body.email,
        avatar = body.avatar or body.name[:2].upper(),
    )
    session.add(user)
    await session.commit()
    return UserResponse(id=user.id, name=user.name, email=user.email, avatar=user.avatar)


#  Threads 

@router.get("/users/{uid}/threads", response_model=list[ThreadResponse])
async def get_threads(uid: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Thread)
        .where(Thread.user_id == uid)
        .order_by(Thread.staleness_score.desc())
    )
    threads = list(result.scalars())
    out = []
    for t in threads:
        ev_count = await session.execute(
            select(Event).where(Event.thread_id == t.id)
        )
        out.append(ThreadResponse(
            id              = t.id,
            title           = t.title,
            status          = t.status,
            staleness_score = t.staleness_score,
            confidence      = t.confidence,
            inferred_count  = t.inferred_count,
            blocker         = t.blocker,
            next_action     = t.next_action,
            last_activity   = str(t.last_activity) if t.last_activity else None,
            event_count     = len(list(ev_count.scalars())),
        ))
    return out


#  Brief 

@router.get("/users/{uid}/brief", response_model=BriefResponse | None)
async def get_latest_brief(uid: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(HandoffBrief)
        .where(HandoffBrief.user_id == uid)
        .order_by(HandoffBrief.generated_at.desc())
        .limit(1)
    )
    brief = result.scalar_one_or_none()
    if not brief:
        return None
    return BriefResponse(
        id           = brief.id,
        user_id      = brief.user_id,
        generated_at = str(brief.generated_at),
        summary      = brief.summary,
        threads      = brief.content,
        llm_model    = brief.llm_model,
        verified     = brief.verified,
    )


#  Events 

@router.get("/users/{uid}/events", response_model=list[EventResponse])
async def get_events(uid: str, limit: int = 100, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Event)
        .where(Event.user_id == uid)
        .order_by(Event.timestamp.desc())
        .limit(limit)
    )
    return [
        EventResponse(
            id        = e.id,
            source    = e.source,
            content   = e.content[:300],
            timestamp = str(e.timestamp),
            url       = e.url,
            thread_id = e.thread_id,
        )
        for e in result.scalars()
    ]


#  Pipeline triggers 

async def _pipeline_task(uid: str, db_url: str):
    """Background task — creates its own session."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        await run_pipeline(
            session     = session,
            user_id     = uid,
            connectors  = _connectors(),
            embedder    = get_embedder(),
            llm         = get_llm(),
        )
    await engine.dispose()


@router.post("/users/{uid}/run")
async def run_full_pipeline(
    uid: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Trigger the full 4-stage pipeline in the background."""
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{uid}' not found")
    background_tasks.add_task(_pipeline_task, uid, cfg.database_url)
    return {"status": "pipeline started", "user_id": uid}


@router.post("/users/{uid}/ingest")
async def run_ingest(uid: str, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(404, f"User '{uid}' not found")
    result = await ingestion.ingest(
        session, uid, _connectors(), get_embedder(), cfg.ingest_days_back
    )
    return result


@router.post("/users/{uid}/cluster")
async def run_cluster(uid: str, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(404, f"User '{uid}' not found")
    c = await clustering.cluster(session, uid, get_llm(), cfg.hdbscan_min_cluster_size)
    s = await scoring.score_threads(session, uid, cfg.staleness_halflife_days)
    return {"cluster": c, "score": s}


@router.post("/users/{uid}/synthesise")
async def run_synthesise(uid: str, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(404, f"User '{uid}' not found")
    brief = await synthesis.synthesise(session, uid, get_llm(), cfg.max_threads_per_brief)
    return BriefResponse(
        id           = brief.id,
        user_id      = brief.user_id,
        generated_at = str(brief.generated_at),
        summary      = brief.summary,
        threads      = brief.content,
        llm_model    = brief.llm_model,
        verified     = brief.verified,
    )


#  Demo dataset 

@router.get("/demo/info")
async def demo_info():
    """
    Return metadata about the bundled synthetic dataset:
    user list, total event count, and breakdowns by user/source.
    Returns null fields if no dataset file is present.
    """
    dc = _dataset_connector()
    if dc is None:
        return {"available": False, "path": str(_dataset_path())}
    info = dc.info()
    return {"available": True, **info}


@router.post("/demo/seed")
async def demo_seed(session: AsyncSession = Depends(get_session)):
    """
    Ensure every user defined in the synthetic dataset exists in the DB.
    Idempotent — safe to call multiple times.
    """
    dc = _dataset_connector()
    if dc is None:
        raise HTTPException(404, f"No dataset found at {_dataset_path()}")

    created = []
    for u in dc.list_users():
        existing = await session.get(User, u["id"])
        if not existing:
            session.add(User(
                id     = u["id"],
                name   = u["name"],
                email  = u.get("email"),
                avatar = u.get("avatar") or u["name"][:2].upper(),
            ))
            created.append(u["id"])
    await session.commit()

    all_users = [u["id"] for u in dc.list_users()]
    return {"created": created, "total_users": len(all_users), "user_ids": all_users}


@router.post("/demo/run-all")
async def demo_run_all(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Run the full 4-stage pipeline for every user in the synthetic dataset.
    Seeds users first (idempotent), then runs in the background —
    poll /api/users/{uid}/brief to check progress.
    """
    dc = _dataset_connector()
    if dc is None:
        raise HTTPException(404, f"No dataset found at {_dataset_path()}")

    # Ensure all dataset users exist before queuing pipeline runs
    for u in dc.list_users():
        if not await session.get(User, u["id"]):
            session.add(User(
                id     = u["id"],
                name   = u["name"],
                email  = u.get("email"),
                avatar = u.get("avatar") or u["name"][:2].upper(),
            ))
    await session.commit()

    user_ids = [u["id"] for u in dc.list_users()]
    for uid in user_ids:
        background_tasks.add_task(_pipeline_task, uid, cfg.database_url)

    return {"status": "started", "user_ids": user_ids}
