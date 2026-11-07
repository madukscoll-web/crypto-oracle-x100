"""Regression tests for fail-closed Telegram heading normalization."""
import unittest
from classification_policy import classify_existing_message, format_message, HEADINGS


class ClassificationPolicyTests(unittest.TestCase):
    def test_health_digest(self):
        msg = "CRYPTO-ORACLE X100 daily pipeline health, latest scan at UTC"
        self.assertTrue(format_message(msg).startswith("SYSTEM HEALTH REPORT\n"))

    def test_technical_hypothesis_is_not_confirmed_reversal(self):
        msg = "CRYPTO-ORACLE | TECHNICAL WATCH — NOT APPROVED FOR PURCHASE\nSetup: EARLY REVERSAL WATCH"
        out = format_message(msg)
        self.assertTrue(out.startswith("RESEARCH WATCH\n"))
        self.assertNotIn("BULLISH REVERSAL\n", out)

    def test_unverified_pool_not_new_coin(self):
        msg = "CRYPTO-ORACLE Z — UNVERIFIED RESEARCH LEAD\nPool age: 1h"
        self.assertEqual(classify_existing_message(msg), "RESEARCH WATCH")
        self.assertFalse(format_message(msg).startswith("NEW COIN"))

    def test_no_atl_without_verified_evidence(self):
        msg = "Pool price down 99%; historical low UNKNOWN"
        self.assertEqual(classify_existing_message(msg), "RESEARCH WATCH")

    def test_buy_label_preserved_from_existing_admission_path(self):
        msg = "CRYPTO-ORACLE X100 — BUY CANDIDATE — MANUAL REVIEW\nAuthenticated review"
        self.assertTrue(format_message(msg).startswith("BUY CANDIDATE — MANUAL REVIEW\n"))

    def test_existing_heading_not_duplicated(self):
        msg = "RESEARCH WATCH\nExisting report"
        self.assertEqual(format_message(msg), msg)

    def test_all_headings_defined(self):
        self.assertEqual(len(HEADINGS), 7)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            format_message("")


if __name__ == "__main__":
    unittest.main()
