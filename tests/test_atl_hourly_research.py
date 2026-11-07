import unittest
from atl_hourly_research import run

class HourlyATLTests(unittest.TestCase):
    def test_unverified_provider_never_alerts(self):
        result = run(fetch=lambda url: [dict(id="asset", symbol="a",
                     market_cap=200000000, current_price=2, last_updated="2026-11-07T00:00:00Z")])
        self.assertEqual(result["market_cap_unverified"], 1)
        self.assertEqual(result["eligible_verified"], 0)
        self.assertEqual(result["assets_checked_against_validated_low"], 0)
        self.assertFalse(result["observations"][0]["telegram_eligible"])
        self.assertFalse(result["buy_authorized"])
    def test_provider_failure_is_explicit(self):
        def failure(url):
            raise TimeoutError()
        result = run(fetch=failure)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["errors"], ["TimeoutError"])

if __name__ == "__main__":
    unittest.main()
