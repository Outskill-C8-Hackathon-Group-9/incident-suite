import itertools
from app.models import JiraTicket
from app.config import config


class MockJiraClient:
    """Drop-in mock. To go real: replace create_ticket() with a POST to
    /rest/api/3/issue (the `jira` package or httpx). Keep the JiraTicket return type."""

    _counter = itertools.count(101)

    def create_ticket(self, *, summary: str, severity: str, issue_id: str, description: str) -> JiraTicket:
        num = next(self._counter)
        key = f"{config.JIRA_PROJECT_KEY}-{num}"
        url = f"https://your-org.atlassian.net/browse/{key}"
        print(f"[MOCK JIRA] created {key}  ({severity})  {summary}")
        return JiraTicket(key=key, url=url, summary=summary, severity=severity, issue_id=issue_id)