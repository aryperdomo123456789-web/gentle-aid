from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(tempfile.mkdtemp(prefix="gentle-aid-p0-"))
STORAGE = ROOT / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)
os.environ["VIRAL_ROOT"] = str(REPO)
os.environ["VIRAL_STORAGE"] = str(STORAGE)
os.environ["SECRET_KEY"] = "local-p0-secret-" + ("x" * 40)
os.environ["OWNER_EMAIL"] = "owner@example.test"
os.environ["OWNER_PASSWORD"] = "local-owner-password-123"
os.environ["API_REQUESTS_PER_MINUTE"] = "2"
os.environ["API_JOBS_PER_DAY"] = "1"
os.environ["API_AUDIO_SECONDS_PER_DAY"] = "10"
os.environ["API_COST_UNITS_PER_DAY"] = "1"
sys.path.insert(0, str(REPO / "backend"))

from app import create_app
from app.config import Config
from app.services import persistent_queue, rate_limits


class PersistentQueueAndLimitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app(Config.from_env())
        cls.app.config.update(TESTING=True)
        with cls.app.app_context():
            persistent_queue.migrate()
            rate_limits.migrate()
        cls.consumer = "rk_test_consumer"

    def test_queue_claim_heartbeat_and_complete(self) -> None:
        job_id = "queue-test-complete"
        with self.app.app_context():
            self.assertTrue(persistent_queue.enqueue(job_id, "test", {"value": 1}))
            item = persistent_queue.claim("worker-a", job_id=job_id, lease_seconds=60)
            self.assertIsNotNone(item)
            self.assertEqual(item["job_id"], job_id)
            self.assertTrue(persistent_queue.heartbeat(job_id, "worker-a", lease_seconds=60))
            self.assertTrue(persistent_queue.complete(job_id, "worker-a"))
            self.assertEqual(persistent_queue.get(job_id)["status"], "done")

    def test_retry_is_requeued_and_attempt_is_counted(self) -> None:
        job_id = "queue-test-retry"
        with self.app.app_context():
            persistent_queue.enqueue(job_id, "test", {"value": 2})
            item = persistent_queue.claim("worker-b", job_id=job_id, lease_seconds=60)
            self.assertIsNotNone(item)
            terminal = persistent_queue.fail(
                job_id,
                "PROVIDER_UNAVAILABLE",
                retryable=True,
                worker_id="worker-b",
                max_attempts=2,
                retry_delay_seconds=1,
            )
            self.assertFalse(terminal)
            state = persistent_queue.get(job_id)
            self.assertEqual(state["status"], "queued")
            self.assertEqual(state["attempts"], 1)
            self.assertEqual(state["last_error_code"], "PROVIDER_UNAVAILABLE")

    def test_rate_limit_rejects_third_request_in_window(self) -> None:
        with self.app.app_context():
            rate_limits.record_request(self.consumer)
            rate_limits.record_request(self.consumer)
            with self.assertRaises(rate_limits.LimitExceeded) as ctx:
                rate_limits.record_request(self.consumer)
            self.assertEqual(ctx.exception.code, "RATE_LIMIT_EXCEEDED")
            self.assertGreaterEqual(ctx.exception.retry_after_seconds, 1)

    def test_concurrent_job_limit_is_enforced_and_released(self) -> None:
        consumer = "rk_concurrency_consumer"
        previous_jobs_limit = os.environ.get("API_JOBS_PER_DAY", "1")
        os.environ["API_JOBS_PER_DAY"] = "10"
        os.environ["API_MAX_CONCURRENT_JOBS"] = "2"
        try:
            with self.app.app_context():
                rate_limits.reserve_job(
                    consumer,
                    job_id="concurrent-job-1",
                    idempotency_key="concurrent-key-00000001",
                    audio_seconds=0.1,
                    cost_units=0.1,
                )
                rate_limits.reserve_job(
                    consumer,
                    job_id="concurrent-job-2",
                    idempotency_key="concurrent-key-00000002",
                    audio_seconds=0.1,
                    cost_units=0.1,
                )
                with self.assertRaises(rate_limits.LimitExceeded) as ctx:
                    rate_limits.reserve_job(
                        consumer,
                        job_id="concurrent-job-3",
                        idempotency_key="concurrent-key-00000003",
                        audio_seconds=0.1,
                        cost_units=0.1,
                    )
                self.assertEqual(ctx.exception.code, "CONCURRENT_JOB_LIMIT_EXCEEDED")
                rate_limits.release_job(consumer, job_id="concurrent-job-1", idempotency_key="concurrent-key-00000001")
                rate_limits.reserve_job(
                    consumer,
                    job_id="concurrent-job-3",
                    idempotency_key="concurrent-key-00000003",
                    audio_seconds=0.1,
                    cost_units=0.1,
                )
                rate_limits.release_job(consumer, job_id="concurrent-job-2", idempotency_key="concurrent-key-00000002")
                rate_limits.release_job(consumer, job_id="concurrent-job-3", idempotency_key="concurrent-key-00000003")
        finally:
            os.environ["API_JOBS_PER_DAY"] = previous_jobs_limit

    def test_daily_job_quota_rejects_second_reservation(self) -> None:
        with self.app.app_context():
            rate_limits.reserve_job(
                self.consumer,
                job_id="quota-job-1",
                idempotency_key="quota-key-00000001",
                audio_seconds=3,
                cost_units=1,
            )
            with self.assertRaises(rate_limits.LimitExceeded) as ctx:
                rate_limits.reserve_job(
                    self.consumer,
                    job_id="quota-job-2",
                    idempotency_key="quota-key-00000002",
                    audio_seconds=3,
                    cost_units=1,
                )
            self.assertEqual(ctx.exception.code, "DAILY_JOB_QUOTA_EXCEEDED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
