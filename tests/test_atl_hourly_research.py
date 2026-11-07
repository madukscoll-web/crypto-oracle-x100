import unittest
from atl_hourly_research import run
from datetime import datetime, timezone

class HourlyATLTests(unittest.TestCase):
    def test_unverified_provider_never_alerts(self):
        result = run(now=datetime(2026, 11, 7, 1, tzinfo=timezone.utc), fetch=lambda url: [dict(id="asset", symbol="a",
                     market_cap=200000000, circulating_supply=100000000, current_price=2, last_updated="2026-11-07T00:00:00Z")])
        self.assertEqual(result["market_cap_unverified"], 0)
        self.assertEqual(result["eligible_verified"], 1)
        self.assertEqual(result["assets_checked_against_validated_low"], 0)
        self.assertFalse(result["observations"][0]["telegram_eligible"])
        self.assertFalse(result["buy_authorized"])
    def test_published_atl_is_discovery_not_verified_signal(self):
        result = run(fetch=lambda url: [dict(id="example", symbol="ex",
            market_cap=200000000, circulating_supply=100000000, current_price=1.02, atl=1,
            atl_date="2025-01-01T00:00:00Z",
            last_updated="2026-11-07T00:00:00Z")])
        self.assertEqual(result["provider_atl_candidates"], 1)
        candidate = result["observations"][0]["provider_atl_candidate"]
        self.assertEqual(candidate["source"], "CoinGecko")
        self.assertFalse(candidate["independently_verified"])
        self.assertFalse(candidate["telegram_eligible"])
    def test_provider_failure_is_explicit(self):
        def failure(url):
            raise TimeoutError()
        result = run(fetch=failure)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["errors"], ["TimeoutError"])

if __name__ == "__main__":
    unittest.main()
