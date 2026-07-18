from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.models import (
    Decision,
    Engineer,
    ExecutionResult,
    IncidentInput,
    JiraTicket,
    NotificationResult,
    VerificationResult,
)


class IncidentState(TypedDict, total=False):
    incident: IncidentInput
    decision: Decision
    ticket: JiraTicket
    assigned_engineer: Engineer
    execution: ExecutionResult
    verification: VerificationResult
    notification: NotificationResult
    trace: Annotated[list[dict], operator.add]
