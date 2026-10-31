import unittest
from multichain_live_research import run

class Adapter:
    network = "solana"
    def __init__(self, fetch): pass
    def discover(self):
        return {"rows": [{"network": "solana",
            "token_address": "So11111111111111111111111111111111111111112",
            "address": "11111111111111111111111111111111"}],
            "failures": [], "observations": []}

class RunnerTests(unittest.TestCase):
    def test_read_only_and_dedup(self):
        result = run(1, 0, fetch=lambda url: {}, adapters=(Adapter, Adapter))
        self.assertEqual(result["unique_tokens"], 1)
        self.assertEqual(len(result["selected"]), 1)
        self.assertFalse(result["buy_authorized"])
        self.assertFalse(result["telegram_transmission"])
    def test_stonk_leads_are_read_only_and_provider_attested(self):
        payload = {"degraded": False, "pools": [{"mint": "So11111111111111111111111111111111111111112"}]}
        result = run(5, fetch=lambda url: {}, adapters=(Adapter,), include_stonk=True,
                     stonk_fetch=lambda url: payload)
        self.assertEqual(result["unique_tokens"], 1)
        self.assertEqual(result["selected"][0]["network"], "solana")
        self.assertIn("PROVIDER_ATTESTED", result["selected"][0]["launchpad"])
        self.assertFalse(result["buy_authorized"])
        self.assertFalse(result["telegram_transmission"])

    def test_stonk_outage_is_reported_not_suppressed(self):
        def fail(url):
            raise OSError("provider unavailable")
        result = run(5, fetch=lambda url: {}, adapters=(Adapter,), include_stonk=True,
                     stonk_fetch=fail)
        self.assertEqual(result["unique_tokens"], 1)
        self.assertEqual(result["launchpad_direct_feeds_active"], [])
        self.assertEqual(result["failures"][0]["source"], "StonkFun")
        self.assertFalse(result["buy_authorized"])

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            run(0, fetch=lambda url: {}, adapters=())

if __name__ == "__main__":
    unittest.main()
