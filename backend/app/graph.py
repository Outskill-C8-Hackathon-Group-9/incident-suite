from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import IncidentState
from app.nodes.classifier import classifier_node
from app.nodes.image_analyzer import image_analyzer_node
from app.nodes.remediation import remediation_node
from app.nodes.fallback import fallback_node
from app.nodes.cookbook import cookbook_node
from app.nodes.jira import jira_node
from app.nodes.notifier import notifier_node

CRITICAL = {"critical", "high"}


def route_after_classifier(state: IncidentState) -> str:
    """Route to image analyzer if image data is present, otherwise to remediation."""
    if state.get("image_data") or state.get("image_description"):
        return "image_analyzer"
    return "remediation"


def route_by_severity(state: IncidentState) -> str:
    """Conditional edge: go to JIRA only if there's a critical/high issue."""
    if any(i.get("severity") in CRITICAL for i in state.get("issues", [])):
        return "jira"
    return "notifier"


def route_after_remediation(state: IncidentState) -> str:
    """Check if any issues need fallback (unknown/unresolved)."""
    issues = state.get("issues", [])
    rems = state.get("remediations", [])

    has_unknown = any(i.get("category") == "unknown" for i in issues)
    unresolved = any(
        not any(r.get("issue_id") == i.get("id") for r in rems)
        for i in issues
    )

    if has_unknown or unresolved:
        return "fallback"
    return "cookbook"


def build_graph():
    g = StateGraph(IncidentState)

    g.add_node("classifier", classifier_node)
    g.add_node("image_analyzer", image_analyzer_node)
    g.add_node("remediation", remediation_node)
    g.add_node("fallback", fallback_node)
    g.add_node("cookbook", cookbook_node)
    g.add_node("jira", jira_node)
    g.add_node("notifier", notifier_node)

    g.add_edge(START, "classifier")
    g.add_conditional_edges(
        "classifier",
        route_after_classifier,
        {"image_analyzer": "image_analyzer", "remediation": "remediation"},
    )
    g.add_edge("image_analyzer", "remediation")
    g.add_conditional_edges(
        "remediation",
        route_after_remediation,
        {"fallback": "fallback", "cookbook": "cookbook"},
    )
    g.add_edge("fallback", "cookbook")
    g.add_conditional_edges(
        "cookbook",
        route_by_severity,
        {"jira": "jira", "notifier": "notifier"},
    )
    g.add_edge("jira", "notifier")
    g.add_edge("notifier", END)

    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
