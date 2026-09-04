#!/usr/bin/env python3
"""GitHub runner: approved JSON -> Remotion -> R2 -> Buffer -> TikTok.

The private R2 state object is authoritative. Every state change is conditional
on its ETag; missing/corrupt state fails closed. Buffer POSTs are NEVER retried.
No public comments, deletes, paid images, or generated trivia are sent here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('America/Phoenix')
MEDIA_BUCKET = 'candy-trivia-media'
STATE_BUCKET = 'candy-trivia-control'
STATE_KEY = 'publisher/v1/state.json'
CAMPAIGN = 'candy-premium-2026-09'
DELIVERY_STATES = {'SUBMITTING', 'UNCERTAIN', 'SCHEDULED', 'SENT', 'HISTORICAL', 'BLOCKED'}


class CloudError(RuntimeError):
    pass


class Conflict(CloudError):
    pass


class MissingState(CloudError):
    pass


class NotFound(CloudError):
    pass


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def dt(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise CloudError('TIMEZONE_REQUIRED')
    return parsed


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise CloudError('MISSING_' + name)
    return value


def load_local_env():
    # Only explicit operator commands call this. GitHub uses encrypted secrets.
    for file in (ROOT / '.env', ROOT / '.private/cloud.env'):
        if file.exists():
            for line in file.read_text(encoding='utf-8-sig').splitlines():
                if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                    continue
                name, value = line.split('=', 1)
                os.environ.setdefault(name.strip(), value.strip().strip('"\''))


def s3_client(state=False):
    import boto3
    from botocore.config import Config
    prefix = 'CANDY_STATE' if state else 'R2'
    account = required('R2_ACCOUNT_ID')
    if not re.fullmatch('[a-f0-9]{32}', account):
        raise CloudError('INVALID_R2_ACCOUNT')
    return boto3.client('s3', region_name='auto',
        endpoint_url=f'https://{account}.r2.cloudflarestorage.com',
        aws_access_key_id=required(prefix + '_ACCESS_KEY_ID'),
        aws_secret_access_key=required(prefix + '_SECRET_ACCESS_KEY'),
        config=Config(connect_timeout=15, read_timeout=90, retries={'total_max_attempts': 1},
                      request_checksum_calculation='when_required', response_checksum_validation='when_required'))


def client_code(exc):
    return str(getattr(exc, 'response', {}).get('Error', {}).get('Code', 'NETWORK'))


def validate_state(s):
    if s.get('version') != 1 or not s.get('channel_id') or not isinstance(s.get('posts'), dict):
        raise CloudError('INVALID_STATE')
    hashes, buffer_ids = {}, {}
    for key, row in s['posts'].items():
        if row.get('id') != key or not row.get('content_hash'):
            raise CloudError('INVALID_POST_STATE')
        if row['content_hash'] in hashes:
            raise CloudError('DUPLICATE_CONTENT_STATE')
        hashes[row['content_hash']] = key
        for bid in row.get('buffer_ids', []):
            if bid in buffer_ids and buffer_ids[bid] != key:
                raise CloudError('DUPLICATE_BUFFER_ID_STATE')
            buffer_ids[bid] = key


class R2State:
    def __init__(self, client=None):
        self.client = client or s3_client(state=True)

    def load(self):
        try:
            r = self.client.get_object(Bucket=STATE_BUCKET, Key=STATE_KEY)
            data = r['Body'].read(10_000_001)
            if len(data) > 10_000_000:
                raise CloudError('STATE_TOO_LARGE')
            state = json.loads(data)
            validate_state(state)
            if state['channel_id'] != required('BUFFER_TIKTOK_CHANNEL_ID'):
                raise CloudError('CHANNEL_MISMATCH')
            return state, r['ETag']
        except CloudError:
            raise
        except Exception as exc:
            if client_code(exc) in {'NoSuchKey', '404'}:
                raise MissingState('STATE_MISSING_IMPORT_HISTORY_FIRST') from None
            raise CloudError('STATE_READ_FAILED') from None

    def save(self, state, etag):
        validate_state(state)
        state['revision'] = uuid.uuid4().hex  # Prevent identical-byte ABA.
        state['updated_at'] = now_iso()
        condition = {'IfMatch': etag} if etag else {'IfNoneMatch': '*'}
        try:
            self.client.put_object(Bucket=STATE_BUCKET, Key=STATE_KEY,
                Body=json.dumps(state, ensure_ascii=False).encode(),
                ContentType='application/json', CacheControl='private, no-store', **condition)
        except Exception as exc:
            if client_code(exc) in {'PreconditionFailed', '412', 'ConditionalRequestConflict'}:
                raise Conflict('STATE_CONFLICT') from None
            # The write may have committed; never replay external side effects.
            raise CloudError('STATE_WRITE_UNCERTAIN') from None

    def initialize(self, state):
        # An immutable witness prevents a lost/deleted ledger being recreated
        # from an old local export. Recovery then requires an explicit audit.
        try:
            self.client.put_object(Bucket=STATE_BUCKET, Key='publisher/v1/bootstrap.json',
                Body=json.dumps({'initialized_at': now_iso(), 'channel_id': state['channel_id']}).encode(),
                ContentType='application/json', CacheControl='private,no-store', IfNoneMatch='*')
        except Exception:
            raise CloudError('BOOTSTRAP_EXISTS_OR_UNCERTAIN_RECOVER_HISTORY') from None
        self.save(state, None)

    def change(self, fn):
        for _ in range(8):
            state, etag = self.load()
            result = fn(state)  # Pure in-memory state operation, never network.
            try:
                self.save(state, etag)
                return result
            except Conflict:
                continue
        raise Conflict('STATE_BUSY')


def event(state, name, post_id=None):
    state.setdefault('events', []).append({'at': now_iso(), 'event': name, 'post': post_id})
    # Delivery attempts live on their post forever; these are recent UI events.
    state['events'] = state['events'][-500:]


def load_campaign():
    posts = {}
    questions, decks = set(), set()
    for file in sorted((ROOT / 'examples/auto').glob('post-*.json')):
        data = json.loads(file.read_text(encoding='utf-8-sig'))
        number = data.get('day')
        if not isinstance(number, int) or number < 1:
            raise CloudError('INVALID_POST_NUMBER')
        post_id = f'{CAMPAIGN}:{number:03d}'
        if post_id in posts:
            raise CloudError('DUPLICATE_POST_NUMBER')
        dt(data['scheduledAt'])
        if data.get('visualTemplate', 'A') not in ('A', 'B') or data['q3'].get('withhold') is not True:
            raise CloudError('INVALID_TEMPLATE_OR_Q3')
        caption = data.get('caption', '')
        if len(caption) > 120 or len(re.findall(r'#[\w]+', caption)) != 4:
            raise CloudError('INVALID_CAPTION')
        for slot in ('q1', 'q2', 'q3'):
            q = data[slot]
            if not isinstance(q.get('question'), str) or not isinstance(q.get('answer'), str):
                raise CloudError('INVALID_QUESTION')
            normalized = ' '.join(q['question'].casefold().split())
            if normalized in questions:
                raise CloudError('DUPLICATE_QUESTION')
            questions.add(normalized)
        content_hash = digest({k: data[k] for k in ('q1', 'q2', 'q3')})
        if content_hash in decks:
            raise CloudError('DUPLICATE_DECK')
        decks.add(content_hash)
        posts[post_id] = {'id': post_id, 'file': str(file.relative_to(ROOT)), 'number': number,
            'scheduled_at': data['scheduledAt'], 'content_hash': content_hash,
            'approved_hash': digest(data), 'status': 'APPROVED', 'buffer_ids': [], 'attempts': [], 'data': data}
    if not posts:
        raise CloudError('NO_CAMPAIGN')
    counts = Counter(dt(p['scheduled_at']).astimezone(TZ).date() for p in posts.values())
    if max(counts.values()) > 3:
        raise CloudError('MORE_THAN_THREE_PER_DAY')
    return posts


def compact_post(row):
    return {k: v for k, v in row.items() if k != 'data'}


def new_state(posts, channel):
    return {'version': 1, 'channel_id': channel, 'mode': 'shadow', 'paused': False,
        'history_imported': False, 'local_disabled': False, 'shadow_runs': [],
        'posts': {k: compact_post(v) for k, v in posts.items()}, 'events': []}


def candidates(state, posts, now, horizon=72):
    chosen = []
    for key, item in posts.items():
        existing = state['posts'].get(key)
        if not existing or existing['approved_hash'] != item['approved_hash']:
            continue  # New/changed content requires explicit reviewed import.
        when = dt(item['scheduled_at'])
        if not now + timedelta(minutes=45) <= when <= now + timedelta(hours=horizon):
            continue
        status = existing['status']
        if status == 'RENDERING' and existing.get('lease_until', 0) < now.timestamp():
            status = 'APPROVED'  # No Buffer submission has been allowed yet.
        if status in {'APPROVED', 'FAILED_RENDER'} and existing.get('render_attempts', 0) < 3:
            chosen.append(item)
    return sorted(chosen, key=lambda row: dt(row['scheduled_at']))


def claim(store, post, owner, now):
    def change(s):
        if s.get('paused') or not s.get('history_imported') or not s.get('local_disabled'):
            raise CloudError('PUBLISHING_GATE_CLOSED')
        if s.get('mode') not in {'canary', 'live'}:
            raise CloudError('SHADOW_MODE')
        if s['mode'] == 'canary' and s.get('canary_id') != post['id']:
            raise CloudError('NOT_CANARY_POST')
        p = s['posts'][post['id']]
        allowed = p['status'] in {'APPROVED', 'FAILED_RENDER'} or (
            p['status'] == 'RENDERING' and p.get('lease_until', 0) < now.timestamp())
        if not allowed or p['approved_hash'] != post['approved_hash'] or p.get('render_attempts', 0) >= 3:
            raise CloudError('POST_ALREADY_CLAIMED_OR_CHANGED')
        p.update(status='RENDERING', owner=owner, lease_until=now.timestamp() + 3600,
                 render_attempts=p.get('render_attempts', 0) + 1)
        event(s, 'claimed', post['id'])
    store.change(change)


def before_submit(store, post, owner, video, now):
    def change(s):
        p = s['posts'][post['id']]
        if s.get('paused') or not s.get('local_disabled') or s.get('mode') not in {'canary', 'live'}:
            raise CloudError('PUBLISHING_GATE_CLOSED')
        if s['mode'] == 'canary' and s.get('canary_id') != post['id']:
            raise CloudError('NOT_CANARY_POST')
        if p['status'] != 'RENDERING' or p.get('owner') != owner or p.get('lease_until', 0) <= now.timestamp():
            raise CloudError('CLAIM_LOST')
        if dt(p['scheduled_at']) <= now + timedelta(minutes=15):
            raise CloudError('SLOT_TOO_CLOSE')
        if p['approved_hash'] != post['approved_hash']:
            raise CloudError('APPROVED_CONTENT_CHANGED')
        p.update(status='SUBMITTING', video=video, submitted_at=now.isoformat())
        p['attempts'].append({'id': owner, 'at': now.isoformat(), 'status': 'SUBMITTING', 'video_hash': video['sha256']})
        event(s, 'submitting', post['id'])
    store.change(change)


def record_result(store, post_id, owner, result=None):
    def change(s):
        p = s['posts'][post_id]
        if p.get('owner') != owner or p['status'] not in {'SUBMITTING', 'UNCERTAIN'}:
            raise CloudError('SUBMISSION_STATE_CHANGED')
        if result:
            if result['id'] not in p['buffer_ids']:
                p['buffer_ids'].append(result['id'])
            status = 'SENT' if result.get('status') == 'sent' else 'SCHEDULED' if result.get('status') == 'scheduled' else 'BLOCKED'
            p.update(status=status, buffer_post_id=result['id'], due_at=result.get('dueAt'), sent_at=result.get('sentAt'))
        else:
            p['status'] = 'UNCERTAIN'
        p['attempts'][-1]['status'] = p['status']
        event(s, p['status'].lower(), post_id)
    store.change(change)


class Buffer:
    def __init__(self):
        self.channel = required('BUFFER_TIKTOK_CHANNEL_ID')

    def query(self, query, variables=None):
        request = urllib.request.Request('https://api.buffer.com',
            data=json.dumps({'query': query, 'variables': variables or {}}).encode(),
            headers={'Authorization': 'Bearer ' + required('BUFFER_API_KEY'), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=60) as r:
                payload = json.load(r)
        except Exception:
            raise CloudError('BUFFER_REQUEST_FAILED') from None
        if payload.get('errors'):
            if any('post not found' in str(e.get('message', '')).lower() for e in payload['errors']):
                raise NotFound('BUFFER_POST_NOT_FOUND')
            raise CloudError('BUFFER_GRAPHQL_ERROR')
        if not isinstance(payload.get('data'), dict):
            raise CloudError('BUFFER_BAD_RESPONSE')
        return payload['data']

    def channel_check(self):
        data = self.query('query($id:ChannelId!){channel(input:{id:$id}){id name service}}', {'id': self.channel})
        if data['channel']['service'] != 'tiktok' or data['channel']['id'] != self.channel:
            raise CloudError('NOT_CANDY_TIKTOK_CHANNEL')
        return data['channel']

    def get(self, bid, metrics=False):
        fields = 'metrics {type name value unit} metricsUpdatedAt' if metrics else ''
        data = self.query('query($id:PostId!){post(input:{id:$id}){id channelId status dueAt sentAt externalLink text ' + fields + '}}', {'id': bid})
        p = data.get('post')
        if not p or p.get('channelId') != self.channel:
            raise CloudError('BUFFER_CHANNEL_MISMATCH')
        return p

    def list_posts(self):
        orgs = self.query('{account{organizations{id}}}')['account']['organizations']
        found = []
        for org in orgs:
            cursor = None
            for _ in range(50):
                d = self.query('query($input:PostsInput!,$after:String){posts(input:$input,first:100,after:$after){edges{node{id channelId status dueAt sentAt text assets{source}}} pageInfo{hasNextPage endCursor}}}',
                    {'input': {'organizationId': org['id'], 'filter': {'channelIds': [self.channel]}}, 'after': cursor})['posts']
                found.extend(e['node'] for e in d['edges'])
                if not d['pageInfo']['hasNextPage']:
                    break
                cursor = d['pageInfo']['endCursor']
            else:
                raise CloudError('BUFFER_PAGINATION_LIMIT')
        return list({p['id']: p for p in found if p['channelId'] == self.channel}.values())

    def submit(self, post, video):
        value = {'channelId': self.channel, 'text': post['data']['caption'], 'needsApproval': False,
            'schedulingType': 'automatic', 'mode': 'customScheduled', 'dueAt': post['scheduled_at'],
            'aiAssisted': True, 'metadata': {'tiktok': {'isAiGenerated': True}},
            'assets': [{'video': {'url': video['url'], 'metadata': {'thumbnailOffset': 2000}}}]}
        result = self.query('mutation($input:CreatePostInput!){createPost(input:$input){__typename ... on PostActionSuccess{post{id dueAt sentAt status}} ... on MutationError{message}}}', {'input': value})['createPost']
        if result.get('__typename') != 'PostActionSuccess' or not result.get('post', {}).get('id'):
            raise CloudError('BUFFER_SUBMISSION_NOT_CONFIRMED')
        return result['post']


def reconcile(store, buffer):
    state, _ = store.load()
    updates = {}
    pending_unknown = any(p['status'] in {'SUBMITTING', 'UNCERTAIN'} and not p.get('buffer_ids') and p.get('video') for p in state['posts'].values())
    live = buffer.list_posts() if pending_unknown else []
    recovered = {}
    for key, p in state['posts'].items():
        if p['status'] not in {'SCHEDULED', 'HISTORICAL', 'SUBMITTING', 'UNCERTAIN', 'BLOCKED'}:
            continue
        ids = p.get('buffer_ids', [])
        if not ids and p.get('video'):
            matches = [item for item in live if any(a.get('source') == p['video']['url'] for a in item.get('assets', []))]
            if len(matches) == 1:
                ids = [matches[0]['id']]
                recovered[key] = ids
        observations = []
        for bid in ids:
            try:
                observations.append(buffer.get(bid))
            except NotFound:
                observations.append({'id': bid, 'status': 'not_found'})
        updates[key] = observations
    def change(s):
        for key, seen in updates.items():
            p = s['posts'][key]
            for bid in recovered.get(key, []):
                if bid not in p['buffer_ids']:
                    p['buffer_ids'].append(bid)
            p['observations'] = [{k: row.get(k) for k in ('id', 'status', 'dueAt', 'sentAt', 'externalLink')} for row in seen]
            p['reconciled_at'] = now_iso()
            sent = [r for r in seen if r['status'] == 'sent']
            scheduled = [r for r in seen if r['status'] == 'scheduled']
            if sent:
                p.update(status='SENT', sent_at=sent[0].get('sentAt'), buffer_post_id=sent[0]['id'])
            elif p['status'] == 'SENT':
                continue
            elif len(scheduled) == 1:
                p.update(status='SCHEDULED', buffer_post_id=scheduled[0]['id'], due_at=scheduled[0].get('dueAt'))
            elif len(scheduled) > 1:
                p.update(status='BLOCKED', error='MULTIPLE_SCHEDULED_COPIES')
            elif p['status'] in {'SUBMITTING', 'UNCERTAIN', 'SCHEDULED'}:
                p.update(status='UNCERTAIN', error='RECONCILIATION_REQUIRED')
            # No IDs / not-found never restores APPROVED.
        s['last_reconcile'] = now_iso()
    store.change(change)


def render(post):
    import candy_production_validation as validation
    env = os.environ.copy()
    env.update(OPENAI_IMAGES_ENABLED='0', TTS_ENABLED='1', TTS_VOICE='en-US-AvaNeural',
               TTS_RATE='+8%', TTS_PITCH='+0Hz', CANDY_PUBLISHING_DISABLED='1')
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    # Keep verbose render failures and trivia/answers out of public Actions logs.
    result = subprocess.run([npm, 'run', 'render-local', '--', post['file']], cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3000)
    if result.returncode:
        raise CloudError('RENDER_FAILED')
    file = ROOT / 'out' / f"candy-trivia-day-{post['number']:03d}.mp4"
    validation.validate_media(post['data'].get('visualTemplate', 'A'), file, file.with_suffix('.srt'))
    validation.validate_narration(post['number'])
    return file


def upload(post, file):
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    key = f"candy/cloud-v1/{post['number']:03d}/{sha}.mp4"
    client = s3_client()
    try:
        existing = client.head_object(Bucket=MEDIA_BUCKET, Key=key)
        if existing['ContentLength'] != file.stat().st_size or existing.get('Metadata', {}).get('sha256') != sha:
            raise CloudError('IMMUTABLE_MEDIA_CONFLICT')
    except CloudError:
        raise
    except Exception as exc:
        if client_code(exc) not in {'404', 'NoSuchKey', 'NotFound'}:
            raise CloudError('MEDIA_READ_FAILED') from None
        try:
            client.put_object(Bucket=MEDIA_BUCKET, Key=key, Body=file.read_bytes(), ContentType='video/mp4',
                CacheControl='public,max-age=31536000,immutable', Metadata={'sha256': sha}, IfNoneMatch='*')
        except Exception:
            raise CloudError('MEDIA_UPLOAD_FAILED') from None
    base = required('R2_PUBLIC_BASE_URL').rstrip('/')
    if not base.startswith('https://'):
        raise CloudError('HTTPS_MEDIA_REQUIRED')
    url = base + '/' + key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as r:
            if r.status != 200 or r.headers.get_content_type() != 'video/mp4' or int(r.headers.get('Content-Length', 0)) != file.stat().st_size:
                raise CloudError('PUBLIC_MEDIA_INVALID')
    except Exception:
        raise CloudError('PUBLIC_MEDIA_CHECK_FAILED') from None
    return {'url': url, 'key': key, 'sha256': sha, 'bytes': file.stat().st_size}


def render_key(post):
    # Include every renderer/audio/font/art input. Schedules don't affect pixels.
    files = [ROOT / 'package-lock.json']
    for folder in ('src', 'scripts', 'public/art'):
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file())
    renderer = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    content = {k: v for k, v in post['data'].items() if k not in {'scheduledAt', 'meta'}}
    return digest({'content': content, 'renderer': renderer,
        'voice': ['en-US-AvaNeural', '+8%', '+0Hz'], 'pipeline': 'cloud-v1'})


def cached_media(store, post):
    state, _ = store.load()
    video = state['posts'][post['id']].get('cached_video')
    if not video or video.get('render_key') != render_key(post):
        return None
    try:
        r = s3_client().head_object(Bucket=MEDIA_BUCKET, Key=video['key'])
        if r['ContentLength'] != video['bytes'] or r.get('Metadata', {}).get('sha256') != video['sha256']:
            raise CloudError('CACHED_MEDIA_MISMATCH')
        with urllib.request.urlopen(urllib.request.Request(video['url'], method='HEAD'), timeout=30) as public:
            if public.status != 200 or public.headers.get_content_type() != 'video/mp4' or int(public.headers.get('Content-Length', 0)) != video['bytes']:
                raise CloudError('CACHED_MEDIA_INVALID')
        return video
    except Exception:
        raise CloudError('CACHED_MEDIA_VERIFICATION_FAILED') from None


def deliver(store, buffer, post, render_fn=render, upload_fn=upload, cache_fn=cached_media):
    owner = uuid.uuid4().hex
    claim(store, post, owner, datetime.now(timezone.utc))
    try:
        video = cache_fn(store, post) or upload_fn(post, render_fn(post))
        video['render_key'] = render_key(post)
        def remember(s):
            p = s['posts'][post['id']]
            if p.get('owner') != owner or p['status'] != 'RENDERING':
                raise CloudError('CLAIM_LOST')
            p['cached_video'] = video
        store.change(remember)
        # Refresh external queue immediately before the irreversible call. Any
        # same-caption/same-slot item or exhausted daily count blocks submission.
        live = buffer.list_posts()
        target_day = dt(post['scheduled_at']).astimezone(TZ).date()
        same_day = [p for p in live if p.get('dueAt') and dt(p['dueAt']).astimezone(TZ).date() == target_day
                    and p['status'] in {'sent', 'scheduled', 'pending', 'sending'}]
        if len(same_day) >= 3 or any(p.get('text') == post['data']['caption'] for p in same_day):
            raise CloudError('BUFFER_QUEUE_CONFLICT')
        before_submit(store, post, owner, video, datetime.now(timezone.utc))
    except Exception:
        def failed(s):
            p = s['posts'][post['id']]
            if p['status'] == 'RENDERING' and p.get('owner') == owner:
                p.update(status='FAILED_RENDER', error='PRE_SUBMISSION_FAILED')
        store.change(failed)
        raise
    try:
        result = buffer.submit(post, video)  # Exactly one call, no retry wrapper.
        record_result(store, post['id'], owner, result)
    except Exception:
        try:
            record_result(store, post['id'], owner)
        except Exception:
            pass  # Durable SUBMITTING already prevents retries if R2 is down.
        raise CloudError('SUBMISSION_UNCERTAIN_CHECK_BUFFER') from None


def analytics(store, buffer):
    state, _ = store.load()
    collected = {}
    for key, p in state['posts'].items():
        if p['status'] != 'SENT' or not p.get('buffer_post_id') or not p.get('sent_at'):
            continue
        age = (datetime.now(timezone.utc) - dt(p['sent_at'])).total_seconds() / 3600
        windows = [h for h in (24, 72, 168) if age >= h and str(h) not in p.get('metrics', {})]
        if not windows:
            continue
        try:
            r = buffer.get(p['buffer_post_id'], metrics=True)
            collected[key] = {'window': str(max(windows)), 'data': {'collected_at': now_iso(),
                'age_hours': age, 'source': 'buffer_experimental', 'updated_at': r.get('metricsUpdatedAt'),
                'values': r.get('metrics'), 'availability': 'available' if r.get('metrics') else 'unavailable'}}
        except CloudError:
            continue  # Metrics cannot authorize/block a submission.
    def change(s):
        for key, r in collected.items():
            s['posts'][key].setdefault('metrics', {})[r['window']] = r['data']
        s['last_analytics_attempt'] = now_iso()
    store.change(change)


def report(state, posts, planned=None):
    now = datetime.now(timezone.utc)
    future_days = {dt(p['scheduled_at']).astimezone(TZ).date() for p in state['posts'].values()
                   if dt(p['scheduled_at']) > now and p['status'] in {'APPROVED', 'SCHEDULED'}}
    value = {'mode': state.get('mode'), 'paused': state.get('paused'),
        'statuses': dict(Counter(p['status'] for p in state['posts'].values())),
        'future_content_days': len(future_days), 'content_low': len(future_days) < 7,
        'would_process': [p['id'] for p in planned or []],
        'attention': [p['id'] for p in state['posts'].values() if p['status'] in {'UNCERTAIN', 'SUBMITTING', 'BLOCKED'}],
        'local_publisher_disabled': state.get('local_disabled', False)}
    print(json.dumps(value, indent=2))
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(path, 'a', encoding='utf-8') as f:
            f.write('Candy cloud status\n\n```json\n' + json.dumps(value, indent=2) + '\n```\n')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['status', 'dry-run', 'shadow', 'refill', 'canary', 'render-only', 'analytics', 'pause'], default='status')
    parser.add_argument('--post', help='Exact approved post ID for render-only/canary')
    parser.add_argument('--local-env', action='store_true')
    args = parser.parse_args(argv)
    if args.local_env:
        load_local_env()
    posts = load_campaign()
    if args.mode == 'render-only':
        if args.post not in posts:
            raise CloudError('EXACT_POST_REQUIRED')
        render(posts[args.post])
        print('Production render and media/narration checks passed; nothing uploaded or submitted.')
        return 0
    store = R2State()
    state, _ = store.load()
    if args.mode == 'pause':
        store.change(lambda s: s.update(paused=True))
        print('New submissions paused. Existing Buffer queue is unchanged.')
        return 0
    if args.mode in {'status', 'dry-run'}:
        report(state, posts, candidates(state, posts, datetime.now(timezone.utc)))
        return 0
    buffer = Buffer()
    buffer.channel_check()
    reconcile(store, buffer)
    state, _ = store.load()
    planned = candidates(state, posts, datetime.now(timezone.utc))
    if args.mode == 'shadow':
        def shadow(s):
            s.setdefault('shadow_runs', []).append({'at': now_iso(), 'posts': [p['id'] for p in planned],
                'campaign_hash': digest({k: v['approved_hash'] for k, v in posts.items()})})
            s['shadow_runs'] = s['shadow_runs'][-200:]
        store.change(shadow)
    elif args.mode == 'analytics':
        analytics(store, buffer)
    else:
        if os.environ.get('CANDY_PUBLISHING_ENABLED') != 'true':
            raise CloudError('PUBLISHING_DISABLED')
        if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF') != 'refs/heads/main':
            raise CloudError('PRODUCTION_REQUIRES_MAIN_GITHUB_RUNNER')
        if state.get('paused') or not state.get('local_disabled'):
            raise CloudError('PUBLISHING_GATE_CLOSED')
        live = buffer.list_posts()
        queued = sum(p['status'] in {'scheduled', 'pending', 'sending'} for p in live)
        capacity = max(0, min(9, 10 - queued))
        if args.mode == 'canary':
            planned = [p for p in planned if p['id'] == state.get('canary_id') == args.post][:1]
        elif state.get('mode') != 'live':
            raise CloudError('LIVE_MODE_NOT_ACTIVATED')
        for post in planned[:capacity]:
            print('Processing ' + post['id'], flush=True)
            deliver(store, buffer, post)
    state, _ = store.load()
    value = report(state, posts, planned)
    return 2 if value['attention'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except CloudError as exc:
        print('Candy stopped: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        # Never emit provider payloads, headers, credential values or traceback.
        print('Candy stopped: ' + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
