from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import IncidentState
from app.nodes.classifier import classifier_node
from app.nodes.remediation import remediation_node
from app.nodes.cookbook import cookbook_node
from app.nodes.jira import jira_node
from app.nodes.notifier import notifier_node

CRITICAL = {"critical", "high"}


def route_by_severity(state: IncidentState) -> str:
    """Conditional edge: go to JIRA only if there's a critical/high issue."""
    if any(i.get("severity") in CRITICAL for i in state.get("issues", [])):
        return "jira"
    return "notifier"


def build_graph():
    g = StateGraph(IncidentState)

    g.add_node("classifier", classifier_node)
    g.add_node("remediation", remediation_node)
    g.add_node("cookbook", cookbook_node)
    g.add_node("jira", jira_node)
    g.add_node("notifier", notifier_node)

    g.add_edge(START, "classifier")
    g.add_edge("classifier", "remediation")
    g.add_edge("remediation", "cookbook")
    g.add_conditional_edges("cookbook", route_by_severity, {"jira": "jira", "notifier": "notifier"})
    g.add_edge("jira", "notifier")
    g.add_edge("notifier", END)

    return g.compile(checkpointer=MemorySaver())


graph = build_graph()