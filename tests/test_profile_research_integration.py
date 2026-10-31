import unittest
from multichain_live_research import run


class EmptyAdapter:
    network = "solana"
    def __init__(self, fetch): self.fetch = fetch
    def discover(self): return {"rows": [], "failures": []}


class ProfileIntegrationTests(unittest.TestCase):
    def test_profiles_are_optional(self):
        report = run(limit=1, fetch=lambda url: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
                     adapters=(EmptyAdapter,))
        self.assertEqual(report["observed_pools"], 0)
        self.assertEqual(report["launchpad_direct_feeds_active"], [])

    def test_profile_provider_failure_is_reported_not_fatal(self):
        def failing_fetch(url):
            raise OSError("provider unavailable")
        report = run(limit=1, fetch=failing_fetch, adapters=(EmptyAdapter,), include_profiles=True)
        self.assertGreaterEqual(len(report["failures"]), 1)
        self.assertEqual(report["launchpad_direct_feeds_active"], [])
        self.assertFalse(report["buy_authorized"])
        self.assertFalse(report["telegram_transmission"])


if __name__ == "__main__":
    unittest.main()
