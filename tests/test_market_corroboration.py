import unittest
import market_corroboration as m


class MarketCorroborationTests(unittest.TestCase):
    def setUp(self):
        self.item = {"network": "base", "address": "0xpool",
                     "token_address": "0xtoken", "base_token_price_usd": 0.1}

    def test_exact_match(self):
        def fetch(_):
            return {"pairs": [{"chainId": "base", "pairAddress": "0xpool",
                               "baseToken": {"address": "0xtoken"}, "priceUsd": "0.101"}]}
        self.assertEqual(m.check(self.item, fetch)["status"], "CORROBORATED")

    def test_wrong_contract_never_passes(self):
        def fetch(_):
            return {"pairs": [{"chainId": "base", "pairAddress": "0xpool",
                               "baseToken": {"address": "0xother"}, "priceUsd": "0.1"}]}
        self.assertEqual(m.check(self.item, fetch)["status"], "CONFLICTING")

    def test_price_disagreement(self):
        def fetch(_):
            return {"pairs": [{"chainId": "base", "pairAddress": "0xpool",
                               "baseToken": {"address": "0xtoken"}, "priceUsd": "0.2"}]}
        self.assertEqual(m.check(self.item, fetch)["status"], "CONFLICTING")

    def test_provider_failure(self):
        def fetch(_):
            raise OSError("offline")
        self.assertEqual(m.check(self.item, fetch)["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
