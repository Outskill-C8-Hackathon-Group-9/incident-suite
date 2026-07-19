from app.models import VerificationResult
from app.nodes._trace import trace_event
from app.state import IncidentState


def verify_outcome_node(state: IncidentState) -> dict:
    remediations_by_id = {r["issue_id"]: r for r in state.get("remediations", []) or []}
    tickets = state.get("tickets", []) or []
    trace_lines: list[str] = []

    for entry in tickets:
        if entry["decision"]["path"] != "remediative":
            continue
        remediation = remediations_by_id.get(entry["issue_id"])
        needs_approval = bool(remediation and remediation.get("requires_approval"))
        success = not needs_approval
        details = (
            "Fix applied automatically; verification passed."
            if success
            else f"Fix for {entry['title']} requires human approval before it can be considered verified."
        )
        entry["verification"] = VerificationResult(success=success, details=details).model_dump()
        trace_lines.append(f"{entry['title']}: {'passed' if success else 'needs approval'}")

    return {
        "tickets": tickets,
        "trace": [
            trace_event(
                "verify_outcome",
                "; ".join(trace_lines) or "No remediative tickets to verify.",
                {},
            )
        ],
    }
