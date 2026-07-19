from app.decision_engine import decide_all
from app.nodes._trace import trace_event
from app.state import IncidentState


def decide_response_node(state: IncidentState) -> dict:
    decisions = decide_all(state)
    remediative = sum(1 for d in decisions if d["path"] == "remediative")
    investigative = len(decisions) - remediative
    return {
        "decisions": decisions,
        "trace": [
            trace_event(
                "decide_response",
                f"Decided {len(decisions)} incident(s): {remediative} remediative, "
                f"{investigative} investigative.",
                {"decisions": decisions},
            )
        ],
    }
