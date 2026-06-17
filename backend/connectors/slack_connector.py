"""
connectors/slack_connector.py

Fetches messages sent or participated in by a user from Slack.
Requires a Bot Token with scopes:
  channels:history, channels:read, groups:history, groups:read,
  im:history, mpim:history, users:read

Set SLACK_BOT_TOKEN in .env to activate.
"""
from datetime import datetime, timedelta, timezone

from backend.connectors.base import BaseConnector, RawEvent


class SlackConnector(BaseConnector):
    def __init__(self, token: str):
        self._token = token

    async def fetch(self, user_id: str, days_back: int = 30) -> list[RawEvent]:
        # Lazy import — slack_sdk is optional
        from slack_sdk.web.async_client import AsyncWebClient

        client = AsyncWebClient(token=self._token)
        cutoff_ts = (datetime.now(tz=timezone.utc) - timedelta(days=days_back)).timestamp()

        # Resolve Slack user ID from our internal user_id (treat as email or slack id)
        slack_uid = await self._resolve_user(client, user_id)
        if not slack_uid:
            return []

        events: list[RawEvent] = []

        # Fetch all public channels the user is a member of
        channels_resp = await client.users_conversations(
            user=slack_uid,
            types="public_channel,private_channel,im,mpim",
            limit=200,
        )
        channels = channels_resp.get("channels", [])

        for channel in channels:
            channel_id   = channel["id"]
            channel_name = channel.get("name", channel_id)
            history_resp = await client.conversations_history(
                channel=channel_id,
                oldest=str(cutoff_ts),
                limit=200,
            )
            for msg in history_resp.get("messages", []):
                # Only include messages sent by the target user
                if msg.get("user") != slack_uid:
                    continue
                text = msg.get("text", "").strip()
                if not text:
                    continue
                ts = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc).replace(tzinfo=None)
                url = (
                    f"https://slack.com/archives/{channel_id}/p"
                    + msg["ts"].replace(".", "")
                )
                events.append(
                    RawEvent(
                        source="slack",
                        content=f"[#{channel_name}] {text}",
                        timestamp=ts,
                        url=url,
                        metadata={
                            "channel_id":   channel_id,
                            "channel_name": channel_name,
                            "slack_ts":     msg["ts"],
                            "thread_ts":    msg.get("thread_ts"),
                        },
                    )
                )
        return events

    async def _resolve_user(self, client, user_id: str) -> str | None:
        """
        Try to resolve user_id as a Slack user ID or email.
        Returns the Slack UID or None if not found.
        """
        # If it looks like a Slack UID already
        if user_id.upper().startswith("U") and len(user_id) > 6:
            return user_id
        # Try lookup by email
        try:
            resp = await client.users_lookupByEmail(email=user_id)
            return resp["user"]["id"]
        except Exception:
            return None

    @property
    def source_name(self) -> str:
        return "slack"
