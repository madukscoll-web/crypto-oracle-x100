"""Regression: research WATCH counts must not be confused with verified BUY alerts."""
import pathlib
import unittest


class ResearchDeliveryAccountingTests(unittest.TestCase):
    def test_distinct_delivery_counters_are_persisted(self):
        source = pathlib.Path(__file__).resolve().parents[1].joinpath("crypto_oracle_scanner.py").read_text()
        self.assertIn('"alerts_delivered": delivered, "research_watch_delivered": research_sent', source)
        self.assertIn('print(f"Research WATCH messages delivered: {research_sent}"', source)
        self.assertIn('research_sent += 1', source)
        self.assertIn('delivered += 1', source)


if __name__ == "__main__":
    unittest.main()
