#!/usr/bin/env python3
"""Prepare the optional X/Twitter Buffer promotion pull request.

This helper intentionally stages only the reviewed X-promotion files. It does
not read, print, or configure credentials. After the PR merges, add the
BUFFER_X_CHANNEL_ID secret and enable CANDY_X_PROMOTION_ENABLED separately.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'codex/x-buffer-promotion'
REMOTE = 'origin'
PR_TITLE = 'Add optional X Buffer promotion'
PR_BODY = """Adds optional X/Twitter companion posts through Buffer.

- Uses the same validated video media and scheduled time as the Candy video
- Records X state separately under x_promo in the private ledger
- Keeps TikTok submission/retry safeguards intact
- Leaves the feature disabled until BUFFER_X_CHANNEL_ID and CANDY_X_PROMOTION_ENABLED are configured
"""
FILES = [
    '.github/workflows/candy-cloud.yml',
    'CANDY_CLOUD_RUNBOOK.md',
    'README.md',
    'candy_cloud.py',
    'candy_cloud_admin.py',
    'candy_cloud_check.py',
    'tests/test_cloud_publisher.py',
    'scripts/prepare-x-buffer-promotion-pr.py',
]


def run(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        input=input_text,
        text=True,
        encoding='utf-8',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise SystemExit(f"Command failed: {' '.join(args)}\n{details}")
    return result.stdout.strip()


def tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise SystemExit(f'Missing required command on PATH: {name}')
    return found


def python_executable() -> str:
    return sys.executable


def npm_executable() -> str:
    return 'npm.cmd' if os.name == 'nt' else 'npm'


def assert_expected_files_exist() -> None:
    missing = [name for name in FILES if not (ROOT / name).exists()]
    if missing:
        raise SystemExit('Missing expected file(s): ' + ', '.join(missing))


def ensure_branch() -> None:
    current = run(['git', 'branch', '--show-current'])
    if current == BRANCH:
        return
    branches = run(['git', 'branch', '--list', BRANCH])
    if branches:
        run(['git', 'switch', BRANCH])
    else:
        run(['git', 'switch', '-c', BRANCH])


def run_checks(skip_checks: bool) -> None:
    if skip_checks:
        print('Skipping checks by request.')
        return
    run([python_executable(), '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    run([npm_executable(), 'run', 'typecheck'])
    run(['git', 'diff', '--check'])
    print('Checks passed.')


def commit_changes() -> None:
    run(['git', 'add', *FILES])
    staged = run(['git', 'diff', '--cached', '--name-only'])
    if not staged:
        print('No staged changes; existing commit may already contain this work.')
        return
    run(['git', 'commit', '-m', 'Add optional X Buffer promotion'])
    print('Committed X Buffer promotion changes.')


def push_and_pr(skip_push: bool) -> None:
    if skip_push:
        print('Skipping push/PR by request.')
        return
    tool('gh')
    run(['git', 'push', '-u', REMOTE, BRANCH])
    existing = subprocess.run(
        ['gh', 'pr', 'view', BRANCH, '--json', 'url', '--jq', '.url'],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        print('PR already exists: ' + existing.stdout.strip())
        return
    url = run(['gh', 'pr', 'create', '--title', PR_TITLE, '--body', PR_BODY])
    print('Created PR: ' + url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-checks', action='store_true', help='Do not run tests/typecheck/diff check.')
    parser.add_argument('--no-push', action='store_true', help='Commit locally but do not push or create a PR.')
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    assert_expected_files_exist()
    ensure_branch()
    run_checks(args.skip_checks)
    commit_changes()
    push_and_pr(args.no_push)
    print('Done. Enable the X lane only after the Buffer X channel secret is configured.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
