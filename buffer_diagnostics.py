#!/usr/bin/env python3
"""Run safe Buffer GraphQL diagnostics for the Candy TikTok channel.

This script prints only configuration names, HTTP status, and sanitized Buffer
GraphQL error messages. It never prints the Buffer token or channel ID.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def call_buffer(query: str, variables: dict) -> dict:
    request = urllib.request.Request(
        "https://api.buffer.com",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": "Bearer " + required("BUFFER_API_KEY"),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            print(f"HTTP status: {response.status}")
            return json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"HTTP status: {exc.code}")
        body = exc.read().decode("utf-8", errors="replace")
        print("HTTP error body:")
        print(body[:2000])
        raise SystemExit(1)
    except Exception as exc:
        print(f"Buffer request failed: {type(exc).__name__}")
        raise SystemExit(1)


def print_errors(payload: dict) -> bool:
    errors = payload.get("errors") or []
    if not errors:
        return False
    print("GraphQL errors:")
    for error in errors:
        safe = {
            "message": error.get("message"),
            "path": error.get("path"),
            "extensions": error.get("extensions"),
        }
        print(json.dumps(safe, indent=2, ensure_ascii=False))
    return True


def main() -> int:
    print("Checking Buffer API token and TikTok channel without printing secret values.")
    print("BUFFER_API_KEY configured:", bool(os.environ.get("BUFFER_API_KEY", "").strip()))
    print("BUFFER_TIKTOK_CHANNEL_ID configured:", bool(os.environ.get("BUFFER_TIKTOK_CHANNEL_ID", "").strip()))

    payload = call_buffer(
        "query($id:ChannelId!){channel(input:{id:$id}){id name service}}",
        {"id": required("BUFFER_TIKTOK_CHANNEL_ID")},
    )
    if print_errors(payload):
        return 1
    channel = payload.get("data", {}).get("channel")
    print("Channel response:")
    if channel:
        print(json.dumps({"name": channel.get("name"), "service": channel.get("service"), "id_present": bool(channel.get("id"))}, indent=2, ensure_ascii=False))
    else:
        print("null")

    payload = call_buffer("{account{organizations{id}}}", {})
    if print_errors(payload):
        return 1
    orgs = payload.get("data", {}).get("account", {}).get("organizations")
    print("Organization count:", len(orgs or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
