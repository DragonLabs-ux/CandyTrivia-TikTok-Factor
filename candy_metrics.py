#!/usr/bin/env python3
"""Collect durable 1h/24h/72h Buffer performance checkpoints for Candy TikTok posts.

This is intentionally read-only with respect to Buffer/TikTok. It reconciles
known post IDs, reads metrics, then stores snapshots in the private R2 publisher
state. Missing metrics are recorded as unavailable at that checkpoint rather
than treated as zero performance.
"""
from __future__ import annotations

from datetime import datetime, timezone

import candy_cloud as c

CHECKPOINT_HOURS = (1, 24, 72)
HOOK_EXPERIMENT_START_DAY = 25


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


def collect(store: c.R2State, buffer: c.Buffer) -> int:
    c.reconcile(store, buffer)
    state, _ = store.load()
    now = datetime.now(timezone.utc)
    snapshots: dict[str, list[tuple[str, dict]]] = {}

    for key, post in state['posts'].items():
        if post.get('status') != 'SENT' or not post.get('buffer_post_id') or not post.get('sent_at'):
            continue
        age_hours = (now - c.dt(post['sent_at'])).total_seconds() / 3600
        existing = post.get('metrics', {})
        due = [hours for hours in CHECKPOINT_HOURS if age_hours >= hours and str(hours) not in existing]
        if not due:
            continue

        try:
            remote = buffer.get(post['buffer_post_id'], metrics=True)
        except c.CloudError:
            continue

        raw_metrics = remote.get('metrics') or []
        timing_offset = None
        if post.get('scheduled_at') and remote.get('sentAt'):
            timing_offset = (c.dt(remote['sentAt']) - c.dt(post['scheduled_at'])).total_seconds() / 60
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
                'availability': 'available' if raw_metrics else 'unavailable',
                'metrics_updated_at': remote.get('metricsUpdatedAt'),
                'planned_at': post.get('scheduled_at'),
                'sent_at': remote.get('sentAt') or post.get('sent_at'),
                'timing_offset_minutes': timing_offset,
                'hook_variant': hook_variant(int(post.get('number') or key.rsplit(':', 1)[-1])),
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
