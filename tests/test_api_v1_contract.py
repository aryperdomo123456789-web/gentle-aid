from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORAGE = Path(tempfile.mkdtemp(prefix="gentle-aid-api-test-"))
os.environ["VIRAL_ROOT"] = str(REPO)
os.environ["VIRAL_STORAGE"] = str(STORAGE)
os.environ["SECRET_KEY"] = "local-test-secret-" + ("x" * 40)
os.environ["OWNER_EMAIL"] = "owner@example.test"
os.environ["OWNER_PASSWORD"] = "local-owner-password-123"
sys.path.insert(0, str(REPO / "backend"))

from app import create_app
from app.config import Config
from app.services import idempotency, jobs, persistent_queue, rate_limits, release_keys
import worker as api_worker


class ApiV1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app(Config.from_env())
        cls.app.config.update(TESTING=True)
        idempotency.migrate()
        persistent_queue.migrate()
        rate_limits.migrate()
        cls.client = cls.app.test_client()
        owner = {"id": "u_owner_test", "email": "owner@example.test", "role": "owner"}
        cls.full_key = release_keys.create_key(
            owner,
            label="local integration",
            expires_in_days=1,
            scopes=[
                "catalog:read",
                "transcribe:write",
                "jobs:read",
                "jobs:write",
                "results:read",
                "usage:read",
            ],
        )["raw_key"]
        cls.limited_key = release_keys.create_key(
            owner,
            label="limited integration",
            expires_in_days=1,
            scopes=["jobs:read"],
        )["raw_key"]

    def api_headers(self, **extra: str) -> dict[str, str]:
        headers = {"X-API-Key": self.full_key}
        headers.update(extra)
        return headers

    def post_transcription(self, headers: dict[str, str], *, filename: str = "sample.mp3"):
        return self.client.post(
            "/api/v1/transcriptions",
            headers=headers,
            data={
                "file": (io.BytesIO(b"local-test-media"), filename),
                "language": "pt",
                "output_format": "text",
            },
            content_type="multipart/form-data",
        )

    def test_public_health_and_openapi_are_published(self) -> None:
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json["api_version"], "v1")
        self.assertEqual(self.client.get("/api/docs").status_code, 200)
        spec = self.client.get("/api/openapi.json")
        self.assertEqual(spec.status_code, 200)
        self.assertEqual(spec.json["openapi"], "3.1.0")
        self.assertIn("/transcriptions", spec.json["paths"])

    def test_internal_routes_and_downloads_are_not_public(self) -> None:
        self.assertEqual(self.client.get("/api/jobs").status_code, 401)
        self.assertEqual(self.client.get("/api/apis").status_code, 401)
        self.assertEqual(self.client.get("/downloads/_config/auth.sqlite3").status_code, 404)

    def test_api_key_and_scope_are_enforced(self) -> None:
        self.assertEqual(
            self.client.get(
                "/api/v1/capabilities",
                headers=self.api_headers(),
            ).status_code,
            200,
        )
        limited = self.client.get(
            "/api/v1/capabilities",
            headers={"Authorization": f"Bearer {self.limited_key}"},
        )
        self.assertEqual(limited.status_code, 403)
        self.assertEqual(limited.json["code"], "MISSING_SCOPE")

    def test_idempotency_is_required_and_replays_same_job(self) -> None:
        missing = self.post_transcription(self.api_headers())
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json["code"], "IDEMPOTENCY_KEY_REQUIRED")

        headers = self.api_headers(**{"Idempotency-Key": "local-idempotency-12345"})
        first = self.post_transcription(headers)
        self.assertEqual(first.status_code, 202)
        job_id = first.json["id"]
        self.assertEqual(first.json["object"], "operation")
        self.assertTrue(first.json["name"].startswith("operations/"))
        self.assertFalse(first.json["done"])
        self.assertEqual(first.json["status"], "PENDING")
        self.assertIn("metadata", first.json)
        self.assertIsNone(first.json["response"])
        self.assertIsNone(first.json["error"])

        polling = self.client.get(
            f"/api/v1/operations/{job_id}",
            headers=self.api_headers(),
        )
        self.assertEqual(polling.status_code, 200)
        self.assertEqual(polling.json["name"], first.json["name"])
        self.assertIn("done", polling.json)

        replay = self.post_transcription(headers)
        self.assertEqual(replay.status_code, 202)
        self.assertEqual(replay.json["id"], job_id)
        self.assertEqual(replay.headers.get("X-Idempotent-Replay"), "true")

    def test_correlation_headers_do_not_change_idempotency(self) -> None:
        key = "local-correlation-12345"
        first = self.post_transcription(
            self.api_headers(
                **{
                    "Idempotency-Key": key,
                    "X-Client-Request-Id": "checkout-attempt-a",
                    "X-Request-Id": "client-supplied-a",
                }
            )
        )
        self.assertEqual(first.status_code, 202)
        second = self.post_transcription(
            self.api_headers(
                **{
                    "Idempotency-Key": key,
                    "X-Client-Request-Id": "checkout-attempt-b",
                    "X-Request-Id": "client-supplied-b",
                }
            )
        )
        self.assertEqual(second.status_code, 202)
        self.assertEqual(second.json["id"], first.json["id"])
        self.assertEqual(second.headers.get("X-Idempotent-Replay"), "true")
        self.assertTrue(first.headers.get("X-Request-Id"))
        self.assertTrue(second.headers.get("X-Request-Id"))
        self.assertNotEqual(first.headers.get("X-Request-Id"), second.headers.get("X-Request-Id"))

    def test_same_idempotency_key_with_different_payload_conflicts(self) -> None:
        headers = self.api_headers(**{"Idempotency-Key": "local-conflict-12345"})
        first = self.post_transcription(headers, filename="first.mp3")
        self.assertEqual(first.status_code, 202)
        conflict = self.post_transcription(headers, filename="different-name.mp3")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json["code"], "IDEMPOTENCY_CONFLICT")

    def test_job_ownership_isolated_between_api_keys(self) -> None:
        created = self.post_transcription(
            self.api_headers(**{"Idempotency-Key": "local-owner-12345"})
        )
        self.assertEqual(created.status_code, 202)
        job_id = created.json["id"]
        other = release_keys.create_key(
            {"id": "u_other_test", "email": "other@example.test", "role": "owner"},
            label="other integration",
            expires_in_days=1,
            scopes=["jobs:read"],
        )["raw_key"]
        response = self.client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"X-API-Key": other},
        )
        self.assertEqual(response.status_code, 404)

    def test_failed_operation_uses_stable_error_catalog(self) -> None:
        headers = self.api_headers(**{"Idempotency-Key": "local-failure-12345"})
        original_transcribe = __import__("app.services.transcribe", fromlist=["transcribe"]).transcribe
        module = __import__("app.services.transcribe", fromlist=["transcribe"])
        module.transcribe = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider detail must not leak"))
        try:
            created = self.post_transcription(headers)
            self.assertEqual(created.status_code, 202)
            item = persistent_queue.claim("test-worker-failure", lease_seconds=60, job_id=created.json["id"])
            self.assertIsNotNone(item)
            api_worker._process(item)
            operation = self.client.get(
                f"/api/v1/operations/{created.json['id']}",
                headers=self.api_headers(),
            )
            self.assertEqual(operation.status_code, 200)
            self.assertTrue(operation.json["done"])
            self.assertEqual(operation.json["status"], "FAILED")
            self.assertEqual(operation.json["error"]["code"], "WORKER_ERROR")
            self.assertEqual(operation.json["error"]["retryable"], False)
            self.assertIn("type", operation.json["error"])
            self.assertNotIn("provider detail", operation.get_data(as_text=True))
        finally:
            module.transcribe = original_transcribe

    def test_cancel_operation_is_terminal_and_idempotent(self) -> None:
        headers = self.api_headers(**{"Idempotency-Key": "local-cancel-12345"})
        original_enqueue = persistent_queue.enqueue
        persistent_queue.enqueue = lambda _job_id, _kind, _payload: True
        try:
            created = self.post_transcription(headers)
            self.assertEqual(created.status_code, 202)
            job_id = created.json["id"]
            cancelled = self.client.post(
                f"/api/v1/operations/{job_id}:cancel",
                headers=self.api_headers(**{"Idempotency-Key": "local-cancel-request-12345"}),
            )
            self.assertEqual(cancelled.status_code, 202)
            self.assertTrue(cancelled.json["done"])
            self.assertEqual(cancelled.json["status"], "CANCELLED")
            self.assertEqual(cancelled.json["error"]["code"], "CANCELLED")
            self.assertEqual(cancelled.json["name"], f"operations/{job_id}")
        finally:
            persistent_queue.enqueue = original_enqueue

    def test_expired_operation_is_terminal_without_result(self) -> None:
        key_info = release_keys.validate_key(self.full_key)
        self.assertIsNotNone(key_info)
        owner_id = key_info["id"]
        job = jobs.create_job(
            "api-transcription",
            meta={"api_key_id": owner_id, "consumer_id": owner_id},
        )
        jobs.update(
            job["job_id"],
            status="done",
            finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds"),
            progress=100,
        )
        operation = self.client.get(
            f"/api/v1/operations/{job['job_id']}",
            headers=self.api_headers(),
        )
        self.assertEqual(operation.status_code, 200)
        self.assertTrue(operation.json["done"])
        self.assertEqual(operation.json["status"], "EXPIRED")
        self.assertEqual(operation.json["error"]["code"], "RESULT_EXPIRED")
        self.assertIsNone(operation.json["response"])

    def test_invalid_output_format_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/transcriptions",
            headers=self.api_headers(**{"Idempotency-Key": "local-format-12345"}),
            data={
                "file": (io.BytesIO(b"local-test-media"), "sample.mp3"),
                "output_format": "exe",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
