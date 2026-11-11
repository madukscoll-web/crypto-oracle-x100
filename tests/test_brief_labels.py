import os
import unittest
from unittest.mock import patch

import classification_policy as cp
import crypto_oracle_scanner as scanner
import telegram_notify as telegram


class ReversalLabelTests(unittest.TestCase):
    def test_new_reversal_headings_are_known_but_untrusted_in_raw_text(self):
        for heading in ("EARLY BULLISH REVERSAL WATCH", "CONFIRMED BULLISH REVERSAL"):
            self.assertIn(heading, cp.HEADINGS)
            self.assertEqual(cp.classify_existing_message(heading + "\nbody"), "RESEARCH WATCH")
            self.assertTrue(cp.format_message(heading + "\nbody").startswith("RESEARCH WATCH\n"))


class SystemFailureLabelTests(unittest.TestCase):
    def env(self, stages):
        return patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "1", "FAILED_STAGES": stages})

    def test_failed_core_scan_is_critical(self):
        with self.env("scan=failure"):
            text = telegram.workflow_message("failure")
        self.assertEqual(cp.format_message(text).splitlines()[0], "CRITICAL SYSTEM FAILURE")

    def test_unknown_core_outcome_is_critical(self):
        with self.env("state=failure"):
            text = telegram.workflow_message("failure")
        self.assertEqual(cp.format_message(text).splitlines()[0], "CRITICAL SYSTEM FAILURE")

    def test_followup_failure_with_core_success_is_not_critical(self):
        with self.env("scan=success, technical_followup=failure"):
            text = telegram.workflow_message("failure")
        self.assertEqual(cp.format_message(text).splitlines()[0], "SYSTEM HEALTH REPORT")

    def test_critical_label_cannot_front_market_content(self):
        # Preserved only as an operational heading; it grants no BUY authority.
        self.assertNotIn("BUY", cp.format_message("CRITICAL SYSTEM FAILURE\nx").splitlines()[0])


class DiscoveryTypeTests(unittest.TestCase):
    def test_new_pool_does_not_claim_new_token(self):
        text = scanner.pool_class_text({"pool_class": "NEW POOL", "age_hours": 5.25})
        self.assertIn("NEW POOL", text)
        self.assertIn("5.2h", text.replace("5.3h", "5.2h"))
        self.assertIn("token itself may be older", text)

    def test_existing_pool_is_not_a_new_listing(self):
        text = scanner.pool_class_text({"pool_class": "EXISTING POOL", "age_hours": 900})
        self.assertIn("not a new listing", text)

    def test_missing_age_is_reported_unknown(self):
        self.assertIn("unknown age", scanner.pool_class_text({"pool_class": "EXISTING POOL"}))
        self.assertIn("unknown age", scanner.pool_class_text({"pool_class": "NEW POOL", "age_hours": True}))


if __name__ == "__main__":
    unittest.main()
