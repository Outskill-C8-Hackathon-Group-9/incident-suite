import time
import uuid
from app.models import SlackResult
from app.config import config


class MockSlackClient:
    """Drop-in mock. To go real: slack_sdk.WebClient(token=...).chat_postMessage(...).
    Keep the SlackResult return type."""

    def post_message(self, *, text: str, channel: str | None = None) -> SlackResult:
        ch = channel or config.SLACK_CHANNEL
        ts = f"{time.time():.6f}"
        permalink = f"https://your-workspace.slack.com/archives/CHANNEL/p{uuid.uuid4().hex[:12]}"
        print(f"[MOCK SLACK] -> {ch}\n{text}\n")
        return SlackResult(channel=ch, ts=ts, permalink=permalink, text_preview=text)