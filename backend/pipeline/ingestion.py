"""
pipeline/ingestion.py
──────────────────────
Stage 1 of the CHP pipeline.

Responsibilities:
  - Collect raw events from all active connectors
  - Deduplicate against already-ingested events
  - Compute embeddings for each new event
  - Persist normalised events to the database
"""
import hashlib
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.base import BaseConnector, RawEvent
from backend.database.models import Event, User
from backend.models.embedding.base import BaseEmbedder

log = logging.getLogger(__name__)


def _event_id(user_id: str, raw: RawEvent) -> str:
    """Deterministic ID so re-runs don't duplicate events."""
    fingerprint = f"{user_id}:{raw.source}:{raw.timestamp.isoformat()}:{raw.content[:120]}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:24]


async def ingest(
    session: AsyncSession,
    user_id: str,
    connectors: list[BaseConnector],
    embedder: BaseEmbedder,
    days_back: int = 30,
) -> dict:
    """
    Run ingestion for one user across all supplied connectors.
    Returns a summary dict with counts.
    """
    # ── Ensure user row exists ────────────────────────────────────────────────
    result = await session.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        log.warning("Ingestion called for unknown user '%s' — skipping.", user_id)
        return {"error": f"User '{user_id}' not found"}

    # ── Fetch from all connectors ─────────────────────────────────────────────
    raw_events: list[RawEvent] = []
    for connector in connectors:
        try:
            fetched = await connector.fetch(user_id, days_back)
            log.info("[%s] %s returned %d events", user_id, connector.source_name, len(fetched))
            raw_events.extend(fetched)
        except Exception as exc:
            log.error("[%s] connector '%s' failed: %s", user_id, connector.source_name, exc)

    if not raw_events:
        return {"user_id": user_id, "fetched": 0, "new": 0, "skipped": 0}

    # ── Deduplicate ───────────────────────────────────────────────────────────
    new_events: list[tuple[str, RawEvent]] = []
    for raw in raw_events:
        eid = _event_id(user_id, raw)
        existing = await session.get(Event, eid)
        if existing is None:
            new_events.append((eid, raw))

    skipped = len(raw_events) - len(new_events)
    log.info("[%s] %d new events, %d already ingested", user_id, len(new_events), skipped)

    if not new_events:
        return {"user_id": user_id, "fetched": len(raw_events), "new": 0, "skipped": skipped}

    # ── Embed in batches of 32 ────────────────────────────────────────────────
    texts    = [raw.content for _, raw in new_events]
    BATCH    = 32
    all_vecs: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch_vecs = await embedder.embed(texts[i : i + BATCH])
        all_vecs.extend(batch_vecs)

    # ── Persist ───────────────────────────────────────────────────────────────
    for (eid, raw), vec in zip(new_events, all_vecs):
        event = Event(
            id          = eid,
            user_id     = user_id,
            source      = raw.source,
            content     = raw.content,
            timestamp   = raw.timestamp,
            url         = raw.url,
            ingested_at = datetime.utcnow(),
        )
        event.set_meta(raw.metadata)
        event.set_embedding(vec)
        session.add(event)

    await session.commit()

    return {
        "user_id": user_id,
        "fetched": len(raw_events),
        "new":     len(new_events),
        "skipped": skipped,
    }
