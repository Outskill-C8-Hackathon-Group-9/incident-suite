from __future__ import annotations

import os
import json

from app.models import Engineer

try:
    from dotenv import load_dotenv
except ImportError:
    def _clean_env_value(value: str) -> str:
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value

    def load_dotenv(path: str = ".env") -> None:
        if not os.path.exists(path):
            return
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), _clean_env_value(value))


load_dotenv()


def _read_multiline_env_value(name: str, path: str = ".env") -> str:
    if not os.path.exists(path):
        return ""

    prefix = f"{name}="
    capturing = False
    brace_depth = 0
    chunks: list[str] = []

    for raw_line in open(path, encoding="utf-8"):
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not capturing:
            if stripped.startswith(prefix):
                value = stripped[len(prefix):].strip()
                if value:
                    chunks.append(value)
                    brace_depth += value.count("{") - value.count("}")
                    if brace_depth <= 0:
                        return "\n".join(chunks).strip()
                capturing = brace_depth > 0
            continue

        chunks.append(line)
        brace_depth += line.count("{") - line.count("}")
        if brace_depth <= 0:
            return "\n".join(chunks).strip()

    return ""


def _as_bool(value: str, *, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", os.getenv("LLM_MODEL", "openai/gpt-4o-mini"))
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#incidents")
    SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

    JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL", "")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "INC")
    JIRA_ISSUE_TYPE = os.getenv("JIRA_ISSUE_TYPE", "Task")
    JIRA_PRIORITY_ID = os.getenv("JIRA_PRIORITY_ID", "")
    JIRA_DONE_TRANSITION_ID = os.getenv("JIRA_DONE_TRANSITION_ID", "")

    @property
    def use_openrouter(self) -> bool:
        return bool(self.OPENROUTER_API_KEY)

    @property
    def use_real_jira(self) -> bool:
        return bool(self.JIRA_BASE_URL and self.JIRA_USER_EMAIL and self.JIRA_API_TOKEN)

    @property
    def use_real_slack(self) -> bool:
        return bool(self.SLACK_BOT_TOKEN or self.SLACK_WEBHOOK_URL)

    @property
    def oncall_engineers(self) -> list[Engineer]:
        mapping_json = os.getenv("ENGINEER_MAPPING_JSON", "").strip()
        if not mapping_json:
            mapping_json = _read_multiline_env_value("ENGINEER_MAPPING")
        if mapping_json:
            try:
                parsed = json.loads(mapping_json)
            except json.JSONDecodeError:
                parsed = {}
            engineers_from_json = [
                Engineer(
                    name=name,
                    email=entry.get("email", ""),
                    slack_user_id=entry.get("slack_user_id", ""),
                    jira_account_id=entry.get("jira_account_id", ""),
                    expertise=entry.get("expertise", ""),
                )
                for name, entry in parsed.items()
                if isinstance(entry, dict)
            ]
            if engineers_from_json:
                return engineers_from_json

        raw = os.getenv("ONCALL_ENGINEERS", "")
        engineers: list[Engineer] = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = [part.strip() for part in chunk.split("|")]
            while len(parts) < 4:
                parts.append("")
            engineers.append(
                Engineer(
                    name=parts[0] or "Unassigned",
                    email=parts[1],
                    slack_user_id=parts[2],
                    jira_account_id=parts[3],
                    expertise=parts[4] if len(parts) > 4 else "",
                )
            )
        if engineers:
            return engineers
        return [
            Engineer(name="Alex", email="alex@example.com"),
            Engineer(name="Sam", email="sam@example.com"),
        ]

    @property
    def verbose_demo(self) -> bool:
        return _as_bool(os.getenv("VERBOSE_DEMO", "true"), default=True)

    def engineer_by_name(self, name: str) -> Engineer | None:
        if not name:
            return None
        lowered = name.strip().lower()
        for engineer in self.oncall_engineers:
            if engineer.name.strip().lower() == lowered:
                return engineer
        return None


config = Config()
