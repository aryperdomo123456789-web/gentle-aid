import hashlib
import hmac
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
STORAGE = Path(tempfile.mkdtemp(prefix="gentle-aid-saas-test-"))
os.environ["VIRAL_ROOT"] = str(REPO)
os.environ["VIRAL_STORAGE"] = str(STORAGE)
os.environ["SECRET_KEY"] = "saas-test-secret-" + ("x" * 40)
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret_" + ("x" * 32)
sys.path.insert(0, str(REPO / "backend"))

from app import create_app
from app.config import Config
from app.services import billing, billing_webhooks, idempotency, persistent_queue, rate_limits, release_keys, webhook_delivery


class _FakeHTTPResponse:
    status = 204
    def read(self, limit=-1):
        return b""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class SaasCommercialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(Config.from_env())
        cls.app.config.update(TESTING=True)
        with cls.app.app_context():
            release_keys.migrate()
            idempotency.migrate()
            persistent_queue.migrate()
            rate_limits.migrate()
            billing.migrate()
            webhook_delivery.migrate()

    def test_plan_quota_and_account_mapping(self):
        with self.app.app_context():
            billing.ensure_account("account-1")
            self.assertEqual(billing.plan_for("account-1")["code"], "starter")
            billing.set_subscription("account-1", plan_code="pro", status="active")
            self.assertEqual(billing.limits_for("account-1")["max_concurrent_jobs"], 8)
            billing.reserve_transcription("account-1", seconds=120, storage_bytes=100, resource_id="job-1", idempotency_key="billing-idempotency-0001")
            billing.reserve_transcription("account-1", seconds=120, storage_bytes=100, resource_id="job-1", idempotency_key="billing-idempotency-0001")
            snapshot = billing.usage_snapshot("account-1")
            self.assertEqual(snapshot["used"]["audio_minutes"], 2.0)
            self.assertEqual(snapshot["used"]["storage_bytes"], 100)

    def test_release_key_resolves_tenant(self):
        actor = {"id": "tenant-2", "email": "tenant@example.test", "role": "owner"}
        raw = release_keys.create_key(actor, label="tenant key", expires_in_days=1, scopes=["usage:read"])["raw_key"]
        info = release_keys.validate_key(raw)
        self.assertEqual(info["account_id"], "tenant-2")
        with self.app.app_context():
            self.assertEqual(billing.account_id_for_consumer(info["id"]), "tenant-2")

    def test_stripe_signature_and_event_replay(self):
        payload = json.dumps({"id":"evt_test_1","type":"checkout.session.completed","data":{"object":{"metadata":{"account_id":"acct-stripe","plan_code":"pro"},"customer":"cus_1","subscription":"sub_1"}}}, separators=(",", ":")).encode()
        timestamp = int(time.time())
        digest = hmac.new(os.environ["STRIPE_WEBHOOK_SECRET"].encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        signature = f"t={timestamp},v1={digest}"
        first = billing_webhooks.process_stripe(payload, signature_header=signature)
        second = billing_webhooks.process_stripe(payload, signature_header=signature)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        with self.app.app_context():
            self.assertEqual(billing.plan_for("acct-stripe")["code"], "pro")

    def test_downstream_hmac_and_three_attempt_retry(self):
        job = {"job_id":"job-webhook-1","tool":"api-transcription","status":"done","created_at":"2026-01-01T00:00:00+00:00","finished_at":"2026-01-01T00:00:01+00:00","estimated_audio_seconds":2,"meta":{"webhook_url":"https://consumer.example.test/events","webhook_secret":"consumer-secret-" + ("x" * 32)}}
        requests = []
        class RequestCapture:
            def __init__(self, url, data=None, method=None, headers=None):
                requests.append((url, data, method, headers))
        def fake_urlopen(request, timeout):
            self.assertEqual(timeout, 5.0)
            return _FakeHTTPResponse()
        fake_opener = mock.Mock()
        fake_opener.open.side_effect = fake_urlopen
        with mock.patch.object(webhook_delivery, "_safe_delivery_url", return_value=True), mock.patch.object(webhook_delivery.urllib.request, "Request", RequestCapture), mock.patch.object(webhook_delivery.urllib.request, "build_opener", return_value=fake_opener):
            result = webhook_delivery.notify_job(job)
        self.assertEqual(result["status"], "delivered")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(requests[0][3]["X-Viral-Event"], "job.completed")
        self.assertTrue(requests[0][3]["X-Viral-Signature"].startswith("t="))

        failures = {"count": 0}
        def flaky_urlopen(request, timeout):
            failures["count"] += 1
            if failures["count"] < 3:
                raise OSError("synthetic failure")
            return _FakeHTTPResponse()
        job["job_id"] = "job-webhook-2"
        fake_opener.open.side_effect = flaky_urlopen
        with mock.patch.object(webhook_delivery, "_safe_delivery_url", return_value=True), mock.patch.object(webhook_delivery.time, "sleep"), mock.patch.object(webhook_delivery.urllib.request, "build_opener", return_value=fake_opener):
            retried = webhook_delivery.notify_job(job)
        self.assertEqual(retried["status"], "delivered")
        self.assertEqual(retried["attempts"], 3)

    def test_billing_usage_route_is_protected(self):
        with self.app.test_client() as client:
            self.assertEqual(client.get("/api/v1/billing/usage").status_code, 401)


if __name__ == "__main__":
    unittest.main()
