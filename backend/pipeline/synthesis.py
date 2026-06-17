"""
pipeline/synthesis.py
──────────────────────
Stage 4 of the CHP pipeline.

Takes the scored, clustered threads and asks the LLM to produce a
structured handoff brief in JSON.  The JSON is validated and stored
as a HandoffBrief row.

The prompt is deliberately strict to elicit structured output even from
smaller local models (Phi-3, Llama-3.2, Mistral-7B).
"""
import json
import logging
import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Event, HandoffBrief, Thread, User
from backend.models.llm.base import BaseLLM

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a technical writing assistant for engineering teams.
Your job is to create a structured handoff brief in valid JSON.

Output ONLY a JSON object — no markdown fences, no prose before or after.
Use this exact schema:

{
  "summary": "<2-3 sentence overall summary of the person's in-flight work>",
  "threads": [
    {
      "title": "<thread title>",
      "status": "<in_flight|blocked|done|stale>",
      "current_state": "<1-2 sentences describing where things stand>",
      "last_decision": "<most recent decision made, or null>",
      "blocker": "<what is blocking progress, or null>",
      "next_action": "<concrete next step for the person inheriting this work>",
      "confidence": <float 0-1>,
      "inferred_count": <int — number of facts inferred rather than explicit>,
      "sources": [<list of source types: "slack", "github", "notion", "email", "calendar">]
    }
  ],
  "critical_handoff_items": [
    "<item that absolutely must not be missed>"
  ]
}

Be concise. Each field should be 1-2 sentences max.
The "next_action" must be concrete and actionable, not vague.
"""


def _build_user_prompt(user_name: str, threads_data: list[dict]) -> str:
    lines = [f"Generate a handoff brief for {user_name}.\n\nWork threads:\n"]
    for t in threads_data:
        lines.append(f"=== Thread: {t['title']} (status: {t['status']}) ===")
        lines.append(f"Staleness score: {t['staleness_score']:.3f} (higher = more urgent)")
        lines.append(f"Last activity: {t['last_activity']}")
        lines.append(f"Confidence: {t['confidence']:.0%}")
        lines.append("Recent signals:")
        for ev in t["events"][:6]:
            lines.append(f"  [{ev['source'].upper()}] {ev['content'][:280]}")
        lines.append("")
    return "\n".join(lines)


def _parse_json_response(text: str) -> dict | None:
    """Extract and parse JSON from the LLM response, tolerating minor formatting."""
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting the first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _fallback_brief(threads: list[Thread], events_by_thread: dict) -> dict:
    """Produce a rule-based brief if the LLM fails or is unavailable."""
    thread_entries = []
    for t in threads:
        evs = events_by_thread.get(t.id, [])
        thread_entries.append({
            "title":         t.title,
            "status":        t.status,
            "current_state": evs[0].content[:200] if evs else "No recent activity.",
            "last_decision": None,
            "blocker":       t.blocker,
            "next_action":   "Review recent activity and determine next steps.",
            "confidence":    t.confidence,
            "inferred_count": t.inferred_count,
            "sources":       list({e.source for e in evs}),
        })
    return {
        "summary":                 f"{len(threads)} active work threads detected.",
        "threads":                 thread_entries,
        "critical_handoff_items":  [t.title for t in threads if t.status == "blocked"],
    }


async def synthesise(
    session: AsyncSession,
    user_id: str,
    llm: BaseLLM,
    max_threads: int = 8,
) -> HandoffBrief:
    """
    Generate and persist a HandoffBrief for user_id.
    Returns the saved HandoffBrief ORM object.
    """
    # ── Load user ─────────────────────────────────────────────────────────────
    user = await session.get(User, user_id)
    user_name = user.name if user else user_id

    # ── Load top-N threads by staleness score ─────────────────────────────────
    result = await session.execute(
        select(Thread)
        .where(Thread.user_id == user_id)
        .order_by(Thread.staleness_score.desc())
        .limit(max_threads)
    )
    threads: list[Thread] = list(result.scalars().all())

    if not threads:
        log.warning("[%s] No threads to synthesise", user_id)
        brief = HandoffBrief(
            id           = str(uuid.uuid4()),
            user_id      = user_id,
            generated_at = datetime.utcnow(),
            summary      = "No in-flight work threads found.",
            llm_model    = llm.provider_name,
        )
        brief.content = []
        session.add(brief)
        await session.commit()
        return brief

    # ── Load events per thread ────────────────────────────────────────────────
    events_by_thread: dict[str, list[Event]] = {}
    for thread in threads:
        ev_result = await session.execute(
            select(Event)
            .where(Event.thread_id == thread.id)
            .order_by(Event.timestamp.desc())
        )
        events_by_thread[thread.id] = list(ev_result.scalars().all())

    # ── Build LLM input ───────────────────────────────────────────────────────
    threads_data = [
        {
            "title":          t.title,
            "status":         t.status,
            "staleness_score": t.staleness_score,
            "last_activity":  str(t.last_activity),
            "confidence":     t.confidence,
            "events": [
                {"source": e.source, "content": e.content}
                for e in events_by_thread.get(t.id, [])[:8]
            ],
        }
        for t in threads
    ]

    user_prompt = _build_user_prompt(user_name, threads_data)
    brief_data: dict | None = None

    # ── LLM call ──────────────────────────────────────────────────────────────
    try:
        resp       = await llm.complete(_SYSTEM_PROMPT, user_prompt, temperature=0.15, max_tokens=2048)
        brief_data = _parse_json_response(resp.text)
        if brief_data is None:
            log.warning("[%s] LLM returned unparseable JSON, using fallback", user_id)
    except Exception as exc:
        log.error("[%s] LLM synthesis failed: %s — using fallback brief", user_id, exc)

    if brief_data is None:
        brief_data = _fallback_brief(threads, events_by_thread)

    # ── Merge DB metadata into the JSON content ───────────────────────────────
    # Ensure confidence / inferred_count from our scorer is reflected
    for i, t in enumerate(threads):
        if i < len(brief_data.get("threads", [])):
            entry = brief_data["threads"][i]
            entry.setdefault("confidence",    t.confidence)
            entry.setdefault("inferred_count", t.inferred_count)
            sources = list({e.source for e in events_by_thread.get(t.id, [])})
            entry["sources"] = sources
            entry["thread_id"] = t.id

    # ── Persist ───────────────────────────────────────────────────────────────
    brief = HandoffBrief(
        id           = str(uuid.uuid4()),
        user_id      = user_id,
        generated_at = datetime.utcnow(),
        summary      = brief_data.get("summary", ""),
        llm_model    = llm.provider_name,
    )
    brief.content = brief_data.get("threads", [])
    session.add(brief)
    await session.commit()

    log.info("[%s] brief generated with %d threads via %s", user_id, len(threads), llm.provider_name)
    return brief
