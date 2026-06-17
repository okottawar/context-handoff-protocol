"""
pipeline/orchestrator.py
─────────────────────────
Runs the full CHP pipeline for a user in one call.

  Stage 1 — Ingest    : fetch + embed + persist events
  Stage 2 — Cluster   : HDBSCAN → work threads
  Stage 3 — Score     : staleness + confidence per thread
  Stage 4 — Synthesise: LLM-generated handoff brief

Each stage result is collected and returned as a structured report.
"""
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings as cfg
from backend.connectors.base import BaseConnector
from backend.models.embedding.base import BaseEmbedder
from backend.models.llm.base import BaseLLM
from backend.pipeline import clustering, ingestion, scoring, synthesis

log = logging.getLogger(__name__)


async def run_pipeline(
    session: AsyncSession,
    user_id: str,
    connectors: list[BaseConnector],
    embedder: BaseEmbedder,
    llm: BaseLLM,
    skip_ingest: bool = False,
) -> dict[str, Any]:
    """
    Execute all four pipeline stages for user_id.

    Parameters
    ----------
    skip_ingest : bool
        If True, skip Stage 1 (useful for re-clustering without re-fetching).

    Returns
    -------
    dict with per-stage results and a top-level "brief_id" key.
    """
    report: dict[str, Any] = {
        "user_id": user_id,
        "stages":  {},
    }

    total_start = time.monotonic()

    # ── Stage 1: Ingest ───────────────────────────────────────────────────────
    if not skip_ingest:
        t0 = time.monotonic()
        result = await ingestion.ingest(
            session, user_id, connectors, embedder, cfg.ingest_days_back
        )
        report["stages"]["ingest"] = {**result, "elapsed_s": round(time.monotonic() - t0, 2)}
    else:
        report["stages"]["ingest"] = {"skipped": True}

    # ── Stage 2: Cluster ──────────────────────────────────────────────────────
    t0 = time.monotonic()
    result = await clustering.cluster(
        session, user_id, llm, cfg.hdbscan_min_cluster_size
    )
    report["stages"]["cluster"] = {**result, "elapsed_s": round(time.monotonic() - t0, 2)}

    # ── Stage 3: Score ────────────────────────────────────────────────────────
    t0 = time.monotonic()
    result = await scoring.score_threads(session, user_id, cfg.staleness_halflife_days)
    report["stages"]["score"] = {**result, "elapsed_s": round(time.monotonic() - t0, 2)}

    # ── Stage 4: Synthesise ───────────────────────────────────────────────────
    t0 = time.monotonic()
    brief = await synthesis.synthesise(session, user_id, llm, cfg.max_threads_per_brief)
    report["stages"]["synthesise"] = {
        "brief_id":  brief.id,
        "threads":   len(brief.content),
        "model":     brief.llm_model,
        "elapsed_s": round(time.monotonic() - t0, 2),
    }

    report["brief_id"]    = brief.id
    report["total_elapsed_s"] = round(time.monotonic() - total_start, 2)

    log.info(
        "[%s] pipeline complete in %.1fs — brief %s",
        user_id, report["total_elapsed_s"], brief.id
    )
    return report
