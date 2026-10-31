import tempfile
import unittest
from pathlib import Path
from notification_preflight import inspect


class NotificationPreflightTests(unittest.TestCase):
    def test_missing_credentials_never_exposes_values(self):
        result = inspect({}, "/nonexistent/scan_summary.json")
        self.assertFalse(result["credentials_configured"])
        self.assertFalse(result["delivery_verified"])
        self.assertIn("TELEGRAM_BOT_TOKEN missing", result["issues"])

    def test_completed_summary_does_not_imply_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "scan_summary.json"
            path.write_text('{"status":"completed","alerts_delivered":0}')
            result = inspect({"TELEGRAM_BOT_TOKEN":"secret", "TELEGRAM_CHAT_ID":"123"}, path)
            self.assertTrue(result["credentials_configured"])
            self.assertFalse(result["delivery_verified"])
            self.assertEqual(result["alerts_delivered"], 0)
            self.assertNotIn("secret", str(result))


if __name__ == "__main__":
    unittest.main()
