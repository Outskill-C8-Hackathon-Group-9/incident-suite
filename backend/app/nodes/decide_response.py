from app.llm import get_decision_reasoner
from app.nodes._trace import trace_event
from app.state import IncidentState


def decide_response_node(state: IncidentState) -> dict:
    incident = state["incident"]
    decision = get_decision_reasoner().decide(incident)
    return {
        "decision": decision,
        "trace": [
            trace_event(
                "decide_response",
                f"Chose the {decision.path} path with {decision.confidence:.2f} confidence.",
                {"decision": decision.model_dump()},
            )
        ],
    }
