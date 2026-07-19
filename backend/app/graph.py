from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import IncidentState
from app.nodes.classifier import classifier_node
from app.nodes.remediation import remediation_node
from app.nodes.cookbook import cookbook_node
from app.nodes.decide_response import decide_response_node
from app.nodes.create_ticket import create_ticket_node
from app.nodes.execute_cookbook import execute_cookbook_node
from app.nodes.verify_outcome import verify_outcome_node
from app.nodes.close_ticket import close_ticket_node
from app.nodes.notify_slack import notify_slack_node


def build_graph():
    g = StateGraph(IncidentState)

    g.add_node("classifier", classifier_node)
    g.add_node("remediation", remediation_node)
    g.add_node("cookbook", cookbook_node)
    g.add_node("decide_response", decide_response_node)
    g.add_node("create_ticket", create_ticket_node)
    g.add_node("execute_cookbook", execute_cookbook_node)
    g.add_node("verify_outcome", verify_outcome_node)
    g.add_node("close_ticket", close_ticket_node)
    g.add_node("notify_slack", notify_slack_node)

    g.add_edge(START, "classifier")
    g.add_edge("classifier", "remediation")
    g.add_edge("remediation", "cookbook")
    g.add_edge("cookbook", "decide_response")
    g.add_edge("decide_response", "create_ticket")
    # execute_cookbook / verify_outcome / close_ticket each loop over
    # state["tickets"] internally and skip investigative entries, so no
    # per-issue conditional routing is needed at the graph level.
    g.add_edge("create_ticket", "execute_cookbook")
    g.add_edge("execute_cookbook", "verify_outcome")
    g.add_edge("verify_outcome", "close_ticket")
    g.add_edge("close_ticket", "notify_slack")
    g.add_edge("notify_slack", END)

    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
