from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
IssueCategory = Literal[
    "memory_leak", "deployment_regression", "database", "network",
    "cpu_saturation", "timeout", "auth", "config", "unknown",
]


# ---- parsing layer ----
class LogEntry(BaseModel):
    line_no: int
    timestamp: Optional[str] = None
    level: Optional[str] = None
    service: Optional[str] = None
    message: str
    raw: str


class ErrorCluster(BaseModel):
    signature: str
    count: int
    level: str
    example_service: Optional[str] = None
    sample_lines: list[str]
    line_numbers: list[int]


# ---- classifier output (LLM structured output) ----
class DetectedIssue(BaseModel):
    id: str = Field(description="short slug id, e.g. 'oom-order-service'")
    title: str
    category: IssueCategory
    severity: Severity
    affected_service: str
    summary: str = Field(description="1-2 sentence plain-English explanation")
    evidence: list[str] = Field(description="log lines that justify this issue")


class ClassifierOutput(BaseModel):
    issues: list[DetectedIssue]


# ---- remediation output (LLM structured output) ----
class Remediation(BaseModel):
    issue_id: str
    fix_summary: str
    rationale: str = Field(description="why this addresses the root cause")
    suggested_command: str = Field(description="a concrete, SAFE command or config change")
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool
    grounded_in: list[str] = Field(
        default_factory=list,
        description="titles of runbooks retrieved from the knowledge base that informed this fix",
    )


class RemediationOutput(BaseModel):
    remediations: list[Remediation]


# ---- cookbook output (LLM structured output) ----
class ChecklistItem(BaseModel):
    step: int
    action: str
    owner_hint: str = Field(description="which role/team, e.g. 'on-call SRE'")
    done_when: str = Field(description="how to know the step succeeded")


class Cookbook(BaseModel):
    title: str
    items: list[ChecklistItem]


# ---- integration results ----
class JiraTicket(BaseModel):
    key: str
    url: str
    summary: str
    severity: Severity
    issue_id: str


class SlackResult(BaseModel):
    channel: str
    ts: str
    permalink: str
    text_preview: str