"""
_generate_dataset.py

One-off generator script for synthetic_dataset.json.
Run manually if you want to regenerate or extend the dataset:

    python3 backend/data/_generate_dataset.py

This script is NOT imported at runtime — it's a content-authoring tool.
The output (synthetic_dataset.json) is what the DatasetConnector reads.
"""
import json
from pathlib import Path

USERS = [
    {"id": "priya",  "name": "Priya Nair",   "email": "priya@company.com",  "avatar": "PN", "role": "Senior Backend Engineer"},
    {"id": "alex",   "name": "Alex Chen",    "email": "alex@company.com",   "avatar": "AC", "role": "Backend Engineer — Payments"},
    {"id": "maria",  "name": "Maria Santos", "email": "maria@company.com",  "avatar": "MS", "role": "Product Designer"},
    {"id": "jordan", "name": "Jordan Lee",   "email": "jordan@company.com", "avatar": "JL", "role": "Product Manager"},
]

# Each event: (user_id, source, content, days_ago, url, metadata)
EVENTS = [

    # PRIYA NAIR — Senior Backend Engineer

    #  Thread A: Auth token refresh / rate limiting (BLOCKED) 
    ("priya", "slack",
     "priya \u2192 sanjay: I think we should switch to a 30-second TTL cache for token "
     "validation instead of per-request checks. Saw this pattern work well at my last "
     "company \u2014 should cut auth latency significantly.",
     4.3, "", {"channel": "#eng-backend", "thread": "auth-ttl"}),

    ("priya", "github",
     "PR #441 opened by priya: 'feat: rate-limit token refresh via TTL cache' \u2014 "
     "Implements a 30s Redis TTL for JWT validation, replacing per-request DB lookups. "
     "Reduces auth latency by ~70ms. Status: open, awaiting review.",
     3.8, "https://github.com/org/backend/pull/441",
     {"type": "pull_request", "state": "open", "pr_number": 441, "reviewer": "sanjay"}),

    ("priya", "notion",
     "Auth Rate Limiting Design Doc (edited by priya): Decision recorded \u2014 move from "
     "per-request JWT verification to a Redis-backed TTL cache (30s). Rationale: "
     "eliminates a DB round-trip on every API call. Open question flagged: logout "
     "invalidation strategy still needs a decision from Sanjay.",
     3.5, "https://notion.so/auth-ratelimit-design", {"type": "page_edit"}),

    ("priya", "slack",
     "sanjay \u2192 priya: Makes sense overall. One concern though \u2014 what happens on "
     "logout? A TTL means a logged-out token could stay valid for up to 30 seconds. Is "
     "that acceptable for our security posture?",
     2.4, "", {"channel": "#eng-backend", "thread": "auth-ttl"}),

    ("priya", "slack",
     "priya \u2192 sanjay: Good catch, that's exactly the open question. We're stuck "
     "between invalidating the cache entry immediately on logout (extra Redis write) vs "
     "accepting the 30s window. Haven't decided yet \u2014 this is currently blocking the "
     "PR merge.",
     2.2, "", {"channel": "#eng-backend", "thread": "auth-ttl"}),

    ("priya", "github",
     "Review comment by sanjay on PR #441: 'Blocking on the logout invalidation decision "
     "above before I can approve. Can we get a decision by end of week?'",
     1.6, "https://github.com/org/backend/pull/441#discussion_r1",
     {"type": "review_comment", "pr_number": 441}),

    ("priya", "slack",
     "priya in #eng-backend: Quick incident note \u2014 the auth DB was hitting 400 rps "
     "during peak yesterday, which is the root cause we're fixing with PR #441. Once the "
     "logout question is resolved, this should ship immediately.",
     5.0, "", {"channel": "#eng-backend"}),

    #  Thread B: Q3 infra cost audit (IN_FLIGHT) 
    ("priya", "email",
     "From: ramesh@company.com To: priya@company.com \u2014 Hi Priya, can you do a quick "
     "audit of our Lambda cold-start costs? We had a billing spike last month and I "
     "suspect it's tied to the deploy cadence change we made in April. Would love your "
     "read on this by end of week.",
     7.2, "", {"from": "ramesh", "subject": "Q3 Lambda cost review"}),

    ("priya", "notion",
     "Q3 Infra Cost Audit (draft, ~60% complete, edited by priya): Pulled CloudWatch "
     "invocation data for the last 90 days. Cold-start frequency is at 18% of total "
     "requests, up from 11% in March. Hypothesis: the increased deploy cadence introduced "
     "in April is shortening function lifetime and causing more cold starts. Still need: "
     "a proper correlation analysis between deploy timestamps and cold-start spikes.",
     4.6, "https://notion.so/infra-cost-audit-q3", {"type": "page_edit", "completion": 60}),

    ("priya", "slack",
     "priya \u2192 ramesh: Update on the Lambda audit \u2014 I've pulled the CloudWatch "
     "data and it's looking like the April deploy cadence change is the likely culprit. "
     "Cold starts are up 23% since then. Still working on the correlation analysis, draft "
     "is in Notion.",
     4.0, "", {"channel": "dm-priya-ramesh"}),

    ("priya", "email",
     "From: priya@company.com To: ramesh@company.com \u2014 Ramesh, quick update: initial "
     "data pull is done and the April correlation looks strong. I want to finish the full "
     "correlation chart before sending you a final recommendation \u2014 should have it "
     "done by early next week.",
     3.1, "", {"from": "priya", "subject": "Re: Q3 Lambda cost review"}),

    #  Thread C: Aditya onboarding DB access (IN_FLIGHT, near done) 
    ("priya", "slack",
     "priya \u2192 aditya: Hey, welcome to the team! I'll help get you set up over the "
     "next couple of days. First step is database access \u2014 I'll request staging "
     "permissions for you today.",
     7.0, "", {"channel": "dm-priya-aditya"}),

    ("priya", "slack",
     "priya in #eng-infra: Requesting staging DB read access for @aditya \u2014 new "
     "backend engineer joining the team this week. Manager approval: @ramesh.",
     6.4, "", {"channel": "#eng-infra"}),

    ("priya", "slack",
     "infra-bot: Staging database access has been granted for user aditya@company.com. "
     "Access level: read-only. Effective immediately.",
     5.8, "", {"channel": "#eng-infra", "type": "bot"}),

    ("priya", "email",
     "From: priya@company.com To: data-team@company.com \u2014 Hi team, requesting "
     "production read-only access for our new engineer Aditya. He needs access to the "
     "analytics tables for the project he's ramping up on. Manager approval: Ramesh. "
     "Could you let me know the process for this?",
     4.2, "", {"from": "priya", "subject": "Prod DB access request \u2014 Aditya", "to": "data-team"}),

    ("priya", "slack",
     "priya \u2192 aditya: Good news \u2014 staging access is live, you should be able to "
     "connect now! Production access is still pending though, I emailed the data team a "
     "few days ago but haven't heard back yet.",
     3.6, "", {"channel": "dm-priya-aditya"}),

    #  Thread D: Postgres 16 migration (DONE / STALE) 
    ("priya", "slack",
     "priya in #eng-backend: Heads up \u2014 planning to migrate our primary database "
     "from Postgres 14 to 16 next week. I'll share a migration runbook shortly. Should be "
     "a low-risk upgrade with some nice performance wins on JSONB queries.",
     21.0, "", {"channel": "#eng-backend"}),

    ("priya", "notion",
     "Postgres 16 Migration Runbook (edited by priya): Step-by-step rollback-safe "
     "migration plan. Includes pre-migration backup checklist, maintenance window "
     "scheduling, and post-migration verification queries.",
     19.5, "https://notion.so/postgres-16-migration-runbook", {"type": "page_edit"}),

    ("priya", "github",
     "PR #410 merged by priya: 'chore: bump postgres to v16, update connection pooling "
     "config' \u2014 All CI checks passed. Deployed to staging successfully, production "
     "migration completed during the scheduled maintenance window.",
     16.0, "https://github.com/org/backend/pull/410",
     {"type": "pull_request", "state": "merged", "pr_number": 410}),

    ("priya", "slack",
     "priya in #eng-backend: Postgres 16 migration is complete \u2014 production upgraded "
     "successfully during last night's maintenance window, zero downtime, all health "
     "checks green. JSONB query performance is noticeably faster already. Closing this "
     "out.",
     15.0, "", {"channel": "#eng-backend"}),


    # ALEX CHEN — Backend Engineer, Payments

    #  Thread A: Payment service async migration (BLOCKED) 
    ("alex", "github",
     "PR #388 opened by alex: 'refactor: migrate payment service to async handlers' \u2014 "
     "Large refactor of the payments module to reduce timeout errors under load. Review "
     "requested from @priya and @rohan. Status: open.",
     4.5, "https://github.com/org/payments/pull/388",
     {"type": "pull_request", "state": "open", "pr_number": 388}),

    ("alex", "notion",
     "Payment Service Migration Plan (edited by alex): Phase 1 complete \u2014 async "
     "handlers deployed to staging, latency improved by 40%. Phase 2 needs a decision: "
     "webhook retry policy. Two options \u2014 exponential backoff (preferred, simpler) "
     "vs a dead-letter queue (more robust, more infra). Decision needed from Rohan before "
     "Phase 2 can proceed.",
     3.8, "https://notion.so/payments-migration-plan", {"type": "page_edit"}),

    ("alex", "slack",
     "alex in #product: Payment service migration update \u2014 async handlers are live "
     "on staging and looking solid. We're blocked on finalizing the webhook retry policy "
     "before we can move to Phase 2 and ship to production.",
     3.4, "", {"channel": "#product"}),

    ("alex", "slack",
     "alex \u2192 rohan: Quick question on the payments refactor \u2014 any preference "
     "between exponential backoff and a dead-letter queue for failed webhooks? I lean "
     "toward backoff for simplicity given our current volume, but wanted your input "
     "before deciding.",
     2.6, "", {"channel": "dm-alex-rohan"}),

    ("alex", "github",
     "Review comment on PR #388 by rohan: 'Looks clean overall. I'd go with exponential "
     "backoff capped at 4 retries \u2014 a DLQ feels like overkill for our current webhook "
     "volume. Approving once that's wired in.'",
     1.3, "https://github.com/org/payments/pull/388#discussion_r2",
     {"type": "review_comment", "pr_number": 388}),

    #  Thread B: Partner API rate limit increase (IN_FLIGHT) 
    ("alex", "email",
     "From: partnerops@bigretailco.com To: alex@company.com \u2014 Hi Alex, as our "
     "integration volume grows we're starting to hit your API's rate limits during peak "
     "hours (around 2-4pm). Could you look into increasing our quota? This is becoming a "
     "blocker for our holiday season prep.",
     6.0, "", {"from": "BigRetailCo", "subject": "API rate limit \u2014 BigRetailCo integration"}),

    ("alex", "slack",
     "alex \u2192 infra-team: BigRetailCo (one of our larger partners) is hitting our API "
     "rate limits during peak hours and it's blocking their holiday prep. What's the "
     "process for granting a higher quota tier to a specific partner?",
     5.2, "", {"channel": "#infra-requests"}),

    ("alex", "email",
     "From: alex@company.com To: cloud-support@provider.com \u2014 Submitting a request "
     "to increase our API gateway quota for partner tier 'enterprise-2' from 500 rps to "
     "1500 rps. This is needed to support a growing integration partner ahead of their "
     "seasonal traffic spike.",
     4.1, "", {"from": "alex", "subject": "Quota increase request \u2014 enterprise-2 tier"}),

    ("alex", "slack",
     "infra-team \u2192 alex: Got your quota request \u2014 a tier upgrade like this needs "
     "VP sign-off since it affects our shared rate-limiting pool. I've forwarded it for "
     "approval, still pending as of today. Will ping you once it's approved.",
     2.3, "", {"channel": "#infra-requests"}),

    #  Thread C: On-call rotation handoff (DONE / STALE) 
    ("alex", "slack",
     "alex in #on-call: This week's on-call summary \u2014 3 minor incidents, all resolved "
     "within SLA. No major outages. Escalation runbook held up well for the "
     "payments-latency alert on Tuesday.",
     15.0, "", {"channel": "#on-call"}),

    ("alex", "notion",
     "On-Call Runbook (edited by alex): Updated escalation contacts for the payments and "
     "auth services. Added a new troubleshooting section for the Redis cache timeout "
     "alert that fired twice this week.",
     14.2, "https://notion.so/on-call-runbook", {"type": "page_edit"}),

    ("alex", "slack",
     "alex \u2192 on-call-next: Handoff complete for this week's rotation \u2014 runbook is "
     "up to date, no open incidents, nothing pending. You're all set for the week ahead!",
     10.5, "", {"channel": "dm-alex-oncall-next"}),


    # MARIA SANTOS — Product Designer

    #  Thread A: Onboarding flow redesign (BLOCKED) 
    ("maria", "notion",
     "Onboarding Flow Redesign v3 (edited by maria): Updated the Figma flow based on last "
     "round of feedback \u2014 simplified from 6 steps to 4. Open comments on step 3 "
     "(account verification) still need resolution before this can move to development.",
     5.4, "https://notion.so/onboarding-redesign-v3", {"type": "page_edit"}),

    ("maria", "slack",
     "maria \u2192 jordan: For the onboarding redesign, I really need the latest user "
     "research on where people are dropping off in the current flow \u2014 especially "
     "around step 3. Do we have that data yet?",
     4.6, "", {"channel": "dm-maria-jordan"}),

    ("maria", "slack",
     "jordan \u2192 maria: The research team is still analyzing the drop-off data, ETA is "
     "end of next week. I know that's frustrating \u2014 I'll flag it as a priority for "
     "them.",
     3.9, "", {"channel": "dm-maria-jordan"}),

    ("maria", "notion",
     "Onboarding Flow Redesign v3 \u2014 Comment thread on Step 3 (account verification): "
     "4 open questions flagged by the team \u2014 should email verification be mandatory "
     "before proceeding? Should we offer a 'skip for now' option? Awaiting research data "
     "before finalizing.",
     2.8, "https://notion.so/onboarding-redesign-v3#step3-comments", {"type": "comment"}),

    ("maria", "slack",
     "maria in #design: Status update \u2014 the onboarding redesign is currently blocked "
     "on user research data for the drop-off analysis. Can't finalize step 3 until that "
     "lands. Will pick this back up as soon as it's available.",
     1.7, "", {"channel": "#design"}),

    #  Thread B: Design system color token migration (IN_FLIGHT) 
    ("maria", "notion",
     "Design Tokens v2 (edited by maria): New color palette finalized \u2014 includes "
     "updated semantic tokens for success/warning/error states and a refreshed neutral "
     "scale for better dark-mode contrast.",
     8.3, "https://notion.so/design-tokens-v2", {"type": "page_edit"}),

    ("maria", "slack",
     "maria in #eng-frontend: Heads up \u2014 rolling out the new design token palette "
     "(v2). I've documented all the mappings from old tokens to new ones in Notion. "
     "Planning a phased rollout starting with the marketing site.",
     6.5, "", {"channel": "#eng-frontend"}),

    ("maria", "github",
     "PR #205 opened by maria (frontend repo): 'style: migrate to design-tokens-v2' \u2014 "
     "Updates tokens.css with the new semantic color palette. Marketing site components "
     "updated first as a pilot.",
     4.7, "https://github.com/org/frontend/pull/205",
     {"type": "pull_request", "state": "open", "pr_number": 205}),

    ("maria", "slack",
     "frontend-eng \u2192 maria: PR #205 is merged and live on staging \u2014 the new "
     "tokens look great on the marketing pages. Ready to start migrating the app shell "
     "whenever you are.",
     2.1, "", {"channel": "#eng-frontend"}),

    #  Thread C: Accessibility audit for checkout (DONE) 
    ("maria", "notion",
     "Checkout Accessibility Audit \u2014 Final Report (maria): Completed a full WCAG 2.1 "
     "AA audit of the checkout flow. Found 3 critical issues (contrast ratios, missing "
     "form labels, focus order) and 5 minor issues. Full report with screenshots "
     "attached.",
     21.0, "https://notion.so/checkout-a11y-audit-final", {"type": "page_edit"}),

    ("maria", "slack",
     "maria in #design: Just finished the accessibility audit for checkout \u2014 found 3 "
     "critical contrast and labeling issues that need fixing before our next release. "
     "Filed tickets for engineering, report is in Notion.",
     18.5, "", {"channel": "#design"}),

    ("maria", "github",
     "PR #198 merged: 'fix: resolve checkout accessibility issues \u2014 contrast, labels, "
     "focus order' \u2014 Addresses all 3 critical findings from Maria's audit. Verified "
     "against WCAG 2.1 AA with axe-core.",
     15.2, "https://github.com/org/frontend/pull/198",
     {"type": "pull_request", "state": "merged", "pr_number": 198}),

    ("maria", "slack",
     "maria in #design: All 3 critical accessibility issues from the checkout audit are "
     "now resolved and verified \u2014 closing this out. Great turnaround from the eng "
     "team!",
     14.0, "", {"channel": "#design"}),


    # JORDAN LEE — Product Manager

    #  Thread A: Q3 roadmap prioritization (BLOCKED) 
    ("jordan", "email",
     "From: jordan@company.com To: leadership@company.com \u2014 Sharing the draft Q3 "
     "roadmap for review ahead of next week's planning cycle. Two big items competing for "
     "the top slot: the onboarding redesign and the partner API scalability work. Would "
     "appreciate feedback by Friday so we can finalize priorities.",
     6.3, "", {"from": "jordan", "subject": "Q3 Roadmap \u2014 Draft for Review", "to": "leadership"}),

    ("jordan", "slack",
     "jordan in #leadership: Following up on the Q3 roadmap doc I sent \u2014 really need "
     "feedback by Friday on the onboarding-redesign vs partner-API-scalability "
     "prioritization call. Both teams are ready to start, just need direction.",
     4.8, "", {"channel": "#leadership"}),

    ("jordan", "email",
     "From: vp-product@company.com To: jordan@company.com \u2014 Thanks for putting this "
     "together. Before we lock priorities, I'd like to discuss both options in person \u2014 "
     "there's a customer commitment tied to the partner API work that might change the "
     "calculus. Can we grab 30 minutes this week?",
     3.0, "", {"from": "VP Product", "subject": "Re: Q3 Roadmap \u2014 Draft for Review"}),

    ("jordan", "slack",
     "jordan in #leadership: Q3 roadmap is currently on hold pending an alignment "
     "discussion with the VP \u2014 there's a customer commitment that might shift our "
     "priorities. Will share the final roadmap as soon as that conversation happens.",
     1.2, "", {"channel": "#leadership"}),

    ("jordan", "calendar",
     "Meeting scheduled: 'Q3 Roadmap Alignment \u2014 Jordan & VP Product', 30 minutes. "
     "Agenda: resolve prioritization between onboarding redesign and partner API "
     "scalability work.",
     0.8, "", {"type": "meeting", "duration_minutes": 30}),

    #  Thread B: Customer feedback synthesis (IN_FLIGHT) 
    ("jordan", "email",
     "From: support-lead@company.com To: jordan@company.com \u2014 Forwarding this month's "
     "top customer complaints for your roadmap input. Biggest themes seem to be around "
     "onboarding confusion and slow checkout \u2014 full ticket export attached.",
     7.1, "", {"from": "support-lead", "subject": "Monthly customer feedback digest"}),

    ("jordan", "notion",
     "Customer Feedback Synthesis \u2014 Q3 (edited by jordan, ~70% complete): Categorized "
     "140 support tickets into 5 themes. Top two by volume: onboarding confusion (38%) "
     "and checkout performance (24%). Still need: cross-reference with NPS survey "
     "comments before finalizing recommendations.",
     4.4, "https://notion.so/customer-feedback-synthesis-q3", {"type": "page_edit", "completion": 70}),

    ("jordan", "slack",
     "jordan \u2192 maria: For the feedback synthesis doc, onboarding confusion is by far "
     "the top complaint theme \u2014 wanted to get your take on whether this lines up with "
     "what you're seeing in the redesign research.",
     3.2, "", {"channel": "dm-jordan-maria"}),

    ("jordan", "notion",
     "Customer Feedback Synthesis \u2014 Q3 (edited by jordan): Added NPS survey "
     "cross-reference \u2014 onboarding confusion theme is corroborated, appears in 31% of "
     "detractor comments too. Recommendation section drafted, ready for review.",
     1.9, "https://notion.so/customer-feedback-synthesis-q3", {"type": "page_edit", "completion": 90}),

    #  Thread C: Vendor contract renewal (DONE / STALE) 
    ("jordan", "email",
     "From: vendor-sales@analyticsco.com To: jordan@company.com \u2014 Hi Jordan, sending "
     "over the renewal terms for our analytics platform contract \u2014 renewal date is "
     "approaching in 3 weeks. New pricing reflects a 12% increase due to expanded usage "
     "tiers.",
     25.0, "", {"from": "AnalyticsCo", "subject": "Contract Renewal \u2014 Analytics Platform"}),

    ("jordan", "slack",
     "jordan \u2192 procurement: Got the renewal terms from AnalyticsCo \u2014 12% price "
     "increase. Given our usage has grown a lot this year that's roughly in line, but want "
     "to push back and see if we can negotiate a smaller increase or get additional seats "
     "included.",
     22.0, "", {"channel": "dm-jordan-procurement"}),

    ("jordan", "email",
     "From: vendor-sales@analyticsco.com To: jordan@company.com \u2014 Following up on our "
     "call \u2014 we can offer a 7% increase instead of 12% if you commit to a 2-year term, "
     "plus 5 additional seats included at no extra cost. Let us know if that works.",
     18.5, "", {"from": "AnalyticsCo", "subject": "Re: Contract Renewal \u2014 Analytics Platform"}),

    ("jordan", "slack",
     "jordan in #procurement: Quick update \u2014 the AnalyticsCo contract renewal is "
     "signed and finalized. Got the increase down to 7% with a 2-year term and 5 extra "
     "seats included. Closing this out.",
     16.0, "", {"channel": "#procurement"}),
]


def main():
    dataset = {
        "$schema_version": 1,
        "description": (
            "Synthetic activity dataset for Context Handoff Protocol demos. "
            "Timestamps are expressed as `days_ago` (float, relative to load time) "
            "so the dataset always appears fresh regardless of when it's loaded."
        ),
        "users": USERS,
        "events": [
            {
                "user_id": u,
                "source": src,
                "content": content,
                "days_ago": days_ago,
                "url": url,
                "metadata": meta,
            }
            for (u, src, content, days_ago, url, meta) in EVENTS
        ],
    }

    out_path = Path(__file__).parent / "synthetic_dataset.json"
    out_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False))

    # Summary
    from collections import Counter
    by_user = Counter(e["user_id"] for e in dataset["events"])
    by_source = Counter(e["source"] for e in dataset["events"])
    print(f"Wrote {out_path}")
    print(f"  Users:  {len(dataset['users'])}")
    print(f"  Events: {len(dataset['events'])}")
    print(f"  By user:   {dict(by_user)}")
    print(f"  By source: {dict(by_source)}")


if __name__ == "__main__":
    main()
