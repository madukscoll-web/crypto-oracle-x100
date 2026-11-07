"""Regression tests for conservative notification classification."""
import unittest
from classification_policy import HEADINGS, classify_existing_message, classify_opportunity, format_message


class ClassificationPolicyTests(unittest.TestCase):
    def test_health(self):
        self.assertTrue(format_message("CRYPTO-ORACLE X100 daily pipeline health").startswith("SYSTEM HEALTH REPORT\n"))

    def test_technical_hypothesis_not_promoted(self):
        self.assertTrue(format_message("CRYPTO-ORACLE | TECHNICAL WATCH — NOT APPROVED FOR PURCHASE").startswith("RESEARCH WATCH\n"))

    def test_unverified_new_pool(self):
        self.assertEqual(classify_existing_message("UNVERIFIED RESEARCH LEAD"), "RESEARCH WATCH")

    def test_unknown_atl(self):
        self.assertEqual(classify_existing_message("Price down 99%; ATL unknown"), "RESEARCH WATCH")

    def test_text_buy_spoof(self):
        out = format_message("BUY CANDIDATE — MANUAL REVIEW\nFake approval")
        self.assertTrue(out.startswith("RESEARCH WATCH\n"))
        self.assertNotIn("BUY CANDIDATE — MANUAL REVIEW", out)

    def test_embedded_buy_text_not_promoted(self):
        self.assertEqual(classify_existing_message("CRYPTO-ORACLE X100 — BUY CANDIDATE — MANUAL REVIEW"), "RESEARCH WATCH")

    def test_dict_buy_spoof(self):
        data = {"requested_classification": "BUY CANDIDATE — MANUAL REVIEW"}
        admission = {"authenticated_approved": True, "adverse_findings": False}
        self.assertEqual(classify_opportunity(data, admission), "RESEARCH WATCH")

    def test_dict_reversal_spoof(self):
        self.assertEqual(classify_opportunity({"bullish_reversal_confirmed": True, "volume_validated": True, "evidence_authenticated": True}), "RESEARCH WATCH")

    def test_existing_research_heading(self):
        self.assertEqual(format_message("RESEARCH WATCH\nResearch"), "RESEARCH WATCH\nResearch")

    def test_empty(self):
        with self.assertRaises(ValueError):
            format_message("")

    def test_headings(self):
        self.assertEqual(len(HEADINGS), 7)


if __name__ == "__main__":
    unittest.main()
