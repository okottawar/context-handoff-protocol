"""
pipeline/scoring.py
────────────────────
Stage 3 of the CHP pipeline.

Computes a staleness / urgency score for every thread belonging to a user.
The score drives the ordering of threads in the handoff brief.

Scoring formula
───────────────
  score = recency × status_weight + blocker_bonus + open_items_bonus

Components:
  recency         Exponential decay from last activity.
                  Half-life = STALENESS_HALFLIFE_DAYS (default 7 days).
  status_weight   Multiplier based on thread state.
  blocker_bonus   Flat bonus when the thread has a detected blocker keyword.
  open_items_bonus Flat bonus proportional to the number of unresolved signals.

Thread status is heuristically inferred from the most-recent event content
and is also stored so the LLM synthesis stage can override it.
"""
import logging
import math
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Event, Thread

log = logging.getLogger(__name__)

# ── Keyword heuristics ────────────────────────────────────────────────────────
_BLOCKER_PATTERNS = re.compile(
    r"\b(block(?:er|ed|ing)|stuck|wait(?:ing)?\s+on|pending|unresolved|haven't heard|no reply|"
    r"open question|need(?:s)? decision|depends on|can't proceed|awaiting)\b",
    re.IGNORECASE,
)
_DONE_PATTERNS = re.compile(
    r"\b(merged|closed|shipped|deployed|done|complete[d]?|resolved|fixed|granted|approved)\b",
    re.IGNORECASE,
)
# "~60% complete" / "70% complete" describes partial progress, not a finished
# thread — strip these before running _DONE_PATTERNS so they don't cause a
# false "done" classification on in-flight work.
_PCT_COMPLETE = re.compile(r"\d{1,3}\s*%\s*complete[d]?\b", re.IGNORECASE)

_STATUS_WEIGHTS = {
    "blocked":   1.30,
    "in_flight": 1.00,
    "stale":     0.50,
    "done":      0.10,
}


def _infer_status(events: list[Event]) -> str:
    """Heuristically infer thread status from recent event content."""
    # Look at the 3 most-recent events (sorted newest-first)
    recent_texts = " ".join(
        e.content for e in sorted(events, key=lambda x: x.timestamp, reverse=True)[:3]
    )
    # Remove "X% complete" phrases — these describe partial progress, not
    # a finished thread, and would otherwise false-match _DONE_PATTERNS.
    cleaned = _PCT_COMPLETE.sub("", recent_texts)
    if _DONE_PATTERNS.search(cleaned):
        return "done"
    if _BLOCKER_PATTERNS.search(cleaned):
        return "blocked"
    return "in_flight"


def _recency(last_activity: datetime, halflife_days: float) -> float:
    days_ago = max(0.0, (datetime.utcnow() - last_activity).total_seconds() / 86400)
    return math.exp(-days_ago * math.log(2) / halflife_days)


def _confidence(events: list[Event]) -> tuple[float, int]:
    """
    Estimate confidence based on source diversity and event count.
    Returns (confidence_score, inferred_point_count).
    """
    sources    = {e.source for e in events}
    n          = len(events)
    inferred   = max(0, 4 - len(sources))  # fewer sources → more inference
    base       = min(0.98, 0.60 + n * 0.04 + len(sources) * 0.06)
    return round(base, 2), inferred


async def score_threads(
    session: AsyncSession,
    user_id: str,
    halflife_days: float = 7.0,
) -> dict:
    """
    Recompute staleness scores for all threads belonging to user_id.
    """
    result = await session.execute(select(Thread).where(Thread.user_id == user_id))
    threads: list[Thread] = list(result.scalars().all())

    if not threads:
        return {"user_id": user_id, "scored": 0}

    for thread in threads:
        # Load child events
        ev_result = await session.execute(
            select(Event).where(Event.thread_id == thread.id)
        )
        events: list[Event] = list(ev_result.scalars().all())

        if not events:
            thread.staleness_score = 0.0
            continue

        # Status
        status = _infer_status(events)
        thread.status = status

        # Recency
        last = thread.last_activity or max(e.timestamp for e in events)
        rec  = _recency(last, halflife_days)

        # Bonuses
        all_text      = " ".join(e.content for e in events)
        blocker_bonus = 0.25 if _BLOCKER_PATTERNS.search(all_text) else 0.0
        open_bonus    = min(len(events) * 0.03, 0.15)

        # Composite score
        weight = _STATUS_WEIGHTS.get(status, 1.0)
        score  = round((rec + blocker_bonus + open_bonus) * weight, 4)
        thread.staleness_score = score

        # Confidence
        conf, inferred   = _confidence(events)
        thread.confidence    = conf
        thread.inferred_count = inferred

        # Detect blocker text
        if _BLOCKER_PATTERNS.search(all_text):
            # Extract a short snippet around the first match
            m = _BLOCKER_PATTERNS.search(all_text)
            start = max(0, m.start() - 40)
            end   = min(len(all_text), m.end() + 100)
            thread.blocker = all_text[start:end].strip()

        thread.updated_at = datetime.utcnow()

    await session.commit()
    log.info("[%s] scored %d threads", user_id, len(threads))
    return {"user_id": user_id, "scored": len(threads)}
