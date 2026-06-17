"""
connectors/mock_connector.py

Mock connector that emits realistic pre-seeded events.
Use this when no Slack/GitHub tokens are available.
Covers three distinct work threads so the clustering pipeline
has clear signal to work with.
"""
from datetime import datetime, timedelta

from backend.connectors.base import BaseConnector, RawEvent

_NOW = datetime.utcnow()
_D = lambda days: _NOW - timedelta(days=days)

#  Pre-seeded events for the demo user "priya" 
# Three threads:
#   T1 - Auth token refresh / rate limiting fix
#   T2 - Q3 infra cost audit
#   T3 - Aditya onboarding / DB access

_PRIYA_EVENTS: list[RawEvent] = [
    #  Thread 1: Auth rate limiting 
    RawEvent("slack",  "priya → sanjay: I think we should switch to a 30-second TTL cache for token validation instead of per-request checks. Saw a similar pattern at my last company and it killed the latency issues.",  _D(1),  "", {"channel": "#eng-backend", "thread": "auth-ttl"}),
    RawEvent("slack",  "sanjay → priya: Makes sense. But what do we do on logout? TTL expiry is fine for passive sessions but a user logging out should invalidate immediately.",                                           _D(1),  "", {"channel": "#eng-backend", "thread": "auth-ttl"}),
    RawEvent("slack",  "priya → sanjay: Good catch. That's the open question — Redis eviction on logout event vs waiting for TTL. Haven't decided yet, that's the blocker.",                                              _D(1),  "", {"channel": "#eng-backend", "thread": "auth-ttl"}),
    RawEvent("github", "PR #441 opened by priya: 'feat: rate-limit token refresh via TTL cache' — Implements 30s Redis TTL for JWT validation. Replaces per-request DB lookup. Reduces auth latency by ~70ms. Awaiting review.",  _D(2),  "https://github.com/org/repo/pull/441", {"type": "pull_request", "state": "open", "reviewer": "sanjay"}),
    RawEvent("github", "Review comment by sanjay on PR #441: 'We need to decide on the logout invalidation strategy before merging. Currently TTL means a logged-out token is valid for up to 30s. Acceptable?'",            _D(1),  "https://github.com/org/repo/pull/441#comment-1", {"type": "review_comment", "pr": "441"}),
    RawEvent("notion", "Auth Rate Limiting Design Doc (edited by priya): Decision to move from per-request JWT verification to Redis-backed TTL cache (30s). Rationale: eliminates DB round-trip on every API call. Open question: logout invalidation strategy — needs decision from Sanjay.",  _D(3),  "https://notion.so/auth-ratelimit", {"type": "page_edit"}),
    RawEvent("slack",  "priya in #eng-backend: Incident post-mortem: token refresh was hitting DB 400 rps during peak. Cache strategy is the fix. PR up now.",                                                             _D(4),  "", {"channel": "#eng-backend"}),

    #  Thread 2: Q3 infra cost audit 
    RawEvent("email",  "From: ramesh@company.com To: priya@company.com — Hi Priya, can you do a quick audit of our Lambda cold start costs? We had a billing spike last month and I suspect it's tied to the deploy cadence change in April.",  _D(5),  "", {"from": "ramesh", "subject": "Q3 Lambda cost review"}),
    RawEvent("notion", "Q3 Infra Cost Audit (draft, 60% complete, edited by priya): Lambda invocation data pulled from CloudWatch. Cold start frequency: 18% of requests. Hypothesis: increased deploy cadence in April correlates with higher cold start rate due to shorter function lifetime. Still need: correlation analysis between deploy timestamps and cold start events.",  _D(4),  "https://notion.so/infra-audit-q3", {"type": "page_edit", "completion": 60}),
    RawEvent("slack",  "priya → ramesh: I've pulled the CloudWatch data and it's looking like the April deploy cadence change is the culprit. Working on the correlation analysis now — draft in Notion.",                   _D(4),  "", {"channel": "#dm-priya-ramesh"}),
    RawEvent("email",  "From: priya@company.com To: ramesh@company.com — Ramesh, initial data pull is done. Cold starts up 23% since April 12. Still correlating with deploy frequency. Will have full analysis by end of week.",  _D(3),  "", {"from": "priya", "subject": "Re: Q3 Lambda cost review"}),

    #  Thread 3: Aditya onboarding 
    RawEvent("slack",  "priya → aditya: Hey! Welcome to the team. I'll help get you set up. First step is DB access — I'll request staging permissions today.",                                                             _D(6),  "", {"channel": "#dm-priya-aditya"}),
    RawEvent("slack",  "priya in #eng-infra: Requesting staging DB read access for @aditya (new engineer, joining backend team). Approved by @ramesh.",                                                                   _D(5),  "", {"channel": "#eng-infra"}),
    RawEvent("slack",  "infra-bot: Staging database access granted for user aditya@company.com. Access level: read-only. Effective immediately.",                                                                          _D(4),  "", {"channel": "#eng-infra", "type": "bot"}),
    RawEvent("email",  "From: priya@company.com To: data-team@company.com — Hi team, requesting production read-only access for our new engineer Aditya. He needs access to the analytics tables for the project he's ramping up on. Manager approval: Ramesh. Please let me know the process.",  _D(3),  "", {"from": "priya", "subject": "Prod DB access request — Aditya", "to": "data-team"}),
    RawEvent("slack",  "priya → aditya: Staging access is live! You should be able to connect. Production access is pending — I've emailed the data team but haven't heard back yet.",                                     _D(3),  "", {"channel": "#dm-priya-aditya"}),
]

_ALEX_EVENTS: list[RawEvent] = [
    RawEvent("github", "PR #388 opened by alex: 'refactor: migrate payment service to async handlers' — Large refactor of the payments module. Reduces timeout errors under load. Review requested from priya.",           _D(3),  "https://github.com/org/repo/pull/388", {"type": "pull_request", "state": "open"}),
    RawEvent("slack",  "alex in #product: Payment service migration is going well. Async handlers are in. Need to finalise the retry policy for failed webhooks before we can ship.",                                      _D(2),  "", {"channel": "#product"}),
    RawEvent("notion", "Payment Service Migration Plan (edited by alex): Phase 1 complete — async handlers deployed to staging. Phase 2: webhook retry policy. Options: exponential backoff (preferred) vs dead-letter queue. Decision needed from Rohan.",  _D(3),  "https://notion.so/payments-migration", {"type": "page_edit"}),
    RawEvent("slack",  "alex → rohan: Quick question on the payments refactor — do you have a preference between exponential backoff and a DLQ for failed webhooks? I lean toward backoff for simplicity but wanted your input.",  _D(2),  "", {"channel": "#dm-alex-rohan"}),
    RawEvent("github", "Review comment on PR #388 by rohan: 'Looks clean. I'd go with exponential backoff, capped at 4 retries. DLQ is overkill for our volume.'",                                                       _D(1),  "https://github.com/org/repo/pull/388#comment-2", {"type": "review_comment"}),
]

_USER_EVENTS: dict[str, list[RawEvent]] = {
    "priya": _PRIYA_EVENTS,
    "alex":  _ALEX_EVENTS,
}


class MockConnector(BaseConnector):
    """
    Returns pre-seeded events for demo users.
    Falls back to an empty list for unknown users.
    """

    async def fetch(self, user_id: str, days_back: int = 30) -> list[RawEvent]:
        events = _USER_EVENTS.get(user_id.lower(), [])
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        return [e for e in events if e.timestamp >= cutoff]

    @property
    def source_name(self) -> str:
        return "mock"
