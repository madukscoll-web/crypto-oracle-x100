"""The operational summary must not conflate research watches with BUY signals."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import telegram_notify


class OperationalWatchMetricsTests(unittest.TestCase):
    def test_watch_and_buy_counts_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            report = {
                "status": "completed", "completed_at": "2026-11-03T00:00:00Z",
                "observations": 100, "candidates": 20, "alerts_delivered": 1,
                "buy_candidates_delivered": 0, "signed_entry_watches_delivered": 1,
                "research_watch_delivered": 2, "warnings": [],
                "filter_audit": {"assessed_candidates": 6},
            }
            pathlib.Path(directory, "scan_summary.json").write_text(json.dumps(report))
            with patch.object(telegram_notify.pathlib.Path, "cwd", return_value=pathlib.Path(directory)):
                old = os.getcwd()
                try:
                    os.chdir(directory)
                    message = telegram_notify.workflow_message("success")
                finally:
                    os.chdir(old)
            self.assertIn("BUY candidates for manual review: 0", message)
            self.assertIn("safety-reviewed entry WATCH alerts: 1", message)
            self.assertIn("research WATCH alerts: 2", message)
            self.assertIn("Assessed: 6", message)


if __name__ == "__main__":
    unittest.main()

