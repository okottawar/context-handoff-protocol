"""
pipeline/clustering.py
───────────────────────
Stage 2 of the CHP pipeline.

Responsibilities:
  - Load all embedded events for a user
  - Run HDBSCAN to group events into semantic work threads
  - Name each cluster with a short LLM-generated title
  - Persist Thread rows and link Event rows to them

HDBSCAN is chosen over k-means because:
  - No need to pre-specify the number of clusters
  - Naturally handles noise (events that belong to no thread)
  - Robust to clusters of varying density
"""
import hashlib
import logging
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Event, Thread
from backend.models.llm.base import BaseLLM

log = logging.getLogger(__name__)


def _run_hdbscan(vectors: np.ndarray, min_cluster_size: int = 2) -> np.ndarray:
    """
    Return cluster label array (-1 = noise).

    Vectors are assumed to be L2-normalised before calling this function.
    We use 'euclidean' distance on normalised vectors, which is equivalent
    to cosine distance and is supported by all HDBSCAN versions.
    """
    from hdbscan import HDBSCAN

    # L2-normalise so euclidean distance == cosine distance
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = vectors / norms

    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=1,
        metric="euclidean",
        cluster_selection_method="eom",
    )
    return clusterer.fit_predict(normed)


async def _name_cluster(llm: BaseLLM, snippets: list[str]) -> str:
    """Ask the LLM for a short thread title given a sample of event content."""
    sample = "\n".join(f"- {s[:200]}" for s in snippets[:6])
    system = (
        "You are a concise technical assistant. "
        "Reply with ONLY a short work-thread title — 4 to 7 words, no punctuation at end, no quotes, no JSON. "
        "Good examples: 'Auth token refresh rate limiting', 'Q3 infra cost audit', 'Aditya onboarding DB access'. "
        "Bad examples: anything with curly braces, markdown, or more than 10 words."
    )
    user = f"Activity signals:\n{sample}\n\nReply with ONLY the thread title (4-7 words):"
    try:
        resp = await llm.complete(system, user, temperature=0.1, max_tokens=24)
        raw = resp.text.strip().strip('"').strip("'")
        # Guard against LLM returning JSON or very long output
        if raw.startswith("{") or len(raw) > 100:
            raise ValueError("LLM returned unexpected format")
        # Take only the first line, cap at 80 chars
        title = raw.splitlines()[0].strip()[:80]
        return title if title else _fallback_title(snippets)
    except Exception as exc:
        log.warning("LLM naming failed: %s — using fallback title", exc)
        return _fallback_title(snippets)


def _fallback_title(snippets: list[str]) -> str:
    """Extract a readable title from the first snippet without LLM."""
    first = snippets[0] if snippets else "Work thread"
    # Remove source prefix like "[#channel]" or "[GITHUB]"
    import re
    clean = re.sub(r"^\[.*?\]\s*", "", first)
    words = clean.split()[:7]
    return " ".join(words) if words else "Work thread"


def _thread_id(user_id: str, label: int, representative_content: str) -> str:
    fp = f"{user_id}:{label}:{representative_content[:80]}"
    return "t_" + hashlib.sha256(fp.encode()).hexdigest()[:20]


async def cluster(
    session: AsyncSession,
    user_id: str,
    llm: BaseLLM,
    min_cluster_size: int = 2,
) -> dict:
    """
    Cluster all unthreaded events for user_id.
    Returns a summary dict.
    """
    # ── Load embedded events without a thread assignment ─────────────────────
    result = await session.execute(
        select(Event)
        .where(Event.user_id == user_id, Event.event_embed != None)  # noqa: E711
        .order_by(Event.timestamp.desc())
    )
    events: list[Event] = list(result.scalars().all())

    if len(events) < 2:
        log.info("[%s] Not enough events to cluster (%d)", user_id, len(events))
        return {"user_id": user_id, "threads_created": 0, "events_clustered": 0, "noise": 0}

    # ── Build embedding matrix ────────────────────────────────────────────────
    vectors = np.array([e.get_embedding() for e in events], dtype=np.float32)

    # ── HDBSCAN ───────────────────────────────────────────────────────────────
    labels = _run_hdbscan(vectors, min_cluster_size=min_cluster_size)
    unique_labels = set(labels) - {-1}
    noise_count   = int(np.sum(labels == -1))
    log.info("[%s] HDBSCAN: %d clusters, %d noise", user_id, len(unique_labels), noise_count)

    # ── Clear previous thread assignments for this user ───────────────────────
    for ev in events:
        ev.thread_id = None
    # Delete stale Thread rows
    old_threads = await session.execute(select(Thread).where(Thread.user_id == user_id))
    for t in old_threads.scalars():
        await session.delete(t)
    await session.flush()

    # ── Create Thread rows and assign events ──────────────────────────────────
    threads_created = 0
    for label in unique_labels:
        idxs = [i for i, lbl in enumerate(labels) if lbl == label]
        cluster_events = [events[i] for i in idxs]
        snippets       = [e.content for e in cluster_events]
        rep_content    = snippets[0]

        title = await _name_cluster(llm, snippets)
        tid   = _thread_id(user_id, label, rep_content)

        thread = Thread(
            id            = tid,
            user_id       = user_id,
            title         = title,
            last_activity = max(e.timestamp for e in cluster_events),
            created_at    = datetime.utcnow(),
            updated_at    = datetime.utcnow(),
        )
        session.add(thread)

        for ev in cluster_events:
            ev.thread_id = tid

        threads_created += 1

    await session.commit()

    return {
        "user_id":          user_id,
        "threads_created":  threads_created,
        "events_clustered": len(events) - noise_count,
        "noise":            noise_count,
    }
