#!/usr/bin/env python3
"""Safely upload the existing 42 Candy Trivia campaign JSON files.

Run this from the existing CandyTrivia-TikTok-Factor checkout. The script never
switches or cleans the current working tree. It validates and scans the local
campaign definitions, creates an isolated Git worktree, commits only the JSON
files, pushes the approved premium branch, and lets GitHub Actions perform the
production validation.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


REMOTE = "origin"
TARGET_BRANCH = "feature/super-premium-candy-graphics"
EXPECTED_NAMES = {f"post-{number:03d}.json" for number in range(1, 43)}
WORKTREE_NAME = "CandyTrivia-Campaign-GitHub-Upload"
WORKFLOW_URL = (
    "https://github.com/DragonLabs-ux/CandyTrivia-TikTok-Factor/actions"
)

SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|buffer[_-]?token|"
    r"password|passwd|secret|authorization|private[_-]?key|client[_-]?secret)",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|\bsk-[A-Za-z0-9_-]{12,}|"
    r"\bgh[opsu]_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)


class UploadError(RuntimeError):
    pass


def run(command: list[str], cwd: Path, *, capture: bool = False) -> str:
    printable = " ".join(command)
    print(f"\n> {printable}")
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        if capture and result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise UploadError(f"Command failed with exit code {result.returncode}: {printable}")
    return result.stdout.strip() if capture else ""


def find_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise UploadError("Run this script from inside CandyTrivia-TikTok-Factor.")
    return Path(result.stdout.strip()).resolve()


def inspect_json(value: object, file_name: str, location: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if SENSITIVE_KEY.search(str(key)):
                findings.append(f"{file_name}: suspicious key at {child_location}")
            findings.extend(inspect_json(child, file_name, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(inspect_json(child, file_name, f"{location}[{index}]"))
    elif isinstance(value, str) and SENSITIVE_VALUE.search(value):
        findings.append(f"{file_name}: suspicious value at {location}")
    return findings


def validate_campaign(source_dir: Path) -> list[Path]:
    files = sorted(source_dir.glob("post-*.json"))
    names = {path.name for path in files}
    missing = sorted(EXPECTED_NAMES - names)
    unexpected = sorted(names - EXPECTED_NAMES)
    if len(files) != 42 or missing or unexpected:
        raise UploadError(
            "Expected post-001.json through post-042.json exactly. "
            f"Found {len(files)}; missing={missing}; unexpected={unexpected}"
        )

    findings: list[str] = []
    post_ids: set[str] = set()
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UploadError(f"Invalid JSON in {path.name}: {exc}") from exc
        findings.extend(inspect_json(data, path.name))
        if isinstance(data, dict) and "postId" in data:
            post_id = str(data["postId"])
            if post_id in post_ids:
                raise UploadError(f"Duplicate postId detected in {path.name}: {post_id}")
            post_ids.add(post_id)

    if findings:
        print("\nPossible credentials were detected; values were not displayed:")
        for finding in findings:
            print(f"  - {finding}")
        raise UploadError("Credential scan failed. Nothing was copied, committed, or pushed.")

    print("Validated 42 JSON files. No likely credentials were detected.")
    return files


def maybe_watch_actions(repo_root: Path, commit_sha: str) -> None:
    if shutil.which("gh") is None:
        print(f"\nGitHub Actions started automatically. Monitor it here:\n{WORKFLOW_URL}")
        return

    print("\nWaiting briefly for GitHub to register the workflow run...")
    for _ in range(12):
        result = subprocess.run(
            [
                "gh", "run", "list",
                "--branch", TARGET_BRANCH,
                "--commit", commit_sha,
                "--workflow", "premium-production-validation.yml",
                "--limit", "1",
                "--json", "databaseId,status,url",
                "--jq", ".[0] | [.databaseId,.status,.url] | @tsv",
            ],
            cwd=repo_root,
            check=False,
            text=True,
            capture_output=True,
        )
        line = result.stdout.strip()
        if result.returncode == 0 and line:
            run_id, status, url = line.split("\t", 2)
            print(f"GitHub Actions run: {url} ({status})")
            if status in {"queued", "in_progress", "waiting", "pending"}:
                print("Watching the GitHub run. Press Ctrl+C only if you want to stop watching;")
                print("the GitHub job itself will continue.")
                subprocess.run(["gh", "run", "watch", run_id, "--exit-status"], cwd=repo_root)
            return
        time.sleep(5)
    print(f"GitHub Actions should start automatically. Monitor it here:\n{WORKFLOW_URL}")


def main() -> int:
    repo_root = find_repo_root()
    source_dir = repo_root / "examples" / "auto"
    files = validate_campaign(source_dir)

    worktree = repo_root.parent / WORKTREE_NAME
    if worktree.exists():
        raise UploadError(
            f"Temporary worktree already exists: {worktree}\n"
            "Nothing was changed. Rename that folder or ask for cleanup guidance."
        )

    run(["git", "fetch", REMOTE, TARGET_BRANCH], repo_root)
    run(
        ["git", "worktree", "add", "--detach", str(worktree), f"{REMOTE}/{TARGET_BRANCH}"],
        repo_root,
    )

    pushed = False
    commit_sha = ""
    try:
        destination = worktree / "examples" / "auto"
        destination.mkdir(parents=True, exist_ok=True)
        for source in files:
            shutil.copy2(source, destination / source.name)

        copied = sorted(destination.glob("post-*.json"))
        if {path.name for path in copied} != EXPECTED_NAMES:
            raise UploadError("Temporary copy validation failed. Nothing was committed or pushed.")

        run(["git", "add", "--", "examples/auto"], worktree)
        run(["git", "diff", "--cached", "--check"], worktree)
        staged = run(["git", "diff", "--cached", "--name-only"], worktree, capture=True)
        staged_names = {Path(line).name for line in staged.splitlines() if line.strip()}
        if staged_names != EXPECTED_NAMES:
            raise UploadError(
                "Safety check failed: the staged files were not exactly post-001.json through "
                "post-042.json. Nothing was committed or pushed."
            )

        run(["git", "commit", "-m", "Add 42-post Candy Trivia campaign definitions"], worktree)
        commit_sha = run(["git", "rev-parse", "HEAD"], worktree, capture=True)
        run(["git", "push", REMOTE, f"HEAD:refs/heads/{TARGET_BRANCH}"], worktree)
        pushed = True
    finally:
        if pushed:
            run(["git", "worktree", "remove", str(worktree)], repo_root)
        else:
            print(f"\nThe diagnostic worktree was retained at: {worktree}")

    print("\nSUCCESS: All 42 campaign JSON files were pushed to the premium branch.")
    print("The GitHub workflow will audit the full campaign and render Templates A and B.")
    print("TikTok, Buffer, R2 publishing, and paid image APIs were not invoked.")
    maybe_watch_actions(repo_root, commit_sha)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UploadError as exc:
        print(f"\nSTOPPED SAFELY: {exc}", file=sys.stderr)
        raise SystemExit(1)
