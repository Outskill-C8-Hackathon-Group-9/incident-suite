from __future__ import annotations

import base64
import itertools
import json
from urllib import error, parse, request

from app.config import config
from app.models import Engineer, JiraTicket


def _adf_text(text: str) -> dict:
    lines = text.splitlines() or [" "]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "\n".join(lines)}]}
        ],
    }


class JiraTicketManager:
    _counter = itertools.count(101)

    def __init__(self) -> None:
        self.last_create_was_real = False
        self.last_assign_was_real = False

    def create_ticket(self, *, summary: str, description: str, severity: str) -> JiraTicket:
        if config.use_real_jira:
            try:
                ticket = self._create_ticket_real(summary=summary, description=description, severity=severity)
                self.last_create_was_real = True
                return ticket
            except Exception as exc:
                print(f"[JIRA] real create failed, falling back to mock: {exc}")
        self.last_create_was_real = False
        return self._create_ticket_mock(summary=summary, description=description, severity=severity)

    def assign_ticket(self, ticket: JiraTicket, engineer: Engineer) -> JiraTicket:
        # Real-Jira path: PUT the assignee, then refetch the issue so the
        # returned ticket carries the assignee displayName that Jira itself
        # confirmed (rather than the local Engineer.name we passed in).
        if config.use_real_jira:
            try:
                account_id = self._resolve_assignable_account_id(engineer)
                if not account_id:
                    raise RuntimeError(
                        f"Could not resolve an assignable Jira account for engineer '{engineer.name}'."
                    )
                self._request(
                    method="PUT",
                    path=f"/rest/api/3/issue/{ticket.key}/assignee",
                    payload={"accountId": account_id},
                )
                confirmed = self._fetch_ticket(ticket.key)
                if confirmed is not None:
                    self.last_assign_was_real = True
                    return confirmed.model_copy(update={"status": "Assigned"})
                self.last_assign_was_real = True
                return ticket.model_copy(
                    update={"assignee": engineer.name, "status": "Assigned"}
                )
            except Exception as exc:
                print(f"[JIRA] real assign failed, falling back to mock: {exc}")
        self.last_assign_was_real = False
        print(f"[MOCK JIRA] assigned {ticket.key} to {engineer.name}")
        return ticket.model_copy(update={"assignee": engineer.name, "status": "Assigned"})

    def find_open_ticket_by_summary(self, *, summary: str) -> JiraTicket | None:
        if not config.use_real_jira:
            return None
        try:
            issues = self._search_issues(
                jql=(
                    f'project = "{config.JIRA_PROJECT_KEY}" '
                    'AND labels = incident-suite '
                    'AND statusCategory != Done '
                    "ORDER BY created DESC"
                ),
                max_results=25,
                fields=["summary", "status", "assignee", "labels"],
            )
        except Exception as exc:
            print(f"[JIRA] duplicate check skipped: {exc}")
            return None
        for issue in issues:
            issue_summary = issue.get("fields", {}).get("summary", "")
            if issue_summary == summary:
                return self._ticket_from_issue(issue)
        return None

    def next_round_robin_engineer(self, engineers: list[Engineer]) -> Engineer | None:
        if not engineers:
            return None
        if not config.use_real_jira:
            return engineers[0]

        try:
            issues = self._search_issues(
                jql=(
                    f'project = "{config.JIRA_PROJECT_KEY}" '
                    'AND labels = incident-suite '
                    "ORDER BY created DESC"
                ),
                max_results=50,
                fields=["assignee"],
            )
        except Exception as exc:
            print(f"[JIRA] round-robin history lookup skipped: {exc}")
            return engineers[0]
        # Build a map of local jira_account_id -> engineer so we can match
        # Jira's canonical accountId against what we have in ENGINEER_MAPPING.
        by_account_id = {e.jira_account_id: e for e in engineers if e.jira_account_id}
        for issue in issues:
            assignee = issue.get("fields", {}).get("assignee") or {}
            account_id = assignee.get("accountId", "")
            if not account_id:
                continue
            matched = by_account_id.get(account_id)
            if matched is None:
                # Jira knows about an assignee we don't have in the mapping.
                # Surface it so the user can fix ENGINEER_MAPPING in .env.
                print(
                    f"[JIRA] round-robin: Jira assignee accountId={account_id} "
                    f"is not in ENGINEER_MAPPING; using first engineer."
                )
                return engineers[0]
            index = engineers.index(matched)
            return engineers[(index + 1) % len(engineers)]
        return engineers[0]

    def update_ticket(self, ticket: JiraTicket, *, note: str) -> JiraTicket:
        if config.use_real_jira:
            try:
                self._request(
                    method="PUT",
                    path=f"/rest/api/3/issue/{ticket.key}",
                    payload={"update": {"labels": [{"add": "incident-suite"}]}},
                )
                print(f"[JIRA] updated {ticket.key}: {note}")
                return ticket
            except Exception as exc:
                print(f"[JIRA] real update failed, falling back to mock: {exc}")
        print(f"[MOCK JIRA] updated {ticket.key}: {note}")
        return ticket

    def close_ticket(self, ticket: JiraTicket, *, note: str) -> JiraTicket:
        if config.use_real_jira and config.JIRA_DONE_TRANSITION_ID:
            try:
                self._request(
                    method="POST",
                    path=f"/rest/api/3/issue/{ticket.key}/transitions",
                    payload={"transition": {"id": config.JIRA_DONE_TRANSITION_ID}},
                )
                print(f"[JIRA] closed {ticket.key}: {note}")
                return ticket.model_copy(update={"status": "Closed"})
            except Exception as exc:
                print(f"[JIRA] real close failed, falling back to mock: {exc}")
        print(f"[MOCK JIRA] closed {ticket.key}: {note}")
        return ticket.model_copy(update={"status": "Closed"})

    def _create_ticket_real(self, *, summary: str, description: str, severity: str) -> JiraTicket:
        fields = {
            "project": {"key": config.JIRA_PROJECT_KEY},
            "summary": summary,
            "description": _adf_text(description),
            "issuetype": {"name": config.JIRA_ISSUE_TYPE},
            "labels": ["incident-suite", severity],
        }
        if config.JIRA_PRIORITY_ID:
            fields["priority"] = {"id": config.JIRA_PRIORITY_ID}

        payload = {"fields": fields}
        data = self._request(method="POST", path="/rest/api/3/issue", payload=payload)
        key = data["key"]
        return JiraTicket(
            key=key,
            url=f"{config.JIRA_BASE_URL}/browse/{key}",
            summary=summary,
            severity=severity,
            status="Open",
        )

    def _create_ticket_mock(self, *, summary: str, description: str, severity: str) -> JiraTicket:
        num = next(self._counter)
        key = f"{config.JIRA_PROJECT_KEY}-{num}"
        print(f"[MOCK JIRA] created {key} ({severity}) {summary}")
        print(description)
        return JiraTicket(
            key=key,
            url=f"{config.JIRA_BASE_URL or 'https://example.atlassian.net'}/browse/{key}",
            summary=summary,
            severity=severity,
            status="Open",
        )

    def _request(self, *, method: str, path: str, payload: dict | None = None) -> dict:
        raw_auth = f"{config.JIRA_USER_EMAIL}:{config.JIRA_API_TOKEN}".encode("utf-8")
        auth = base64.b64encode(raw_auth).decode("utf-8")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            f"{config.JIRA_BASE_URL}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    def _search_issues(self, *, jql: str, max_results: int, fields: list[str]) -> list[dict]:
        data = self._request(
            method="POST",
            path="/rest/api/3/search/jql",
            payload={
                "jql": jql,
                "maxResults": max_results,
                "fields": fields,
            },
        )
        return data.get("issues", [])

    def _fetch_ticket(self, key: str) -> JiraTicket | None:
        """Fetch a single issue by key and project it to a JiraTicket.

        Returns None if the request fails (so callers can fall back).
        """
        try:
            data = self._request(
                method="GET",
                path=f"/rest/api/3/issue/{key}",
            )
        except Exception as exc:
            print(f"[JIRA] fetch {key} failed: {exc}")
            return None
        if not data:
            return None
        return self._ticket_from_issue(data)

    def _resolve_assignable_account_id(self, engineer: Engineer) -> str:
        candidates: list[dict] = []
        for query in self._assignee_queries(engineer):
            users = self._search_assignable_users(query=query)
            candidates.extend(users)

        unique_by_account: dict[str, dict] = {}
        for user in candidates:
            account_id = user.get("accountId", "")
            if account_id:
                unique_by_account[account_id] = user

        if engineer.jira_account_id and engineer.jira_account_id in unique_by_account:
            return engineer.jira_account_id

        for user in unique_by_account.values():
            if user.get("displayName", "").strip().lower() == engineer.name.strip().lower():
                return user["accountId"]

        if len(unique_by_account) == 1:
            return next(iter(unique_by_account))

        return engineer.jira_account_id

    def _assignee_queries(self, engineer: Engineer) -> list[str]:
        queries: list[str] = []
        if engineer.name:
            queries.append(engineer.name)
        if engineer.email:
            queries.append(engineer.email)
        if engineer.jira_account_id:
            queries.append(engineer.jira_account_id)
        return list(dict.fromkeys(query for query in queries if query))

    def _search_assignable_users(self, *, query: str) -> list[dict]:
        encoded_query = parse.urlencode(
            {
                "project": config.JIRA_PROJECT_KEY,
                "query": query,
                "maxResults": 50,
            }
        )
        data = self._request(
            method="GET",
            path=f"/rest/api/3/user/assignable/search?{encoded_query}",
        )
        if isinstance(data, list):
            return data
        return []

    def _ticket_from_issue(self, issue: dict) -> JiraTicket:
        fields = issue.get("fields", {})
        assignee = fields.get("assignee") or {}
        status = fields.get("status") or {}
        labels = fields.get("labels") or []
        severity = "info"
        for label in labels:
            if label in {"critical", "high", "medium", "low", "info"}:
                severity = label
                break
        return JiraTicket(
            key=issue["key"],
            url=f"{config.JIRA_BASE_URL}/browse/{issue['key']}",
            summary=fields.get("summary", ""),
            severity=severity,
            status=status.get("name", "Open"),
            assignee=assignee.get("displayName", ""),
        )
