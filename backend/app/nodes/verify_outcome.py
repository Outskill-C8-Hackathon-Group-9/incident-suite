from app.models import VerificationResult
from app.nodes._trace import trace_event
from app.state import IncidentState


def verify_outcome_node(state: IncidentState) -> dict:
    incident = state["incident"]
    success = incident.expected_verification_success
    details = (
        f"Verification passed for {incident.host}; the demo marked the automated fix as successful."
        if success
        else f"Verification failed for {incident.host}; a human should continue the investigation."
    )
    verification = VerificationResult(success=success, details=details)
    return {
        "verification": verification,
        "trace": [
            trace_event(
                "verify_outcome",
                details,
                {"verification": verification.model_dump()},
            )
        ],
    }
