"""Notifies pipeline stage status. Formats a Slack-style message and either
posts it to a real webhook (if SLACK_WEBHOOK_URL is set) or prints it, so the
pipeline is demoable without any external service configured.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

STATUS_EMOJI = {"success": ":white_check_mark:", "failure": ":x:", "info": ":information_source:"}


def build_payload(stage: str, status: str, message: str) -> dict[str, str]:
    emoji = STATUS_EMOJI.get(status, ":grey_question:")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = f"{emoji} *[{stage}]* {status.upper()} - {message} ({timestamp})"
    return {"text": text}


def send(payload: dict[str, str]) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print(f"[notify:console] {payload['text']}")
        return

    import requests  # imported lazily: only needed when a real webhook is configured

    response = requests.post(webhook_url, json=payload, timeout=5)
    response.raise_for_status()
    print(f"[notify:slack] delivered - {payload['text']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Notify pipeline stage status")
    parser.add_argument("--stage", required=True, help="pipeline stage name, e.g. 'Deploy'")
    parser.add_argument("--status", required=True, choices=sorted(STATUS_EMOJI))
    parser.add_argument("--message", required=True)
    args = parser.parse_args()

    payload = build_payload(args.stage, args.status, args.message)
    send(payload)


if __name__ == "__main__":
    main()
