from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Literal

Severity = Literal["critical", "high", "medium", "low", "info"]
ResponsePath = Literal["remediative", "investigative"]


class ModelMixin:
    def model_dump(self) -> dict:
        return asdict(self)

    def model_copy(self, update: dict | None = None):
        return replace(self, **(update or {}))


@dataclass
class CookbookStep(ModelMixin):
    step: int
    action: str
    done_when: str


@dataclass
class Cookbook(ModelMixin):
    title: str
    items: list[CookbookStep]

    @classmethod
    def from_dict(cls, data: dict) -> "Cookbook":
        return cls(
            title=data["title"],
            items=[CookbookStep(**item) for item in data.get("items", [])],
        )


@dataclass
class IncidentInput(ModelMixin):
    summary: str
    severity: Severity
    host: str
    service: str
    cookbook: Cookbook
    expected_verification_success: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "IncidentInput":
        return cls(
            summary=data["summary"],
            severity=data["severity"],
            host=data["host"],
            service=data["service"],
            cookbook=Cookbook.from_dict(data["cookbook"]),
            expected_verification_success=data.get("expected_verification_success", True),
        )

    @classmethod
    def model_validate_json(cls, raw: str) -> "IncidentInput":
        return cls.from_dict(json.loads(raw))


@dataclass
class Decision(ModelMixin):
    path: ResponsePath
    confidence: float
    policy_reason: str


@dataclass
class Engineer(ModelMixin):
    name: str
    email: str
    slack_user_id: str = ""
    jira_account_id: str = ""


@dataclass
class JiraTicket(ModelMixin):
    key: str
    url: str
    summary: str
    severity: Severity
    status: str
    assignee: str = ""


@dataclass
class ExecutionResult(ModelMixin):
    steps_run: list[str]
    summary: str


@dataclass
class VerificationResult(ModelMixin):
    success: bool
    details: str


@dataclass
class NotificationResult(ModelMixin):
    channel: str
    team_permalink: str
    dm_permalink: str = ""
    text_preview: str = ""
