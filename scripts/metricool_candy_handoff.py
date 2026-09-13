#!/usr/bin/env python3
"""Create a Candy Trivia MP4 handoff for Metricool.

This script does the local operator work around the GitHub cloud workflow:
- optionally pulls the current branch
- dispatches candy-cloud.yml in metricool-media mode
- waits for the run to finish
- extracts the uploaded R2 media key from the Actions log
- combines it with R2_PUBLIC_BASE_URL from --r2-public-base-url, env, .env, or .private/cloud.env
- writes out/metricool-handoff-POST.json

It does not call Buffer and it does not schedule inside Metricool. Paste the
printed handoff JSON into the Metricool-connected chat to schedule the post.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = 'DragonLabs-ux/CandyTrivia-TikTok-Factor'
WORKFLOW = 'candy-cloud.yml'
DEFAULT_POST = 'candy-premium-2026-09:043'
ROOT = Path(__file__).resolve().parents[1]


class Stop(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> str:
    print('+ ' + ' '.join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    if check and completed.returncode:
        raise Stop(completed.stdout.strip() or f'Command failed: {cmd[0]}')
    return completed.stdout


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        values[name.strip()] = value.strip().strip('"\'')
    return values


def find_public_base(cli_value: str | None) -> str | None:
    if cli_value:
        return cli_value.strip().rstrip('/')
    if os.environ.get('R2_PUBLIC_BASE_URL'):
        return os.environ['R2_PUBLIC_BASE_URL'].strip().rstrip('/')
    for file in (ROOT / '.env', ROOT / '.private' / 'cloud.env'):
        value = load_env_file(file).get('R2_PUBLIC_BASE_URL')
        if value:
            return value.strip().rstrip('/')
    # Optional non-secret repo variable, if you choose to create one later.
    value = run(['gh', 'variable', 'get', 'CANDY_R2_PUBLIC_BASE_URL', '--repo', REPO], check=False).strip()
    if value and 'could not' not in value.lower() and 'not found' not in value.lower():
        return value.rstrip('/')
    return None


def parse_run_id(output: str) -> str | None:
    match = re.search(r'/actions/runs/(\d+)', output)
    return match.group(1) if match else None


def newest_dispatch_run() -> str:
    data = run(['gh', 'run', 'list', '--repo', REPO, '--workflow', WORKFLOW,
                '--event', 'workflow_dispatch', '--limit', '1',
                '--json', 'databaseId'])
    rows = json.loads(data)
    if not rows:
        raise Stop('No workflow_dispatch run found.')
    return str(rows[0]['databaseId'])


def dispatch(post: str) -> str:
    output = run(['gh', 'workflow', 'run', WORKFLOW, '--repo', REPO,
                  '-f', 'mode=metricool-media', '-f', f'post={post}'])
    time.sleep(5)
    return parse_run_id(output) or newest_dispatch_run()


def wait_for_run(run_id: str, timeout_minutes: int) -> dict:
    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        raw = run(['gh', 'run', 'view', run_id, '--repo', REPO,
                   '--json', 'status,conclusion,url,jobs'], check=False)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(raw.strip())
            time.sleep(15)
            continue
        status = data.get('status')
        conclusion = data.get('conclusion')
        print(f'Run {run_id}: {status or "unknown"} {conclusion or ""}'.rstrip(), flush=True)
        if status == 'completed':
            if conclusion != 'success':
                raise Stop(f'Workflow failed: {data.get("url")}')
            return data
        time.sleep(30)
    raise Stop(f'Timed out waiting for run {run_id}.')


def fetch_logs(run_id: str) -> str:
    return run(['gh', 'run', 'view', run_id, '--repo', REPO, '--log'])


def strip_log_prefixes(text: str) -> str:
    # GitHub log lines often start with timestamps. Keep JSON extraction simple.
    return re.sub(r'^\d{4}-\d\d-\d\dT[^\s]+\s', '', text, flags=re.MULTILINE)


def extract_metricool_block(log_text: str) -> dict:
    cleaned = strip_log_prefixes(log_text)
    starts = [m.start() for m in re.finditer(r'\{\s*"metricool_media"\s*:', cleaned)]
    if not starts:
        raise Stop('No metricool_media block found in the workflow log.')
    errors: list[str] = []
    decoder = json.JSONDecoder()
    for start in reversed(starts):
        try:
            obj, _ = decoder.raw_decode(cleaned[start:])
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        media = obj.get('metricool_media')
        if media and media.get('post_id') != 'candy-premium-2026-09:100':
            return media
    raise Stop('Only the unit-test metricool_media block was found. Last JSON errors: ' + '; '.join(errors[-3:]))


def extract_media_key(media_url: str) -> str:
    if media_url.startswith('https://'):
        marker = '/candy/cloud-v1/'
        if marker in media_url:
            return 'candy/cloud-v1/' + media_url.split(marker, 1)[1]
    match = re.search(r'\*{3}/(candy/cloud-v1/[^\s"]+\.mp4)', media_url)
    if match:
        return match.group(1)
    if media_url.startswith('candy/cloud-v1/'):
        return media_url
    raise Stop('Could not extract R2 media key from media_url: ' + media_url)


def verify_url(url: str) -> None:
    request = urllib.request.Request(url, method='HEAD', headers={
        'User-Agent': 'CandyMetricoolHandoff/1.0'
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise Stop(f'Public media check failed with HTTP {response.status}.')
        content_type = response.headers.get_content_type()
        if content_type != 'video/mp4':
            raise Stop(f'Public media is not video/mp4: {content_type}')


def main(argv: list[str] | None = None) -> int:
    global REPO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--post', default=DEFAULT_POST,
                        help=f'Candy post id to render/upload. Default: {DEFAULT_POST}')
    parser.add_argument('--repo', default=REPO, help=argparse.SUPPRESS)
    parser.add_argument('--r2-public-base-url', help='Public R2/custom-domain base URL.')
    parser.add_argument('--run-id', help='Skip dispatch and parse an existing run id.')
    parser.add_argument('--timeout-minutes', type=int, default=60)
    parser.add_argument('--no-pull', action='store_true', help='Do not run git pull first.')
    parser.add_argument('--skip-url-check', action='store_true')
    args = parser.parse_args(argv)

    REPO = args.repo

    if not args.no_pull:
        run(['git', 'pull', 'origin', 'main'], check=False)

    public_base = find_public_base(args.r2_public_base_url)
    run_id = args.run_id or dispatch(args.post)
    run_data = wait_for_run(run_id, args.timeout_minutes)
    log_text = fetch_logs(run_id)
    media = extract_metricool_block(log_text)
    key = extract_media_key(media['media_url'])
    media['media_key'] = key

    if public_base:
        media['media_url'] = public_base + '/' + key
        if not args.skip_url_check:
            verify_url(media['media_url'])
    else:
        media['media_url'] = 'MISSING_R2_PUBLIC_BASE_URL/' + key
        media['needs'] = 'Provide --r2-public-base-url or set R2_PUBLIC_BASE_URL in .env/.private/cloud.env.'

    media['workflow_run_url'] = run_data.get('url') or f'https://github.com/{REPO}/actions/runs/{run_id}'
    media['prepared_at'] = datetime.now(timezone.utc).isoformat()

    out_dir = ROOT / 'out'
    out_dir.mkdir(exist_ok=True)
    safe_post = args.post.replace(':', '-')
    out_file = out_dir / f'metricool-handoff-{safe_post}.json'
    out_file.write_text(json.dumps({'metricool_media': media}, indent=2), encoding='utf-8')

    print('\nMetricool handoff:')
    print(json.dumps({'metricool_media': media}, indent=2))
    print('\nSaved:', out_file)
    if media['media_url'].startswith('MISSING_R2_PUBLIC_BASE_URL/'):
        print('\nNext: rerun with --r2-public-base-url https://YOUR_PUBLIC_BASE_URL')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Stop as exc:
        print('\nSTOPPED:', exc, file=sys.stderr)
        raise SystemExit(1)
