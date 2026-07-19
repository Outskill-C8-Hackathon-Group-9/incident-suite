from app.state import IncidentState
from app.models import ClassifierOutput
from app.parsing import parse_logs, cluster_errors
from app.llm import get_llm
from app.nodes._trace import trace_event

CLASSIFY_PROMPT = """You are a senior SRE triaging a production incident from log clusters.

You are given error/warning clusters extracted from uploaded logs. Each cluster has a signature,
an occurrence count, the affected service, and sample lines.

For each DISTINCT underlying problem, produce a DetectedIssue with:
- a short slug id (e.g. 'oom-order-service')
- a clear title
- the best-fitting category from: memory_leak, deployment_regression, database, network,
  cpu_saturation, timeout, auth, config, dns, certificate, disk, cache, messaging, search,
  rate_limit, container_crash, container_image, security, monitoring, load_balancer, deadlock, unknown
- a severity (critical/high/medium/low/info) reasoning about blast radius and user impact
- severity_detail: a detailed classification with:
  - level: same as severity
  - confidence: 0.0-1.0 how confident you are
  - blast_radius: 'single-service', 'multi-service', 'cluster-wide', or 'customer-facing'
  - user_impact: 'none', 'degraded', 'partial-outage', or 'full-outage'
  - escalation_needed: true if immediate senior on-call escalation is warranted
  - reasoning: 1-sentence justification for the severity level
- the affected service
- a 1-2 sentence plain-English summary
- evidence: the specific sample lines that justify the issue

SEVERITY CLASSIFICATION GUIDELINES:
- critical: customer-facing full outage, data loss risk, security breach. Always escalate.
- high: significant degradation, multi-service impact, approaching threshold. Usually escalate.
- medium: single-service degradation, performance issues, no data loss. Monitor closely.
- low: minor issues, cosmetic errors, non-production impact. Fix in next sprint.
- info: informational, no action needed. Log for trending.

Merge clusters that are symptoms of the same root cause into ONE issue.

CLUSTERS:
{clusters}
"""


def classifier_node(state: IncidentState) -> dict:
    entries = parse_logs(state["raw_logs"])
    clusters = cluster_errors(entries)

    if not clusters:
        return {
            "entries": [e.model_dump() for e in entries],
            "clusters": [],
            "issues": [],
            "trace": [trace_event("classifier", "No error/warning clusters found.")],
        }

    clusters_text = "\n\n".join(
        f"[{c.count}x] level={c.level} service={c.example_service} sig={c.signature}\n"
        + "\n".join(f"  {ln}" for ln in c.sample_lines)
        for c in clusters
    )

    llm = get_llm().with_structured_output(ClassifierOutput, method="function_calling")
    result: ClassifierOutput = llm.invoke(CLASSIFY_PROMPT.format(clusters=clusters_text))
    issues = [i.model_dump() for i in result.issues]

    severity_counts = {}
    for i in issues:
        sev = i.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        "entries": [e.model_dump() for e in entries],
        "clusters": [c.model_dump() for c in clusters],
        "issues": issues,
        "trace": [trace_event(
            "classifier",
            f"Parsed {len(entries)} lines, {len(clusters)} clusters, "
            f"detected {len(issues)} issue(s). "
            f"Severity breakdown: {severity_counts}",
            {"issues": issues, "severity_breakdown": severity_counts},
        )],
    }
