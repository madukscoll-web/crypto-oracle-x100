import unittest
from unittest import mock

import crypto_oracle_scanner as scanner
import dexscreener_prices as dp

POOL = "0xAbC0000000000000000000000000000000000001"
BASE = "0xBase000000000000000000000000000000000001"
QUOTE = "0x4200000000000000000000000000000000000006"


def pair(**over):
    p = {"chainId": "base", "pairAddress": POOL, "priceUsd": "0.0123",
         "baseToken": {"address": BASE, "symbol": "NEW"}, "quoteToken": {"address": QUOTE, "symbol": "WETH"},
         "liquidity": {"usd": 50000}, "volume": {"h24": 120000}, "txns": {"h1": {"buys": 30, "sells": 10}},
         "priceChange": {"h1": 4.5, "h24": -12}}
    p.update(over)
    return p


class PoolPayloadTests(unittest.TestCase):
    def test_exact_pool_becomes_geckoterminal_shaped_payload(self):
        payload = dp.pool_payload("base", POOL, lambda url: {"pairs": [pair()]})
        self.assertEqual(scanner._relationship_token(payload, "base_token"), (BASE, "NEW"))
        self.assertEqual(scanner._relationship_token(payload, "quote_token")[0], QUOTE)
        attrs = payload["data"]["attributes"]
        self.assertEqual(attrs["address"], POOL)
        self.assertEqual(attrs["transactions"]["h1"], {"buys": 30, "sells": 10})
        self.assertEqual(attrs["price_source"], "dexscreener")

    def test_cannot_prove_pool_returns_none(self):
        cases = [{"pairs": []}, {"pairs": None}, {"pairs": [pair(chainId="ethereum")]},
                 {"pairs": [pair(pairAddress="0x9990000000000000000000000000000000000009")]},
                 {"pairs": [pair(baseToken={"symbol": "X"})]}, "junk"]
        for response in cases:
            self.assertIsNone(dp.pool_payload("base", POOL, lambda url, r=response: r), response)
        self.assertIsNone(dp.pool_payload("zksync", POOL, lambda url: {"pairs": [pair()]}))

        def down(url):
            raise OSError("down")
        self.assertIsNone(dp.pool_payload("base", POOL, down))

    def test_bad_numbers_are_dropped_not_invented(self):
        payload = dp.pool_payload("base", POOL, lambda url: {"pairs": [pair(
            priceUsd="nan", liquidity={"usd": -5}, txns={"h1": {"buys": 1.5, "sells": "x"}}, volume={"h24": "inf"})]})
        attrs = payload["data"]["attributes"]
        self.assertIsNone(attrs["base_token_price_usd"])
        self.assertIsNone(attrs["reserve_in_usd"])
        self.assertEqual(attrs["transactions"]["h1"], {"buys": None, "sells": None})
        self.assertIsNone(attrs["volume_usd"]["h24"])


class EnrichTests(unittest.TestCase):
    def item(self):
        return {"key": f"base:{POOL}", "network": "base", "address": POOL, "base_token_price_usd": 1}

    def test_enrich_uses_dexscreener_and_skips_rate_limited_geckoterminal(self):
        def gecko(url):
            if "/pools/" + POOL in url:
                raise scanner.ProviderRateLimited("cooldown")
            return {"data": []}
        source = lambda network, address: dp.pool_payload(network, address, lambda url: {"pairs": [pair()]})
        with mock.patch.object(scanner, "_fresh_discovery_snapshot", return_value=None):
            item = scanner.enrich(self.item(), fetch=gecko, delay=0, pool_source=source)
        self.assertEqual(item["token_address"], BASE)
        self.assertEqual(item["token_identity_status"], "Base token from DexScreener pool relationship")
        self.assertTrue(item["price_source"].startswith("DexScreener"))
        self.assertIn("dexscreener.com", item["market_source_url"])

    def test_enrich_falls_back_to_geckoterminal_when_dexscreener_cannot_prove_pool(self):
        calls = []
        gecko_pool = {"data": {"attributes": {"address": POOL, "base_token_price_usd": "2"},
                               "relationships": {"base_token": {"data": {"id": "t1"}}, "quote_token": {"data": {"id": "t2"}}}},
                      "included": [{"type": "token", "id": "t1", "attributes": {"address": BASE, "symbol": "NEW"}},
                                   {"type": "token", "id": "t2", "attributes": {"address": QUOTE, "symbol": "WETH"}}]}

        def gecko(url):
            calls.append(url)
            return gecko_pool if "/pools/" + POOL in url else {"data": []}
        with mock.patch.object(scanner, "_fresh_discovery_snapshot", return_value=None):
            item = scanner.enrich(self.item(), fetch=gecko, delay=0, pool_source=lambda n, a: None)
        self.assertTrue(any("/pools/" + POOL in c for c in calls))
        self.assertEqual(item["token_identity_status"], "Base token from GeckoTerminal pool relationship")

    def test_scan_wires_dexscreener_identity(self):
        import inspect
        self.assertIn("pool_source=lambda network, address: dexscreener_prices.pool_payload(",
                      inspect.getsource(scanner.main))


if __name__ == "__main__":
    unittest.main()
