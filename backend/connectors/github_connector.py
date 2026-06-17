"""
connectors/github_connector.py

Fetches PRs, review comments, and issues authored by a user from GitHub.
Requires a personal access token with repo scope.

Set GITHUB_TOKEN in .env to activate.
The user_id should be the GitHub username.
"""
from datetime import datetime, timedelta, timezone

from backend.connectors.base import BaseConnector, RawEvent


class GitHubConnector(BaseConnector):
    def __init__(self, token: str):
        self._token = token

    async def fetch(self, user_id: str, days_back: int = 30) -> list[RawEvent]:
        import asyncio
        from github import Github, GithubException

        loop = asyncio.get_running_loop()
        events = await loop.run_in_executor(
            None, self._fetch_sync, user_id, days_back
        )
        return events

    def _fetch_sync(self, username: str, days_back: int) -> list[RawEvent]:
        from github import Github, GithubException

        gh     = Github(self._token)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
        events: list[RawEvent] = []

        try:
            user = gh.get_user(username)
        except GithubException:
            return []

        #  Pull Requests 
        query = f"author:{username} type:pr updated:>{cutoff.date().isoformat()}"
        for pr in gh.search_issues(query=query)[:50]:
            ts = pr.created_at.replace(tzinfo=None)
            events.append(RawEvent(
                source="github",
                content=(
                    f"PR #{pr.number}: '{pr.title}' in {pr.repository.full_name}. "
                    f"State: {pr.state}. Body: {(pr.body or '')[:300]}"
                ),
                timestamp=ts,
                url=pr.html_url,
                metadata={
                    "type":       "pull_request",
                    "repo":       pr.repository.full_name,
                    "pr_number":  pr.number,
                    "state":      pr.state,
                },
            ))

        #  Review Comments 
        for repo in user.get_repos()[:20]:
            try:
                for comment in repo.get_pulls_review_comments():
                    if comment.user.login != username:
                        continue
                    if comment.created_at < cutoff:
                        continue
                    events.append(RawEvent(
                        source="github",
                        content=(
                            f"Review comment on PR in {repo.full_name}: "
                            f"{comment.body[:400]}"
                        ),
                        timestamp=comment.created_at.replace(tzinfo=None),
                        url=comment.html_url,
                        metadata={
                            "type": "review_comment",
                            "repo": repo.full_name,
                        },
                    ))
            except Exception:
                continue

        return events

    @property
    def source_name(self) -> str:
        return "github"
