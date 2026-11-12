import os
import unittest
from unittest.mock import patch

import classification_policy as cp
import crypto_oracle_scanner as scanner
import telegram_notify as telegram
from research_notice import _issue, verified_text

ITEM = {"network": "base", "token_address": "0x" + "a" * 40, "address": "0x" + "b" * 40, "token_symbol": "ABC",
        "liquidity": 250000, "volume": 500000, "trades": 120, "score": 80, "source": "GeckoTerminal",
        "url": "https://example.test/p", "observed_at": "2026-11-12T00:00:00+00:00",
        "pool_class": "NEW POOL", "age_hours": 3.0, "risk_reasons": ["LP controls unverified"]}


def section_order(text, headers):
    positions = [text.index(h) for h in headers]
    return positions == sorted(positions)


class DiscoveryLayoutTests(unittest.TestCase):
    def text(self):
        with patch.object(scanner, "decision_summary", return_value=("WAIT / VERIFY", "gaps")), \
             patch.object(scanner, "setup_assessment", return_value=("WATCH", "reason")):
            return scanner.research_alert_text(ITEM)

    def test_headings_in_reading_order(self):
        text = self.text()
        self.assertEqual(text.splitlines()[0], "NEW TOKEN DISCOVERY")
        self.assertTrue(section_order(text, ["📌 VERDICT", "🪙 TOKEN", "📊 MARKET DATA", "🏢 PROJECT CONTEXT",
                                             "⚠️ UNRESOLVED EVIDENCE", "🔗 SOURCE"]))

    def test_disclosures_survive_restyle(self):
        text = self.text()
        for fragment in ("NOT A BUY SIGNAL", "LP controls unverified", "must be verified before any purchase",
                         "Token launch origin/age: not established", "NEW POOL", "Contract: 0x" + "a" * 40):
            self.assertIn(fragment, text)

    def test_still_a_valid_signed_research_notice_within_limit(self):
        notice = _issue("NEW TOKEN DISCOVERY", self.text())
        shown = verified_text(notice)
        self.assertEqual(shown.splitlines()[0], "NEW TOKEN DISCOVERY")
        self.assertLessEqual(len(shown.encode("utf-16-le")) // 2, 4096)


class OperationalLayoutTests(unittest.TestCase):
    def test_failure_notice_sections(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "1", "FAILED_STAGES": "scan=failure"}):
            text = telegram.workflow_message("failure")
        self.assertEqual(cp.format_message(text).splitlines()[0], "CRITICAL SYSTEM FAILURE")
        self.assertTrue(section_order(text, ["🩺 STATUS", "⚠️ WHAT THIS MEANS", "🔗 LINKS"]))
        self.assertIn("/o/r/actions/runs/1", text)

    def test_health_report_sections_and_profitability_disclaimer(self):
        text = telegram.health_summary({"candidates": 3}, {}, {}, {}, {}, {}, "https://x.test/run")
        self.assertEqual(text.splitlines()[0], "SYSTEM HEALTH REPORT")
        self.assertTrue(section_order(text, ["🩺 STATUS", "🔎 DISCOVERY", "🔔 ALERTS", "📈 PERFORMANCE",
                                             "🧾 SUMMARY", "🔗 LINKS"]))
        self.assertIn("Profitability: NOT ESTABLISHED", text)


if __name__ == "__main__":
    unittest.main()
