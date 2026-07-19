from app.state import IncidentState
from app.models import ClassifierOutput
from app.parsing import parse_logs, cluster_errors
from app.llm import get_llm, invoke_llm
from app.agent_logging import log_agent_io
from app.nodes._trace import trace_event

CLASSIFY_PROMPT = """You are a senior SRE triaging a production incident from log clusters.

You are given error/warning clusters extracted from uploaded logs. Each cluster has a signature,
an occurrence count, the affected service, and sample lines.

For each DISTINCT underlying problem, produce a DetectedIssue with:
- a short slug id (e.g. 'oom-order-service')
- a clear title
- the best-fitting category
- a severity (critical/high/medium/low/info) reasoning about blast radius and user impact
- the affected service
- a 1-2 sentence plain-English summary
- evidence: the specific sample lines that justify the issue

Merge clusters that are symptoms of the same root cause into ONE issue.

CLUSTERS:
{clusters}
"""


def classifier_node(state: IncidentState) -> dict:
    log_agent_io(
        "classifier",
        "request",
        {
            "filename": state.get("filename"),
            "raw_logs_chars": len(state.get("raw_logs") or ""),
            "raw_logs_preview": (state.get("raw_logs") or "")[:500],
        },
    )

    entries = parse_logs(state["raw_logs"])
    clusters = cluster_errors(entries)

    if not clusters:
        response = {
            "entries": [e.model_dump() for e in entries],
            "clusters": [],
            "issues": [],
            "trace": [trace_event("classifier", "No error/warning clusters found.")],
        }
        log_agent_io("classifier", "response", {
            "entries_count": len(entries),
            "clusters": [],
            "issues": [],
        })
        return response

    clusters_text = "\n\n".join(
        f"[{c.count}x] level={c.level} service={c.example_service} sig={c.signature}\n"
        + "\n".join(f"  {ln}" for ln in c.sample_lines)
        for c in clusters
    )

    prompt = CLASSIFY_PROMPT.format(clusters=clusters_text)
    llm = get_llm().with_structured_output(ClassifierOutput, method="function_calling")
    result: ClassifierOutput = invoke_llm("classifier.llm", llm, prompt)
    issues = [i.model_dump() for i in result.issues]

    response = {
        "entries": [e.model_dump() for e in entries],
        "clusters": [c.model_dump() for c in clusters],
        "issues": issues,
        "trace": [trace_event(
            "classifier",
            f"Parsed {len(entries)} lines, {len(clusters)} clusters, "
            f"detected {len(issues)} issue(s).",
            {"issues": issues},
        )],
    }
    log_agent_io("classifier", "response", {
        "entries_count": len(entries),
        "clusters": [c.model_dump() for c in clusters],
        "issues": issues,
    })
    return response
