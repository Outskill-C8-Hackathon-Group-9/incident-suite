from __future__ import annotations

import json
import time
import uuid
from urllib import error, parse, request

from app.config import config


class SlackNotifier:
    def post_team_message(self, *, text: str) -> tuple[str, str]:
        if config.SLACK_BOT_TOKEN:
            try:
                channel_id = config.SLACK_CHANNEL_ID
                if not channel_id:
                    raise RuntimeError("SLACK_CHANNEL_ID is required for real Slack posts")
                result = self._post_message(channel=channel_id, text=text)
                permalink = self._get_permalink(channel=result["channel"], ts=result["ts"])
                return channel_id, permalink
            except Exception as exc:
                raise RuntimeError(f"real team message failed: {exc}") from exc
        if config.SLACK_WEBHOOK_URL:
            try:
                self._post_webhook(text=text)
                return config.SLACK_CHANNEL, "webhook://posted"
            except Exception as exc:
                raise RuntimeError(f"webhook team message failed: {exc}") from exc
        return self._mock_post(channel=config.SLACK_CHANNEL, text=text)

    def post_direct_message(self, *, slack_user_id: str, text: str) -> str:
        if not slack_user_id:
            return ""
        if config.SLACK_BOT_TOKEN:
            try:
                channel_id = self._open_dm(slack_user_id=slack_user_id)
                result = self._post_message(channel=channel_id, text=text)
                return self._get_permalink(channel=result["channel"], ts=result["ts"])
            except Exception as exc:
                raise RuntimeError(f"real DM failed: {exc}") from exc
        _, permalink = self._mock_post(channel=f"@{slack_user_id}", text=text)
        return permalink

    def _post_message(self, *, channel: str, text: str) -> dict:
        return self._api_call(
            endpoint="chat.postMessage",
            payload={"channel": channel, "text": text},
        )

    def _open_dm(self, *, slack_user_id: str) -> str:
        result = self._api_call(endpoint="conversations.open", payload={"users": slack_user_id})
        return result["channel"]["id"]

    def _get_permalink(self, *, channel: str, ts: str) -> str:
        result = self._api_call(
            endpoint="chat.getPermalink",
            payload={"channel": channel, "message_ts": ts},
        )
        return result.get("permalink", "")

    def _post_webhook(self, *, text: str) -> None:
        body = json.dumps({"text": text}).encode("utf-8")
        req = request.Request(
            config.SLACK_WEBHOOK_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=20):
            return None

    def _api_call(self, *, endpoint: str, payload: dict) -> dict:
        body = parse.urlencode({key: json.dumps(value) if isinstance(value, dict) else value for key, value in payload.items()}).encode("utf-8")
        req = request.Request(
            f"https://slack.com/api/{endpoint}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {config.SLACK_BOT_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with request.urlopen(req, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "unknown_slack_error"))
        return data

    def _mock_post(self, *, channel: str, text: str) -> tuple[str, str]:
        permalink = f"https://mock.slack.local/{uuid.uuid4().hex[:12]}"
        print(f"[MOCK SLACK] -> {channel}\n{text}\n")
        return channel, permalink
