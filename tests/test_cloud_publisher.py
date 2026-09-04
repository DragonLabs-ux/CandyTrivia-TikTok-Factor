from __future__ import annotations
import copy
import io
import json
import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candy_cloud as c
import candy_cloud_admin as admin


class S3Error(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class AtomicS3:
    def __init__(self):
        self.body = None
        self.etag = None
        self.lock = threading.Lock()
        self.version = 0
        self.fail_writes = False

    def get_object(self, **kwargs):
        with self.lock:
            if self.body is None:
                raise S3Error('NoSuchKey')
            return {'Body': io.BytesIO(self.body), 'ETag': self.etag}

    def put_object(self, **kwargs):
        with self.lock:
            if self.fail_writes:
                raise S3Error('NetworkError')
            if kwargs.get('IfNoneMatch') == '*' and self.body is not None:
                raise S3Error('PreconditionFailed')
            if 'IfMatch' in kwargs and kwargs['IfMatch'] != self.etag:
                raise S3Error('PreconditionFailed')
            self.version += 1
            self.etag = str(self.version)
            self.body = kwargs['Body']
            return {'ETag': self.etag}


class FakeBuffer:
    def __init__(self, timeout=False):
        self.calls = 0
        self.timeout = timeout
        self.found = {}

    def submit(self, post, video):
        self.calls += 1
        if self.timeout:
            raise c.CloudError('timeout after provider accepted')
        return {'id': 'buffer-new', 'status': 'scheduled', 'dueAt': post['scheduled_at']}

    def list_posts(self):
        return list(self.found.values())

    def get(self, bid):
        if bid not in self.found:
            raise c.NotFound('not found')
        return self.found[bid]


class WitnessS3(AtomicS3):
    def __init__(self):
        super().__init__()
        self.witness = False

    def put_object(self, **kwargs):
        if kwargs['Key'].endswith('bootstrap.json'):
            if self.witness:
                raise S3Error('PreconditionFailed')
            self.witness = True
            return {'ETag': 'bootstrap'}
        return super().put_object(**kwargs)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'BUFFER_TIKTOK_CHANNEL_ID': 'candy-test'}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.now = datetime.now(timezone.utc)
        self.post = {'id': c.CAMPAIGN + ':100', 'number': 100, 'file': 'example.json',
            'scheduled_at': (self.now + timedelta(hours=6)).isoformat(), 'status': 'APPROVED',
            'approved_hash': 'approved', 'content_hash': 'unique', 'buffer_ids': [], 'attempts': [],
            'data': {'caption': 'Quiz'}}
        self.posts = {self.post['id']: self.post}
        self.s3 = AtomicS3()
        self.store = c.R2State(self.s3)
        state = c.new_state(self.posts, 'candy-test')
        state.update(mode='live', history_imported=True, local_disabled=True)
        self.store.save(state, None)
        self.video = {'sha256': 'abc', 'url': 'https://example.test/video.mp4'}

    def current(self):
        return self.store.load()[0]['posts'][self.post['id']]

    def deliver(self, buffer):
        c.deliver(self.store, buffer, self.post, render_fn=lambda p: 'file', upload_fn=lambda p, f: self.video)

    def test_missing_state_fails_closed(self):
        with self.assertRaises(c.MissingState):
            c.R2State(AtomicS3()).load()

    def test_initialization_cannot_overwrite_history(self):
        with self.assertRaises(c.Conflict):
            self.store.save(c.new_state(self.posts, 'candy-test'), None)

    def test_lost_ledger_cannot_be_reinitialized_from_old_import(self):
        client = WitnessS3()
        store = c.R2State(client)
        store.initialize(c.new_state(self.posts, 'candy-test'))
        client.body = None  # Simulate accidental deletion outside the publisher.
        with self.assertRaisesRegex(c.CloudError, 'BOOTSTRAP_EXISTS'):
            store.initialize(c.new_state(self.posts, 'candy-test'))

    def test_bootstrap_without_completed_state_requires_recovery(self):
        client = WitnessS3()
        client.witness = True
        store = c.R2State(client)
        with self.assertRaises(c.CloudError):
            store.initialize(c.new_state(self.posts, 'candy-test'))
        with self.assertRaises(c.MissingState):
            store.load()

    def test_channel_mismatch_stops(self):
        with patch.dict(os.environ, {'BUFFER_TIKTOK_CHANNEL_ID': 'other'}):
            with self.assertRaisesRegex(c.CloudError, 'CHANNEL_MISMATCH'):
                self.store.load()

    def test_stale_write_cannot_overwrite_new_state(self):
        old, etag = self.store.load()
        self.store.change(lambda s: s.update(paused=True))
        with self.assertRaises(c.Conflict):
            self.store.save(old, etag)
        self.assertTrue(self.store.load()[0]['paused'])

    def test_concurrent_claims_have_one_winner(self):
        def attempt(i):
            try:
                c.claim(self.store, self.post, str(i), self.now)
                return True
            except c.CloudError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(12)))
        self.assertEqual(1, sum(results))

    def test_expired_render_owner_is_fenced(self):
        c.claim(self.store, self.post, 'old', self.now - timedelta(hours=2))
        c.claim(self.store, self.post, 'new', self.now)
        with self.assertRaisesRegex(c.CloudError, 'CLAIM_LOST'):
            c.before_submit(self.store, self.post, 'old', self.video, self.now)

    def test_pausing_during_render_prevents_submission(self):
        c.claim(self.store, self.post, 'owner', self.now)
        self.store.change(lambda s: s.update(paused=True))
        with self.assertRaises(c.CloudError):
            c.before_submit(self.store, self.post, 'owner', self.video, self.now)

    def test_shadow_mode_cannot_claim(self):
        self.store.change(lambda s: s.update(mode='shadow'))
        with self.assertRaisesRegex(c.CloudError, 'SHADOW_MODE'):
            c.claim(self.store, self.post, 'owner', self.now)

    def test_local_publisher_must_be_disabled(self):
        self.store.change(lambda s: s.update(local_disabled=False))
        with self.assertRaises(c.CloudError):
            c.claim(self.store, self.post, 'owner', self.now)

    def test_success_records_scheduled_not_sent(self):
        buffer = FakeBuffer()
        self.deliver(buffer)
        self.assertEqual('SCHEDULED', self.current()['status'])
        self.assertEqual(['buffer-new'], self.current()['buffer_ids'])
        self.assertEqual(1, buffer.calls)

    def test_provider_timeout_never_retries(self):
        buffer = FakeBuffer(timeout=True)
        with self.assertRaises(c.CloudError):
            self.deliver(buffer)
        self.assertEqual('UNCERTAIN', self.current()['status'])
        with self.assertRaises(c.CloudError):
            self.deliver(buffer)
        self.assertEqual(1, buffer.calls)

    def test_exact_media_match_recovers_lost_submission_id(self):
        buffer = FakeBuffer(timeout=True)
        with self.assertRaises(c.CloudError):
            self.deliver(buffer)
        buffer.found['recovered'] = {'id': 'recovered', 'status': 'sent',
            'sentAt': self.now.isoformat(), 'assets': [{'source': self.video['url']}]}
        c.reconcile(self.store, buffer)
        self.assertEqual('SENT', self.current()['status'])
        self.assertEqual(['recovered'], self.current()['buffer_ids'])
        self.assertEqual(1, buffer.calls)

    def test_ambiguous_media_matches_stay_uncertain(self):
        buffer = FakeBuffer(timeout=True)
        with self.assertRaises(c.CloudError):
            self.deliver(buffer)
        for bid in ('one', 'two'):
            buffer.found[bid] = {'id': bid, 'status': 'sent', 'assets': [{'source': self.video['url']}]}
        c.reconcile(self.store, buffer)
        self.assertEqual('UNCERTAIN', self.current()['status'])
        self.assertEqual([], self.current()['buffer_ids'])

    def test_existing_cache_skips_renderer(self):
        buffer = FakeBuffer()
        def unexpected_render(p):
            self.fail('Renderer should not run for a verified cached video')
        c.deliver(self.store, buffer, self.post, render_fn=unexpected_render,
                  cache_fn=lambda store, post: self.video)
        self.assertEqual(1, buffer.calls)

    def test_failure_saving_result_leaves_submitting_and_blocks_retry(self):
        s3 = self.s3
        class AcceptedButStorageDown(FakeBuffer):
            def submit(self, post, video):
                result = super().submit(post, video)
                s3.fail_writes = True
                return result
        buffer = AcceptedButStorageDown()
        with self.assertRaises(c.CloudError):
            self.deliver(buffer)
        s3.fail_writes = False
        self.assertEqual('SUBMITTING', self.current()['status'])
        with self.assertRaises(c.CloudError):
            self.deliver(buffer)
        self.assertEqual(1, buffer.calls)

    def test_render_failure_does_not_contact_buffer(self):
        buffer = FakeBuffer()
        def bad_render(p):
            raise c.CloudError('bad media')
        with self.assertRaises(c.CloudError):
            c.deliver(self.store, buffer, self.post, render_fn=bad_render)
        self.assertEqual('FAILED_RENDER', self.current()['status'])
        self.assertEqual(0, buffer.calls)

    def test_missing_provider_id_never_reapproves(self):
        self.deliver(FakeBuffer())
        c.reconcile(self.store, FakeBuffer())
        self.assertEqual('UNCERTAIN', self.current()['status'])
        self.assertEqual([], c.candidates(self.store.load()[0], self.posts, self.now))

    def test_confirmed_delivery_moves_forward(self):
        self.deliver(FakeBuffer())
        b = FakeBuffer()
        b.found['buffer-new'] = {'id': 'buffer-new', 'status': 'sent', 'sentAt': self.now.isoformat()}
        c.reconcile(self.store, b)
        self.assertEqual('SENT', self.current()['status'])
        c.reconcile(self.store, FakeBuffer())
        self.assertEqual('SENT', self.current()['status'])

    def test_modified_content_requires_review(self):
        changed = copy.deepcopy(self.posts)
        changed[self.post['id']]['approved_hash'] = 'new'
        self.assertEqual([], c.candidates(self.store.load()[0], changed, self.now))

    def test_due_or_too_close_posts_are_not_rescheduled(self):
        self.assertEqual([], c.candidates(self.store.load()[0], self.posts, self.now + timedelta(hours=6)))
        self.assertEqual([], c.candidates(self.store.load()[0], self.posts, self.now + timedelta(hours=5, minutes=30)))

    def test_history_import_preserves_manual_evidence(self):
        s = self.store.load()[0]
        history = {'campaign_hash': c.digest({k: p['approved_hash'] for k, p in self.posts.items()}),
            'exported_at': c.now_iso(), 'local_disabled': False,
            'evidence': [{'day': 100, 'status': 'SENT', 'source': 'manual'}]}
        admin.merge_history(s, history, self.posts)
        self.assertEqual('HISTORICAL', s['posts'][self.post['id']]['status'])
        self.assertFalse(s['local_disabled'])

    def test_import_cannot_reapprove_or_erase_sent(self):
        s = self.store.load()[0]
        s['posts'][self.post['id']]['status'] = 'SENT'
        history = {'campaign_hash': c.digest({k: p['approved_hash'] for k, p in self.posts.items()}),
            'exported_at': c.now_iso(), 'local_disabled': True,
            'evidence': [{'day': 100, 'status': 'PUBLISHING', 'source': 'legacy'}]}
        admin.merge_history(s, history, self.posts)
        self.assertEqual('SENT', s['posts'][self.post['id']]['status'])

    def test_canary_cannot_skip_shadow_period(self):
        with patch.object(admin, 'load_campaign', return_value=self.posts):
            with self.assertRaisesRegex(c.CloudError, '48_HOURS'):
                admin.activate(self.store, self.post['id'])

    def test_live_requires_confirmed_canary_delivery(self):
        with self.assertRaisesRegex(c.CloudError, 'CANARY_MUST_BE_CONFIRMED_SENT'):
            admin.promote(self.store)

    def test_canary_only_claims_selected_post(self):
        self.store.change(lambda s: s.update(mode='canary', canary_id='different'))
        with self.assertRaises(c.CloudError):
            c.claim(self.store, self.post, 'owner', self.now)

    def test_duplicate_content_and_provider_ids_are_rejected(self):
        s = self.store.load()[0]
        duplicate = copy.deepcopy(s['posts'][self.post['id']])
        duplicate['id'] = 'second'
        s['posts']['second'] = duplicate
        with self.assertRaisesRegex(c.CloudError, 'DUPLICATE_CONTENT_STATE'):
            c.validate_state(s)
        duplicate['content_hash'] = 'different'
        duplicate['buffer_ids'] = ['same-id']
        s['posts'][self.post['id']]['buffer_ids'] = ['same-id']
        with self.assertRaisesRegex(c.CloudError, 'DUPLICATE_BUFFER_ID_STATE'):
            c.validate_state(s)

    def test_content_sync_is_append_only(self):
        added = copy.deepcopy(self.post)
        added.update(id=c.CAMPAIGN + ':101', number=101,
                     content_hash='new-content', approved_hash='new-approved')
        posts = {self.post['id']: self.post, added['id']: added}
        with patch.object(admin, 'load_campaign', return_value=posts), \
             patch.object(admin, 'R2State', return_value=self.store):
            admin.sync_content()
        self.assertEqual('APPROVED', self.store.load()[0]['posts'][added['id']]['status'])

    def test_content_sync_rejects_existing_changes(self):
        changed = copy.deepcopy(self.post)
        changed['approved_hash'] = 'changed'
        with patch.object(admin, 'load_campaign', return_value={changed['id']: changed}), \
             patch.object(admin, 'R2State', return_value=self.store):
            with self.assertRaisesRegex(c.CloudError, 'EXISTING_APPROVED_CONTENT_CHANGED'):
                admin.sync_content()


if __name__ == '__main__':
    unittest.main()
