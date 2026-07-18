from pydantic import ValidationError

from app.state import IncidentState
from app.models import RemediationOutput, RemediationEvaluations
from app.llm import get_llm
from app.knowledge.runbook_store import retrieve
from app.config import config
from app.nodes._trace import trace_event

REMEDIATION_PROMPT = """You are an SRE proposing remediations for detected incidents.

Use the RETRIEVED RUNBOOKS below as authoritative guidance. Prefer their recommended steps.
For EACH issue, propose exactly one remediation with:
- issue_id (must match)
- fix_summary
- rationale: why this addresses the ROOT CAUSE (reference the runbook guidance where relevant)
- suggested_command: a concrete, SAFE command or config change
  (e.g. 'kubectl rollout undo deployment/user-service'). NEVER propose destructive commands
  (no 'rm -rf', 'drop database', 'DELETE FROM', 'terminate all').
- risk_level (low/medium/high)
- requires_approval: true for anything high-risk
- grounded_in: the titles of the runbooks you actually used for this issue
- confidence: a number between 0.0 and 1.0 representing how strongly this remediation matches the retrieved runbooks

ISSUES:
{issues}

RETRIEVED RUNBOOKS:
{runbooks}
"""

_DANGEROUS = ("rm -rf", "drop database", "delete from", "terminate all", "mkfs", "> /dev")
KNOWN_RISK = {"low", "medium", "high"}


def _evaluate_remediations(remediations: list[dict], issue_ids: set[str]) -> dict:
    passed = True
    rules: list[str] = []
    confidences: list[float] = []

    for r in remediations:
        if r["issue_id"] not in issue_ids:
            passed = False
            rules.append(f"Remediation references unknown issue_id {r['issue_id']}.")
        if r["risk_level"] not in KNOWN_RISK:
            passed = False
            rules.append(f"Risk level {r['risk_level']} is invalid.")
        if r["risk_level"] == "high" and not r["requires_approval"]:
            passed = False
            rules.append(f"High-risk remediation for {r['issue_id']} should require approval.")
        if not r["grounded_in"]:
            passed = False
            rules.append(f"Remediation for {r['issue_id']} should be grounded in retrieved runbooks.")
        if any(bad in r["suggested_command"].lower() for bad in _DANGEROUS):
            passed = False
            rules.append(f"Remediation for {r['issue_id']} includes a dangerous command.")
        confidences.append(r.get("confidence", 0.0))

    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    return {"passed": passed, "rules": rules, "avg_confidence": avg_confidence}


def remediation_node(state: IncidentState) -> dict:
    issues = state.get("issues", [])
    if not issues:
        return {"remediations": [], "trace": [trace_event("remediation", "No issues to remediate.")]}

    # ---- RAG retrieval: pull matching runbooks per issue ----
    seen: dict[str, str] = {}          # title -> content (dedupe across issues)
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

    runbooks_text = "\n\n".join(f"[{title}]\n{content}" for title, content in seen.items()) \
        or "No matching runbooks found."

    issues_text = "\n".join(
        f"- id={i['id']} | {i['severity'].upper()} | {i['category']} | "
        f"{i['affected_service']} | {i['summary']}"
        for i in issues
    )

    llm = get_llm(temperature=0.2).with_structured_output(RemediationOutput, method="function_calling")
    try:
        result: RemediationOutput = llm.invoke(
            REMEDIATION_PROMPT.format(issues=issues_text, runbooks=runbooks_text)
        )
    except ValidationError as exc:
        result = RemediationOutput(remediations=[])
        trace_data = {"error": str(exc)}
    else:
        trace_data = {}

    safe = [
        r.model_dump()
        for r in result.remediations
        if not any(bad in r.suggested_command.lower() for bad in _DANGEROUS)
    ]
    evaluation = _evaluate_remediations(safe, {i["id"] for i in issues})

    # --- LLM-based evaluation of remediations: ask the model to rate each remediation's confidence & reasoning
    llm_eval_prompt = """You are an SRE auditor. Use the KNOWN CATEGORIES below as the canonical taxonomy when judging whether a remediation is well-targeted for the issue.
Known categories: memory_leak, deployment_regression, database, network, cpu_saturation, timeout, auth, config, unknown.

For each proposed Remediation below, return an evaluation with:
- issue_id (must match)
- confidence: number between 0.0 and 1.0
- reasoning: one-sentence justification for this confidence (mention whether the remediation aligns with the issue's category)

REMEDIATIONS:
{remediations}

Return a JSON matching the model RemediationEvaluations.remediation_evals list.
"""
    try:
        if safe:
            llm_eval = get_llm(temperature=0.0).with_structured_output(RemediationEvaluations, method="function_calling")
            rem_text = "\n".join(
                f"- issue_id={r['issue_id']} | fix={r['fix_summary']} | cmd={r['suggested_command']} | grounded_in={','.join(r.get('grounded_in', []))}"
                for r in safe
            )
            rem_eval_result: RemediationEvaluations = llm_eval.invoke(llm_eval_prompt.format(remediations=rem_text))
            for ev in rem_eval_result.remediation_evals:
                for r in safe:
                    if r["issue_id"] == ev.issue_id:
                        r["confidence"] = ev.confidence
                        r.setdefault("evaluation", {})["llm_reasoning"] = ev.reasoning
            evaluation = _evaluate_remediations(safe, {i["id"] for i in issues})
            trace_data.setdefault("llm_evaluated", True)
    except Exception as exc:
        trace_data.setdefault("llm_eval_error", str(exc))

    return {
        "remediations": safe,
        "trace": [trace_event(
            "remediation",
            f"Proposed {len(safe)} remediation(s), grounded in {len(seen)} retrieved runbook(s), avg confidence {evaluation['avg_confidence']:.2f}.",
            {
                "remediations": safe,
                "retrieved_runbooks": grounding_by_issue,
                "evaluation": evaluation,
                **trace_data,
            },
        )],
    }
