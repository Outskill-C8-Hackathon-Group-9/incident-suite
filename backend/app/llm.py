from __future__ import annotations

from app.config import config
from app.models import Decision, IncidentInput

DECISION_PROMPT = """You are the decision engine for an incident workflow.

Choose exactly one path:
- remediative: the cookbook is concrete enough for safe automation right now
- investigative: a human should take over after ticket creation

Reply as JSON matching this schema:
{"path":"remediative|investigative","confidence":0.0,"policy_reason":"short reason"}

Incident summary: {summary}
Severity: {severity}
Host: {host}
Service: {service}
Cookbook title: {cookbook_title}
Cookbook steps:
{cookbook_steps}
"""

REMEDIATIVE_HINTS = (
    "restart",
    "rollback",
    "roll back",
    "scale",
    "increase",
    "clear cache",
    "redeploy",
    "re-deploy",
    "fail over",
    "rotate",
)

INVESTIGATIVE_HINTS = (
    "unclear",
    "investigate",
    "investigation",
    "collect evidence",
    "compare",
    "triage",
    "diagnose",
)


class OfflineDecisionReasoner:
    def decide(self, incident: IncidentInput) -> Decision:
        text = " ".join(
            [incident.summary, incident.cookbook.title]
            + [item.action for item in incident.cookbook.items]
        ).lower()
        if any(hint in text for hint in INVESTIGATIVE_HINTS):
            path = "investigative"
        elif any(hint in text for hint in REMEDIATIVE_HINTS):
            path = "remediative"
        else:
            path = "investigative"
        return Decision(
            path=path,
            confidence=0.55,
            policy_reason="Offline fallback used because OPENROUTER_API_KEY is missing.",
        )


class OpenRouterDecisionReasoner:
    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI

        self._llm = ChatOpenAI(
            model=config.OPENROUTER_MODEL,
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            temperature=config.LLM_TEMPERATURE,
        ).with_structured_output(Decision, method="json_mode")

    def decide(self, incident: IncidentInput) -> Decision:
        prompt = DECISION_PROMPT.format(
            summary=incident.summary,
            severity=incident.severity,
            host=incident.host,
            service=incident.service,
            cookbook_title=incident.cookbook.title,
            cookbook_steps="\n".join(
                f"- Step {item.step}: {item.action} | done when: {item.done_when}"
                for item in incident.cookbook.items
            ),
        )
        return self._llm.invoke(prompt)


def get_decision_reasoner() -> OfflineDecisionReasoner | OpenRouterDecisionReasoner:
    if config.use_openrouter:
        try:
            return OpenRouterDecisionReasoner()
        except Exception as exc:
            print(f"[LLM] OpenRouter unavailable, using offline fallback: {exc}")
    return OfflineDecisionReasoner()
