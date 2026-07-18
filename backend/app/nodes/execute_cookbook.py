from app.models import ExecutionResult
from app.nodes._trace import trace_event
from app.state import IncidentState


def execute_cookbook_node(state: IncidentState) -> dict:
    incident = state["incident"]
    steps_run = [f"Ran step {item.step}: {item.action}" for item in incident.cookbook.items]
    execution = ExecutionResult(
        steps_run=steps_run,
        summary=f"Executed {len(steps_run)} cookbook step(s) for {incident.service}.",
    )
    return {
        "execution": execution,
        "trace": [
            trace_event(
                "execute_cookbook",
                execution.summary,
                {"execution": execution.model_dump()},
            )
        ],
    }
