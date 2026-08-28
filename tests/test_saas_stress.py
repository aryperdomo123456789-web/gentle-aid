import os
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
STORAGE = Path(tempfile.mkdtemp(prefix='gentle-aid-saas-stress-'))
os.environ['VIRAL_ROOT'] = str(REPO)
os.environ['VIRAL_STORAGE'] = str(STORAGE)
os.environ['SECRET_KEY'] = 'saas-stress-secret-' + ('x' * 40)
sys.path.insert(0, str(REPO / 'backend'))

from app import create_app
from app.config import Config
from app.services import billing, persistent_queue, rate_limits, release_keys, webhook_delivery


class _Response:
    status = 204
    def read(self, limit=-1):
        return b''
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class SaasStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(Config.from_env())
        cls.app.config.update(TESTING=True)
        with cls.app.app_context():
            release_keys.migrate()
            billing.migrate()
            rate_limits.migrate()
            persistent_queue.migrate()
            webhook_delivery.migrate()

    def test_five_tenants_reserve_claim_complete_and_deliver(self):
        accounts = [f'stress-account-{i}' for i in range(5)]
        jobs = [f'stress-job-{i}' for i in range(5)]
        for account in accounts:
            billing.ensure_account(account)
            billing.set_subscription(account, plan_code='agency', status='active')

        barrier = threading.Barrier(5)
        def reserve_and_enqueue(index):
            account = accounts[index]
            job_id = jobs[index]
            barrier.wait(timeout=10)
            billing.reserve_transcription(account, seconds=60, storage_bytes=256, resource_id=job_id, idempotency_key=f'stress-idempotency-{index:02d}-0001')
            billing.reserve_clip(account, resource_id=job_id + '-clip', idempotency_key=f'stress-clip-{index:02d}-0001')
            rate_limits.reserve_job(account, job_id=job_id, idempotency_key=f'stress-tech-{index:02d}-0001', audio_seconds=60, cost_units=1)
            persistent_queue.enqueue(job_id, 'api-transcription', {'synthetic': True, 'source': 'stress'})
            return job_id

        with ThreadPoolExecutor(max_workers=5) as pool:
            accepted = list(pool.map(reserve_and_enqueue, range(5)))
        self.assertEqual(sorted(accepted), sorted(jobs))

        def claim_complete(index):
            item = persistent_queue.claim(f'stress-worker-{index}', job_id=jobs[index], lease_seconds=60)
            self.assertIsNotNone(item)
            self.assertEqual(item['job_id'], jobs[index])
            self.assertTrue(persistent_queue.heartbeat(jobs[index], f'stress-worker-{index}', lease_seconds=60))
            self.assertTrue(persistent_queue.complete(jobs[index], f'stress-worker-{index}'))
            rate_limits.release_active_job(accounts[index], job_id=jobs[index])
            billing.release_storage(accounts[index], resource_id=jobs[index])
            return item['job_id']

        with ThreadPoolExecutor(max_workers=5) as pool:
            completed = list(pool.map(claim_complete, range(5)))
        self.assertEqual(sorted(completed), sorted(jobs))

        calls = []
        def fake_request(url, data=None, method=None, headers=None):
            calls.append((url, headers or {}))
        def fake_open(request, timeout):
            return _Response()
        fake_opener = mock.Mock()
        fake_opener.open.side_effect = fake_open
        webhook_jobs = [
            {'job_id': job_id, 'tool': 'api-transcription', 'status': 'done', 'created_at': '2026-01-01T00:00:00+00:00', 'finished_at': '2026-01-01T00:00:01+00:00', 'meta': {'webhook_url': 'https://consumer.example.test/events', 'webhook_secret': 'stress-secret-' + ('x' * 32)}}
            for job_id in jobs
        ]
        with mock.patch.object(webhook_delivery, '_safe_delivery_url', return_value=True), mock.patch.object(webhook_delivery.urllib.request, 'Request', fake_request), mock.patch.object(webhook_delivery.urllib.request, 'build_opener', return_value=fake_opener):
            with ThreadPoolExecutor(max_workers=5) as pool:
                deliveries = list(pool.map(webhook_delivery.notify_job, webhook_jobs))
        self.assertEqual(len(deliveries), 5)
        self.assertTrue(all(item and item['status'] == 'delivered' and item['attempts'] == 1 for item in deliveries))
        self.assertEqual(len(calls), 5)

        with billing._conn() as conn:
            billing_events = conn.execute("SELECT COUNT(*) AS n FROM billing_usage_events WHERE account_id LIKE 'stress-account-%'").fetchone()['n']
            storage_active = conn.execute("SELECT COUNT(*) AS n FROM billing_storage_reservations WHERE account_id LIKE 'stress-account-%' AND status = 'active'").fetchone()['n']
        with rate_limits._conn() as conn:
            active_jobs = conn.execute("SELECT COUNT(*) AS n FROM api_usage_events WHERE consumer_id LIKE 'stress-account-%' AND kind = 'active_job'").fetchone()['n']
        with persistent_queue._conn() as conn:
            queue_done = conn.execute("SELECT COUNT(*) AS n FROM api_queue WHERE job_id LIKE 'stress-job-%' AND status = 'done'").fetchone()['n']
        self.assertEqual(billing_events, 10)
        self.assertEqual(storage_active, 0)
        self.assertEqual(active_jobs, 0)
        self.assertEqual(queue_done, 5)

        with billing._conn() as conn:
            conn.execute("DELETE FROM billing_usage_events WHERE account_id LIKE 'stress-account-%'")
            conn.execute("DELETE FROM billing_storage_reservations WHERE account_id LIKE 'stress-account-%'")
            conn.execute("DELETE FROM billing_accounts WHERE account_id LIKE 'stress-account-%'")
        with rate_limits._conn() as conn:
            conn.execute("DELETE FROM api_usage_events WHERE consumer_id LIKE 'stress-account-%'")
        with persistent_queue._conn() as conn:
            conn.execute("DELETE FROM api_queue WHERE job_id LIKE 'stress-job-%'")
        with webhook_delivery._conn() as conn:
            conn.execute("DELETE FROM api_webhook_deliveries WHERE job_id LIKE 'stress-job-%'")


if __name__ == '__main__':
    unittest.main()
