"""Regression checks for workflow notification policy."""
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkflowNotificationPolicyTests(unittest.TestCase):
    def test_one_aggregate_success_telegram_step(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("python telegram_notify.py success"), 1)
        self.assertNotIn("Notify Telegram on successful scan completion", workflow)

    def test_failure_alert_preserved(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertIn("python telegram_notify.py failure", workflow)
        self.assertIn("if: failure()", workflow)

    def test_hourly_scan_and_diagnostics_preserved(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '7,27,47 * * * *'", workflow)
        self.assertIn("python -u crypto_oracle_scanner.py", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)


if __name__ == "__main__":
    unittest.main()


class FailureDetailTests(unittest.TestCase):
    def test_failure_names_actual_followup_and_preserves_core_success(self):
        import os
        from unittest.mock import patch
        from telegram_notify import workflow_message
        with patch.dict(os.environ, {'FAILED_STAGES':'scan=success, state=success, research_health=failure, technical_followup=failure'}):
            text=workflow_message('failure')
        self.assertIn('Core scan outcome: success',text)
        self.assertIn('technical_followup=failure',text)
        self.assertNotIn('scan=success',text)
        self.assertNotIn('No successful scan should be assumed',text)
