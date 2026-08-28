import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORAGE = Path(tempfile.mkdtemp(prefix="gentle-aid-retention-test-"))
os.environ["VIRAL_ROOT"] = str(REPO)
os.environ["VIRAL_STORAGE"] = str(STORAGE)
os.environ["SECRET_KEY"] = "retention-test-secret-" + ("x" * 40)
sys.path.insert(0, str(REPO / "backend"))

from app.config import Config
from app import create_app
from app.services import billing, jobs, retention


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(Config.from_env())
        cls.app.config.update(TESTING=True)
        with cls.app.app_context():
            billing.migrate()

    def test_expiration_removes_artifacts_releases_storage_and_keeps_job(self):
        with self.app.app_context():
            account = "retention-account"
            billing.ensure_account(account)
            artifact = STORAGE / "retention-output.mp4"
            artifact.write_bytes(b"x" * 128)
            job = jobs.create_job("api-clip", meta={"account_id": account, "consumer_id": account})
            billing.reserve_storage(account, resource_id=job["job_id"], storage_bytes=128)
            jobs.update(job["job_id"], status="done", finished_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds"), expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds"), artifacts=[{"path": str(artifact), "kind": "api-output"}], source_path=str(artifact))
            result = retention.collect(limit=20)
            self.assertEqual(result["expired"], 1)
            self.assertEqual(result["files_removed"], 1)
            self.assertFalse(artifact.exists())
            saved = jobs.get(job["job_id"])
            self.assertEqual(saved["retention_status"], "expired")
            self.assertEqual(billing.usage_snapshot(account)["used"]["storage_bytes"], 0)
            jobs.delete(job["job_id"])


if __name__ == "__main__":
    unittest.main()
