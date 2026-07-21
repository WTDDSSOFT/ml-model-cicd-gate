"""Smoke test used by Jenkins (post-deploy) and Ansible (blue-green cutover gate).

Polls GET {base_url}/health until it returns 200 or the retry budget is
exhausted. A failure here is what triggers rollback.sh in the pipeline.
"""
from __future__ import annotations

import argparse
import sys
import time

import requests


def check_health(base_url: str, timeout: float) -> bool:
    try:
        response = requests.get(f"{base_url.rstrip('/')}/health", timeout=timeout)
    except requests.RequestException as exc:
        print(f"  request failed: {exc}")
        return False
    if response.status_code != 200:
        print(f"  unexpected status {response.status_code}: {response.text}")
        return False
    print(f"  200 OK: {response.json()}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll /health until it succeeds or retries run out")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between attempts")
    parser.add_argument("--timeout", type=float, default=3.0, help="per-request timeout in seconds")
    args = parser.parse_args()

    for attempt in range(1, args.retries + 1):
        print(f"health check attempt {attempt}/{args.retries} -> {args.base_url}/health")
        if check_health(args.base_url, args.timeout):
            print("PASSED: service is healthy")
            return
        if attempt < args.retries:
            time.sleep(args.delay)

    print("BLOCKED: service failed health check after all retries", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
