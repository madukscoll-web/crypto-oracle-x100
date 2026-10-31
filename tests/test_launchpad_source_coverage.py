import unittest
from multichain_live_research import run


class FakeAdapter:
    network = "solana"
    def __init__(self, fetch):
        self.fetch = fetch
    def discover(self):
        row = {"network": "solana", "token_address": "11111111111111111111111111111111",
               "source": "GeckoTerminal public pool feed", "address": "11111111111111111111111111111111"}
        return {"rows": [row], "failures": []}


class SourceCoverageTests(unittest.TestCase):
    def test_gecko_pool_is_not_claimed_as_pumpfun_origin(self):
        report = run(limit=1, fetch=lambda url: None, adapters=(FakeAdapter,))
        self.assertEqual(report["selected"][0]["launchpad"], "UNKNOWN — no authenticated launchpad-origin evidence")
        self.assertEqual(report["launchpad_direct_feeds_active"], [])
        self.assertEqual(report["coverage_audit"]["launchpad_origin_verified_count"], 0)
        self.assertEqual(report["discovery_sources"]["GeckoTerminal public pool feed"], 1)
        self.assertFalse(report["buy_authorized"])
        self.assertFalse(report["telegram_transmission"])


if __name__ == "__main__":
    unittest.main()
