#!/usr/bin/env python3
"""Collect durable 1h/24h/72h Buffer performance checkpoints for Candy TikTok posts.

This is read-only with respect to Buffer/TikTok. It supports both the current
local publisher and the cloud publisher during migration. Cloud-owned post IDs
are used directly. Locally-created Buffer posts are associated only when one
sent post uniquely matches BOTH the approved caption and scheduled timestamp.
Ambiguous matches are skipped rather than guessed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import candy_cloud as c

CHECKPOINT_HOURS = (1, 24, 72)
HOOK_EXPERIMENT_START_DAY = 25
MATCH_TOLERANCE_SECONDS = 5 * 60


def hook_variant(number: int) -> str:
    if number < HOOK_EXPERIMENT_START_DAY:
        return 'cover-hook'
    return 'question-first-hook' if number % 2 == 0 else 'cover-hook'


def metric_key(value: object) -> str:
    return ''.join(ch for ch in str(value or '').casefold() if ch.isalnum())


def metric_value(metrics: list[dict], names: tuple[str, ...]):
    wanted = {metric_key(name) for name in names}
    for metric in metrics:
        if metric_key(metric.get('type')) in wanted or metric_key(metric.get('name')) in wanted:
            return metric.get('value')
    return None


def summarize(metrics: list[dict]) -> dict:
    views = metric_value(metrics, ('views', 'videoViews', 'impressions', 'reach'))
    reactions = metric_value(metrics, ('reactions', 'likes'))
    comments = metric_value(metrics, ('comments',))
    shares = metric_value(metrics, ('shares',))
    follows = metric_value(metrics, ('follows', 'newFollowers', 'followers'))
    engagement = metric_value(metrics, ('engagementRate', 'engRate'))
    if engagement is None and isinstance(views, (int, float)) and views > 0:
        engagement = ((reactions or 0) + (comments or 0) + (shares or 0)) / views * 100
    return {
        'views': views,
        'engagement_rate': engagement,
        'comments': comments,
        'shares': shares,
        'follows': follows,
    }


def unique_local_match(campaign_post: dict, live_posts: list[dict]):
    planned = c.dt(campaign_post['scheduled_at'])
    caption = campaign_post['data']['caption']
    matches = []
    for remote in live_posts:
        if remote.get('status') != 'sent' or remote.get('text') != caption or not remote.get('dueAt'):
            continue
        if abs((c.dt(remote['dueAt']) - planned).total_seconds()) <= MATCH_TOLERANCE_SECONDS:
            matches.append(remote)
    return matches[0] if len(matches) == 1 else None


def collect(store: c.R2State, buffer: c.Buffer) -> int:
    # Reconcile cloud-owned IDs first, then independently discover local-publisher
    # posts for analytics only. Discovery never changes delivery authorization.
    c.reconcile(store, buffer)
    state, _ = store.load()
    campaign = c.load_campaign()
    live_posts = buffer.list_posts()
    now = datetime.now(timezone.utc)
    snapshots: dict[str, list[tuple[str, dict]]] = {}

    for key, post in state['posts'].items():
        approved = campaign.get(key)
        if not approved:
            continue

        source = 'cloud-ledger'
        remote_summary = None
        buffer_post_id = post.get('buffer_post_id')
        if buffer_post_id and post.get('status') == 'SENT':
            remote_summary = next((item for item in live_posts if item.get('id') == buffer_post_id), None)
        else:
            remote_summary = unique_local_match(approved, live_posts)
            if remote_summary:
                source = 'local-publisher-match'
                buffer_post_id = remote_summary.get('id')

        if not buffer_post_id or not remote_summary or not remote_summary.get('sentAt'):
            continue

        age_hours = (now - c.dt(remote_summary['sentAt'])).total_seconds() / 3600
        existing = post.get('metrics', {})
        due = [hours for hours in CHECKPOINT_HOURS if age_hours >= hours and str(hours) not in existing]
        if not due:
            continue

        try:
            remote = buffer.get(buffer_post_id, metrics=True)
        except c.CloudError:
            continue

        raw_metrics = remote.get('metrics') or []
        timing_offset = None
        if approved.get('scheduled_at') and remote.get('sentAt'):
            timing_offset = (c.dt(remote['sentAt']) - c.dt(approved['scheduled_at'])).total_seconds() / 60
        summary = summarize(raw_metrics) if raw_metrics else {
            'views': None,
            'engagement_rate': None,
            'comments': None,
            'shares': None,
            'follows': None,
        }

        for hours in due:
            snapshots.setdefault(key, []).append((str(hours), {
                'checkpoint_hours': hours,
                'collected_at': c.now_iso(),
                'age_hours': age_hours,
                'late_by_hours': max(0.0, age_hours - hours),
                'source': 'buffer_experimental',
                'match_source': source,
                'availability': 'available' if raw_metrics else 'unavailable',
                'buffer_post_id': buffer_post_id,
                'metrics_updated_at': remote.get('metricsUpdatedAt'),
                'planned_at': approved.get('scheduled_at'),
                'sent_at': remote.get('sentAt'),
                'timing_offset_minutes': timing_offset,
                'hook_variant': hook_variant(int(approved['number'])),
                'summary': summary,
                'values': raw_metrics,
            }))

    def change(current):
        for key, items in snapshots.items():
            destination = current['posts'][key].setdefault('metrics', {})
            for window, data in items:
                destination.setdefault(window, data)
        current['last_analytics_attempt'] = c.now_iso()
        current['analytics_checkpoints'] = list(CHECKPOINT_HOURS)

    store.change(change)
    return sum(len(items) for items in snapshots.values())


def main() -> int:
    store = c.R2State()
    buffer = c.Buffer()
    buffer.channel_check()
    count = collect(store, buffer)
    print(f'Candy analytics checkpoints collected: {count}')
    print('Configured checkpoints: 1h, 24h, 72h')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
