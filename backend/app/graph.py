from app.nodes.assign_ticket import assign_ticket_node
from app.nodes.close_ticket import close_ticket_node
from app.nodes.create_ticket import create_ticket_node
from app.nodes.decide_response import decide_response_node
from app.nodes.execute_cookbook import execute_cookbook_node
from app.nodes.notify_slack import notify_slack_node
from app.nodes.verify_outcome import verify_outcome_node
from app.state import IncidentState

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
except ImportError:
    MemorySaver = None
    StateGraph = None
    START = "START"
    END = "END"


def _route_after_decision(state: IncidentState) -> str:
    return "create_ticket"


def _route_after_ticket(state: IncidentState) -> str:
    if state["decision"].path == "remediative":
        return "execute_cookbook"
    return "assign_ticket"


def _route_after_verification(state: IncidentState) -> str:
    if state["verification"].success:
        return "close_ticket"
    return "notify_slack"


def build_graph():
    if StateGraph is None:
        return _build_fallback_graph()

    graph = StateGraph(IncidentState)

    graph.add_node("decide_response", decide_response_node)
    graph.add_node("create_ticket", create_ticket_node)
    graph.add_node("execute_cookbook", execute_cookbook_node)
    graph.add_node("verify_outcome", verify_outcome_node)
    graph.add_node("close_ticket", close_ticket_node)
    graph.add_node("assign_ticket", assign_ticket_node)
    graph.add_node("notify_slack", notify_slack_node)

    graph.add_edge(START, "decide_response")
    graph.add_conditional_edges(
        "decide_response",
        _route_after_decision,
        {"create_ticket": "create_ticket"},
    )
    graph.add_conditional_edges(
        "create_ticket",
        _route_after_ticket,
        {
            "execute_cookbook": "execute_cookbook",
            "assign_ticket": "assign_ticket",
        },
    )
    graph.add_edge("execute_cookbook", "verify_outcome")
    graph.add_conditional_edges(
        "verify_outcome",
        _route_after_verification,
        {
            "close_ticket": "close_ticket",
            "notify_slack": "notify_slack",
        },
    )
    graph.add_edge("close_ticket", "notify_slack")
    graph.add_edge("assign_ticket", "notify_slack")
    graph.add_edge("notify_slack", END)

    return graph.compile(checkpointer=MemorySaver())


class _StateSnapshot:
    def __init__(self, values: dict):
        self.values = values


class _FallbackGraph:
    def __init__(self) -> None:
        self._states: dict[str, dict] = {}

    async def astream(self, initial_state: dict, cfg: dict, stream_mode: str = "updates"):
        state = dict(initial_state)
        thread_id = cfg.get("configurable", {}).get("thread_id", "default")
        current = "decide_response"
        while current != END:
            update = _FALLBACK_NODES[current](state)
            if "trace" in update:
                state["trace"] = state.get("trace", []) + update["trace"]
                merged_update = dict(update)
            else:
                merged_update = update
            for key, value in update.items():
                if key == "trace":
                    continue
                state[key] = value
            self._states[thread_id] = dict(state)
            yield {current: merged_update}
            current = _fallback_next_node(current, state)

    def get_state(self, cfg: dict) -> _StateSnapshot:
        thread_id = cfg.get("configurable", {}).get("thread_id", "default")
        return _StateSnapshot(self._states.get(thread_id, {}))


_FALLBACK_NODES = {
    "decide_response": decide_response_node,
    "create_ticket": create_ticket_node,
    "execute_cookbook": execute_cookbook_node,
    "verify_outcome": verify_outcome_node,
    "close_ticket": close_ticket_node,
    "assign_ticket": assign_ticket_node,
    "notify_slack": notify_slack_node,
}


def _fallback_next_node(current: str, state: IncidentState) -> str:
    if current == "decide_response":
        return "create_ticket"
    if current == "create_ticket":
        return _route_after_ticket(state)
    if current == "execute_cookbook":
        return "verify_outcome"
    if current == "verify_outcome":
        return _route_after_verification(state)
    if current in {"close_ticket", "assign_ticket"}:
        return "notify_slack"
    if current == "notify_slack":
        return END
    return END


def _build_fallback_graph() -> _FallbackGraph:
    return _FallbackGraph()


graph = build_graph()
