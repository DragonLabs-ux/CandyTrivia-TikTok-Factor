#!/usr/bin/env python3
"""One-time history import, encrypted GitHub setup and deliberate cloud cutover.

Does not publish. A successful import starts shadow mode. Production activation
requires 48 hours of shadow observations, fresh history, local cutover, and an
explicit canary; live mode requires that canary to have been delivered.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from candy_cloud import (ROOT, CAMPAIGN, CloudError, MissingState, Buffer, NotFound, R2State,
    compact_post, digest, dt, event, load_campaign, load_local_env, new_state, now_iso, required)

REPO = 'DragonLabs-ux/CandyTrivia-TikTok-Factor'
MARKER = ROOT / '.private/cloud-publisher-cutover.json'


def read_jsonl(file):
    if not file.exists():
        return []
    # Import fails on malformed evidence; never silently discard a bad line.
    return [json.loads(line) for line in file.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def export_history():
    evidence = []
    for name in ('out/manifest.jsonl', 'out/publish-ledger.jsonl', '.private/publish-ledger.jsonl'):
        for row in read_jsonl(ROOT / name):
            fields = ('day', 'post', 'bufferPostId', 'scheduledAt', 'status', 'videoUrl', 'contentFingerprint', 'publishedAt')
            evidence.append({'source': name, **{k: row[k] for k in fields if k in row}})
    file = ROOT / '.private/candy-publisher-state.json'
    if file.exists():
        state = json.loads(file.read_text(encoding='utf-8-sig'))
        for key, row in state.get('posts', {}).items():
            fields = ('bufferPostId', 'scheduledAt', 'status', 'contentFingerprint', 'attemptedAt', 'videoSha256')
            evidence.append({'source': '.private/candy-publisher-state.json', 'day': int(key),
                **{k: row[k] for k in fields if k in row}})
    if not evidence:
        raise CloudError('NO_HISTORY_TO_IMPORT')
    marker = json.loads(MARKER.read_text()) if MARKER.exists() else {}
    return {'exported_at': now_iso(), 'local_disabled': marker.get('disabled') is True,
            'campaign_hash': digest({k: p['approved_hash'] for k, p in load_campaign().items()}),
            'evidence': evidence}


def merge_history(state, history, posts):
    if history['campaign_hash'] != digest({k: p['approved_hash'] for k, p in posts.items()}):
        raise CloudError('HISTORY_CAMPAIGN_MISMATCH')
    # Never reapprove a record or rewrite submitted content during re-import.
    for key, post in posts.items():
        if key not in state['posts']:
            raise CloudError('NEW_CONTENT_REQUIRES_SEPARATE_APPROVAL')
        if state['posts'][key]['approved_hash'] != post['approved_hash']:
            raise CloudError('APPROVED_CONTENT_CHANGED')
    for item in history['evidence']:
        number = item.get('day', item.get('post'))
        if number is None:
            raise CloudError('HISTORY_POST_ID_MISSING')
        key = f'{CAMPAIGN}:{int(number):03d}'
        if key not in state['posts']:
            raise CloudError('UNKNOWN_HISTORICAL_POST')
        p = state['posts'][key]
        if item not in p.setdefault('history', []):
            p['history'].append(item)
        if bid := item.get('bufferPostId'):
            if bid not in p['buffer_ids']:
                p['buffer_ids'].append(bid)
        if p['status'] in {'APPROVED', 'FAILED_RENDER'}:
            p['status'] = 'HISTORICAL'
        if str(item.get('status')).upper() in {'PUBLISHING', 'UNCERTAIN', 'SUBMITTING'} and p['status'] != 'SENT':
            p['status'] = 'UNCERTAIN'
    state.update(history_imported=True, history_exported_at=history['exported_at'],
                 local_disabled=history.get('local_disabled', False))
    event(state, 'history_imported')


def initialize():
    posts = load_campaign()
    raw = base64.b64decode(required('CANDY_HISTORY_IMPORT_B64'), validate=True)
    history = json.loads(raw)
    if (datetime.now(timezone.utc) - dt(history['exported_at'])).total_seconds() > 86400:
        raise CloudError('HISTORY_EXPORT_TOO_OLD')
    store = R2State()
    try:
        state, _ = store.load()
    except MissingState:
        state = new_state(posts, required('BUFFER_TIKTOK_CHANNEL_ID'))
        merge_history(state, history, posts)
        store.initialize(state)
    else:
        store.change(lambda s: merge_history(s, history, posts))
    from candy_cloud import reconcile, report
    b = Buffer()
    b.channel_check()
    provider_history = b.list_posts()
    def retain_provider_history(s):
        for post in provider_history:
            s.setdefault('provider_history', {})[post['id']] = post
    store.change(retain_provider_history)
    reconcile(store, b)
    report(store.load()[0], posts)

def sync_content():
    posts = load_campaign()
    store = R2State()

    def change(s):
        for key, row in s['posts'].items():
            if key not in posts or posts[key]['approved_hash'] != row['approved_hash']:
                raise CloudError('EXISTING_APPROVED_CONTENT_CHANGED')
        additions = [p for key, p in posts.items() if key not in s['posts']]
        if additions and min(p['number'] for p in additions) <= max(p['number'] for p in s['posts'].values()):
            raise CloudError('CONTENT_MUST_BE_APPEND_ONLY')
        if any(dt(p['scheduled_at']) <= datetime.now(timezone.utc) + timedelta(minutes=45) for p in additions):
            raise CloudError('NEW_CONTENT_MUST_BE_SCHEDULED_IN_THE_FUTURE')
        for post in additions:
            s['posts'][post['id']] = compact_post(post)
        event(s, 'content_synced')
        return len(additions)
    print(f'Approved content appended: {store.change(change)}')


def gh(args, value=None):
    result = subprocess.run(['gh', *args], input=value, text=True, encoding='utf-8',
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise CloudError('GITHUB_CONFIGURATION_FAILED_' + args[0].upper())
    return result.stdout


def configure():
    load_local_env()
    # Values enter gh through stdin, never shell arguments or stdout.
    names = ['BUFFER_API_KEY', 'BUFFER_TIKTOK_CHANNEL_ID', 'R2_ACCOUNT_ID',
             'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_PUBLIC_BASE_URL']
    for name in names:
        gh(['secret', 'set', name, '--repo', REPO], required(name))
        print('Configured encrypted secret: ' + name)
    for name in ('CANDY_STATE_ACCESS_KEY_ID', 'CANDY_STATE_SECRET_ACCESS_KEY'):
        if os.environ.get(name):
            gh(['secret', 'set', name, '--repo', REPO], os.environ[name])
            print('Configured encrypted secret: ' + name)
    history = json.dumps(export_history(), separators=(',', ':')).encode()
    encoded = base64.b64encode(history).decode()
    if len(encoded) > 45000:
        raise CloudError('HISTORY_REQUIRES_PRIVATE_FILE_TRANSFER')
    gh(['secret', 'set', 'CANDY_HISTORY_IMPORT_B64', '--repo', REPO], encoded)
    for name, value in [('CANDY_PUBLISHING_ENABLED', 'false'), ('CANDY_CLOUD_MODE', 'shadow')]:
        gh(['variable', 'set', name, '--repo', REPO, '--body', value])
    print('GitHub setup saved. Publishing disabled; run import-history after state credentials are configured.')


def freeze_local():
    # Preserve local credentials/history. The updated legacy entry points check
    # this marker before any git checkout or external side effect.
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps({'disabled': True, 'at': now_iso(), 'reason': 'GitHub cloud publisher cutover'}) + '\n')
    print('Legacy local publisher disabled. Export/import fresh history before canary activation.')


def activate(store, post_id):
    def change(s):
        runs = s.get('shadow_runs', [])
        expected = digest({k: p['approved_hash'] for k, p in load_campaign().items()})
        runs = [r for r in runs if r.get('campaign_hash') == expected]
        if len(runs) < 3 or (dt(runs[-1]['at']) - dt(runs[0]['at'])).total_seconds() < 48 * 3600:
            raise CloudError('NEED_48_HOURS_OF_SHADOW_RUNS')
        if not s.get('local_disabled') or (datetime.now(timezone.utc) - dt(s['history_exported_at'])).total_seconds() > 3600:
            raise CloudError('FREEZE_LOCAL_AND_IMPORT_FRESH_HISTORY')
        if post_id not in s['posts'] or s['posts'][post_id]['status'] != 'APPROVED':
            raise CloudError('CANARY_MUST_BE_APPROVED')
        if dt(s['posts'][post_id]['scheduled_at']) <= datetime.now(timezone.utc):
            raise CloudError('CANARY_SLOT_EXPIRED')
        if any(p['status'] in {'SUBMITTING', 'UNCERTAIN', 'RENDERING'} for p in s['posts'].values()):
            raise CloudError('RESOLVE_UNCERTAIN_POSTS_FIRST')
        s.update(mode='canary', canary_id=post_id, paused=False)
        event(s, 'canary_activated', post_id)
    store.change(change)


def promote(store):
    def change(s):
        if s.get('mode') != 'canary' or s['posts'].get(s.get('canary_id'), {}).get('status') != 'SENT':
            raise CloudError('CANARY_MUST_BE_CONFIRMED_SENT')
        s.update(mode='live', paused=False)
        event(s, 'live_activated')
    store.change(change)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['configure-github', 'import-history', 'sync-content', 'freeze-local', 'activate-canary', 'promote-live'])
    p.add_argument('--post')
    args = p.parse_args(argv)
    if args.command == 'configure-github':
        configure()
    elif args.command == 'freeze-local':
        freeze_local()
    else:
        if os.environ.get('GITHUB_ACTIONS') != 'true':
            load_local_env()
        if args.command == 'import-history':
            initialize()
        elif args.command == 'sync-content':
            sync_content()
        elif args.command == 'activate-canary':
            activate(R2State(), args.post)
        else:
            promote(R2State())


if __name__ == '__main__':
    try:
        main()
    except CloudError as exc:
        print('Candy setup stopped: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print('Candy setup stopped: ' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
