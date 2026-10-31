"""Regression checks for workflow notification policy."""
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkflowNotificationPolicyTests(unittest.TestCase):
    def test_no_routine_success_telegram_step(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertNotIn("python telegram_notify.py success", workflow)
        self.assertNotIn("Notify Telegram on successful scan completion", workflow)

    def test_failure_alert_preserved(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertIn("python telegram_notify.py failure", workflow)
        self.assertIn("if: failure()", workflow)

    def test_hourly_scan_and_diagnostics_preserved(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '7 * * * *'", workflow)
        self.assertIn("python -u crypto_oracle_scanner.py", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)


if __name__ == "__main__":
    unittest.main()
