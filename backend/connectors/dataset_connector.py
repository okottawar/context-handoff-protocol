"""
connectors/dataset_connector.py

Loads pre-authored synthetic events from a JSON file.

This is the recommended connector for demos, judging, and offline
development — it requires no Slack/GitHub tokens and produces realistic,
cross-source signals that cluster meaningfully.

Dataset format (synthetic_dataset.json)

{
  "users": [
    {"id": "priya", "name": "Priya Nair", "email": "priya@company.com", "avatar": "PN"}
  ],
  "events": [
    {
      "user_id": "priya",
      "source": "slack",            # slack | github | notion | email | calendar
      "content": "...",             # the signal text
      "days_ago": 2.3,               # float — relative to load time
      "url": "https://...",          # optional
      "metadata": {"channel": "#eng-backend"}
    }
  ]
}

Timestamps are stored as `days_ago` (relative offsets) rather than absolute
dates, so the dataset always looks "fresh" — staleness scoring and the
"recent activity" framing work correctly no matter when you run the demo.

To build your own dataset

1. Copy synthetic_dataset.json to a new file (e.g. my_dataset.json)
2. Edit `users` — one entry per person you want to demo
3. Edit `events` — each event needs user_id, source, content, days_ago
4. Set DATASET_PATH=path/to/my_dataset.json in .env
5. Restart the server

A companion generator script (_generate_dataset.py) shows how the bundled
dataset was authored and can be adapted for programmatic generation.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from backend.connectors.base import BaseConnector, RawEvent

log = logging.getLogger(__name__)


def default_dataset_path() -> Path:
    """Location of the bundled dataset, relative to this file."""
    return Path(__file__).resolve().parent.parent / "data" / "synthetic_dataset.json"


class DatasetConnector(BaseConnector):
    """
    Connector that serves events from a static JSON dataset.

    The dataset is loaded once and cached. Timestamps are computed relative
    to a single "now" anchor (midnight UTC of the current day) so that
    repeated ingestion runs within the same day produce stable event IDs
    and are correctly deduplicated.
    """

    def __init__(self, dataset_path: str | Path | None = None):
        self._path = Path(dataset_path) if dataset_path else default_dataset_path()
        self._data: dict | None = None

    def _load(self) -> dict:
        if self._data is None:
            if not self._path.exists():
                log.warning("Dataset file not found at %s — returning empty dataset", self._path)
                self._data = {"users": [], "events": []}
            else:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json.load(f)
                log.info(
                    "Loaded dataset from %s (%d users, %d events)",
                    self._path, len(self._data.get("users", [])), len(self._data.get("events", [])),
                )
        return self._data

    def list_users(self) -> list[dict]:
        """Return the user list defined in the dataset (for seeding)."""
        return self._load().get("users", [])

    def info(self) -> dict:
        """Return summary stats — used by the /api/demo/info endpoint."""
        data = self._load()
        events = data.get("events", [])
        from collections import Counter
        by_user   = Counter(e["user_id"] for e in events)
        by_source = Counter(e["source"]  for e in events)
        return {
            "path":        str(self._path),
            "users":       data.get("users", []),
            "event_count": len(events),
            "by_user":     dict(by_user),
            "by_source":   dict(by_source),
        }

    async def fetch(self, user_id: str, days_back: int = 30) -> list[RawEvent]:
        data = self._load()

        # Anchor "now" to midnight UTC so re-runs on the same day produce
        # identical timestamps (and therefore identical event IDs for dedup).
        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        events: list[RawEvent] = []
        for e in data.get("events", []):
            if e.get("user_id") != user_id:
                continue
            days_ago = float(e.get("days_ago", 0))
            if days_ago > days_back:
                continue
            ts = now - timedelta(days=days_ago)
            events.append(RawEvent(
                source    = e["source"],
                content   = e["content"],
                timestamp = ts,
                url       = e.get("url", ""),
                metadata  = e.get("metadata", {}),
            ))

        return events

    @property
    def source_name(self) -> str:
        return "dataset"
