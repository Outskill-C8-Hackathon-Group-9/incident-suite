from pydantic import ValidationError

from app.state import IncidentState
from app.models import ClassifierOutput, IssueEvaluations
from app.parsing import parse_logs, cluster_errors
from app.llm import get_llm
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
- confidence: a number between 0.0 and 1.0 representing how sure you are of this classification

Merge clusters that are symptoms of the same root cause into ONE issue.

CLUSTERS:
{clusters}
"""

KNOWN_CATEGORIES = {
    "memory_leak",
    "deployment_regression",
    "database",
    "network",
    "cpu_saturation",
    "timeout",
    "auth",
    "config",
    "unknown",
}


def _evaluate_classifier_issues(issues: list[dict]) -> dict:
    passed = True
    rules: list[str] = []
    if not issues:
        rules.append("No issues is valid when logs contain no error clusters.")
        return {"passed": True, "rules": rules, "avg_confidence": 0.0}

    confidences = []
    for issue in issues:
        if issue["category"] not in KNOWN_CATEGORIES:
            passed = False
            rules.append(f"Category '{issue['category']}' is not one of the known golden categories.")
        if not issue["evidence"]:
            passed = False
            rules.append(f"Issue {issue['id']} must include evidence lines.")
        if not 0.0 <= issue["confidence"] <= 1.0:
            passed = False
            rules.append(f"Issue {issue['id']} has confidence outside 0.0-1.0.")
        confidences.append(issue["confidence"])

    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    if avg_confidence < 0.2:
        rules.append("Average issue confidence is low; review the classifier prompt or sample data.")

    return {"passed": passed, "rules": rules, "avg_confidence": avg_confidence}


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
    try:
        result: ClassifierOutput = llm.invoke(CLASSIFY_PROMPT.format(clusters=clusters_text))
    except ValidationError as exc:
        result = ClassifierOutput(issues=[])
        trace_data = {"error": str(exc)}
    else:
        trace_data = {}

    issues = [i.model_dump() for i in result.issues]
    evaluation = _evaluate_classifier_issues(issues)

    # --- LLM-based evaluation: ask the model to rate each detected issue with confidence & reasoning
    llm_eval_prompt = """You are an SRE auditor. Use the KNOWN CATEGORIES below as the canonical taxonomy when judging categories.
Known categories: memory_leak, deployment_regression, database, network, cpu_saturation, timeout, auth, config, unknown.

For each DetectedIssue below, return an evaluation with:
- id (must match)
- confidence: number between 0.0 and 1.0
- reasoning: one-sentence justification for this confidence (mention if the category matches the known categories)

ISSUES:
{issues}

Return a JSON matching the model IssueEvaluations.issue_evals list.
"""
    try:
        llm_eval = get_llm(temperature=0.0).with_structured_output(IssueEvaluations, method="function_calling")
        issues_text = "\n".join(
            f"- id={i['id']} | title={i['title']} | category={i['category']} | severity={i['severity']} | service={i['affected_service']} | summary={i['summary']}"
            for i in issues
        )
        eval_result: IssueEvaluations = llm_eval.invoke(llm_eval_prompt.format(issues=issues_text))
        for ev in eval_result.issue_evals:
            for issue in issues:
                if issue["id"] == ev.id:
                    issue["confidence"] = ev.confidence
                    issue.setdefault("evaluation", {})["llm_reasoning"] = ev.reasoning
        evaluation = _evaluate_classifier_issues(issues)  # re-run deterministic checks with LLM confidences
        trace_data.setdefault("llm_evaluated", True)
    except Exception as exc:
        trace_data.setdefault("llm_eval_error", str(exc))

    return {
        "entries": [e.model_dump() for e in entries],
        "clusters": [c.model_dump() for c in clusters],
        "issues": issues,
        "trace": [trace_event(
            "classifier",
            f"Parsed {len(entries)} lines, {len(clusters)} clusters, detected {len(issues)} issue(s) with avg confidence {evaluation['avg_confidence']:.2f}.",
            {"issues": issues, "evaluation": evaluation, **trace_data},
        )],
    }