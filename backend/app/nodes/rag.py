from app.state import IncidentState
from app.knowledge.runbook_store import retrieve
from app.config import config
from app.agent_logging import log_agent_io
from app.nodes._trace import trace_event


def rag_node(state: IncidentState) -> dict:
    """Retrieve matching runbooks for each issue and write them to graph state."""
    issues = state.get("issues", [])
    log_agent_io("rag", "request", {"issues": [{"id": i.get("id"), "title": i.get("title")} for i in issues]})

    if not issues:
        response = {
            "retrieved_runbooks": {},
            "runbook_titles": [],
            "retrieved_runbook_contents": {},
            "trace": [trace_event("rag", "No issues; skipped retrieval.")],
        }
        log_agent_io("rag", "response", {
            "retrieved_runbooks": {},
            "runbook_titles": [],
        })
        return response

    seen: dict[str, str] = {}  # title -> content (dedupe across issues)
    grounding_by_issue: dict[str, list[str]] = {}
    for i in issues:
        query = f"{i['title']} {i['category']} {i['affected_service']} {i['summary']}"
        docs = retrieve(query, k=config.RAG_TOP_K)
        titles = []
        for d in docs:
            title = d.metadata.get("title", "runbook")
            seen[title] = d.page_content
            titles.append(title)
        grounding_by_issue[i["id"]] = titles

    runbook_titles = list(seen.keys())
    response = {
        "retrieved_runbooks": grounding_by_issue,
        "runbook_titles": runbook_titles,
        "retrieved_runbook_contents": seen,
        "trace": [trace_event(
            "rag",
            f"Retrieved {len(runbook_titles)} runbook(s) for {len(issues)} issue(s).",
            {
                "retrieved_runbooks": grounding_by_issue,
                "runbook_titles": runbook_titles,
            },
        )],
    }
    log_agent_io("rag", "response", {
        "retrieved_runbooks": grounding_by_issue,
        "runbook_titles": runbook_titles,
    })
    return response
