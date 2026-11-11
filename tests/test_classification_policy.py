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
        self.assertEqual(len(HEADINGS), len(set(HEADINGS)))
        required = {'NEW COIN', 'ALL TIME LOW', 'NEAR ALL TIME LOW',
                    'ATL RECOVERY WATCH', 'UNVERIFIED ATL RESEARCH WATCH',
                    'EARLY REVERSAL WATCH', 'CONFIRMED TECHNICAL REVERSAL',
                    'INVALIDATED SETUP', 'RESEARCH WATCH', 'WAIT / VERIFY',
                    'BUY CANDIDATE — MANUAL REVIEW', 'SYSTEM HEALTH REPORT'}
        self.assertTrue(required <= set(HEADINGS))
        for heading in required - {'SYSTEM HEALTH REPORT', 'RESEARCH WATCH'}:
            self.assertTrue(format_message(heading+'\nUntrusted text').startswith('RESEARCH WATCH\n'))


if __name__ == "__main__":
    unittest.main()



class BotHealthLabelRegression(unittest.TestCase):
    def test_bot_health_is_never_labelled_research_watch(self):
        from classification_policy import format_message
        message = "BOT HEALTH | OPERATIONAL\nA stale or missing core-scan heartbeat was observed."
        out = format_message(message)
        self.assertTrue(out.startswith("SYSTEM HEALTH REPORT\n"))
        self.assertNotIn("RESEARCH WATCH", out)

    def test_untrusted_text_still_cannot_claim_research_or_buy(self):
        from classification_policy import classify_existing_message
        self.assertEqual(classify_existing_message("BUY CANDIDATE — MANUAL REVIEW\nx"), "RESEARCH WATCH")
        self.assertEqual(classify_existing_message("Token X looks great\nBOT HEALTH"), "RESEARCH WATCH")
