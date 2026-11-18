import datetime as dt
import unittest

import dexscreener_prices as dp
import signal_revisit as sr
from oracle_http import ProviderRateLimited

NOW = dt.datetime(2026, 11, 16, 9, tzinfo=dt.timezone.utc)
POOL = "0xAbC0000000000000000000000000000000000001"
TOKEN = "0xToken000000000000000000000000000000000001"
GT = f"https://api.geckoterminal.com/api/v2/networks/base/pools/multi/{POOL}"


def pair(address=POOL, base=TOKEN, chain="base", price="1.5", liquidity=20000):
    return {"chainId": chain, "pairAddress": address, "baseToken": {"address": base},
            "priceUsd": price, "liquidity": {"usd": liquidity}}


def gecko_payload(address=POOL, base=TOKEN):
    return {"data": [{"attributes": {"address": address, "base_token_price_usd": "1.4", "reserve_in_usd": "20000"},
                      "relationships": {"base_token": {"data": {"id": "base_" + base}}}}]}


def history():
    return {f"base:{POOL}": [{"at": (NOW - dt.timedelta(hours=2)).isoformat(), "token_address": TOKEN,
                             "base_token_price_usd": 1.0, "key": f"base:{POOL}", "network": "base"}]}


class AdapterTests(unittest.TestCase):
    def test_dexscreener_answers_without_touching_geckoterminal(self):
        calls, report = [], {}
        fetch = dp.make_fetch(lambda url: calls.append(url) or {"pairs": [pair()]},
                              lambda url: self.fail("GeckoTerminal must not be called"), report)
        payload = fetch(GT)
        self.assertEqual(calls, [f"{dp.DEX}/base/{POOL}"])
        attrs = payload["data"][0]["attributes"]
        self.assertEqual(attrs["address"], POOL)
        self.assertEqual(float(attrs["base_token_price_usd"]), 1.5)
        self.assertEqual(report["dexscreener_priced"], 1)

    def test_pools_dexscreener_omits_are_asked_from_geckoterminal(self):
        gecko = []
        fetch = dp.make_fetch(lambda url: {"pairs": None}, lambda url: gecko.append(url) or gecko_payload())
        payload = fetch(GT)
        self.assertEqual(gecko, [GT])
        self.assertEqual(payload["data"][0]["attributes"]["base_token_price_usd"], "1.4")

    def test_dexscreener_error_falls_back_and_gecko_rate_limit_propagates(self):
        def dex_down(url):
            raise OSError("down")
        self.assertEqual(dp.make_fetch(dex_down, lambda url: gecko_payload())(GT), gecko_payload())

        def limited(url):
            raise ProviderRateLimited("cooldown")
        with self.assertRaises(ProviderRateLimited):
            dp.make_fetch(lambda url: {"pairs": []}, limited)(GT)

    def test_wrong_chain_unrequested_pair_and_bad_price_are_not_accepted(self):
        other = "0x9990000000000000000000000000000000000009"
        pools = dp.convert("base", [POOL], {"pairs": [pair(chain="ethereum"), pair(address=other)]})
        self.assertEqual(pools, {})
        bad = dp.convert("base", [POOL], {"pairs": [pair(price="nan", liquidity=-1)]})
        self.assertIsNone(bad[POOL.lower()]["attributes"]["base_token_price_usd"])
        self.assertIsNone(bad[POOL.lower()]["attributes"]["reserve_in_usd"])
        with self.assertRaises(ValueError):
            dp.convert("base", [POOL], {"pairs": "oops"})

    def test_non_multi_or_unknown_network_urls_go_straight_to_geckoterminal(self):
        seen = []
        fetch = dp.make_fetch(lambda url: self.fail("no DexScreener"), lambda url: seen.append(url) or {})
        for url in ("https://api.geckoterminal.com/api/v2/networks/base/new_pools?page=1",
                    f"https://api.geckoterminal.com/api/v2/networks/zksync/pools/multi/{POOL}",
                    f"https://evil.example/api/v2/networks/base/pools/multi/{POOL}"):
            fetch(url)
        self.assertEqual(len(seen), 3)


class RevisitIntegrationTests(unittest.TestCase):
    def test_revisit_prices_through_dexscreener_and_keeps_identity_check(self):
        h, state = history(), {"pools": {}}
        fetch = dp.make_fetch(lambda url: {"pairs": [pair()]}, lambda url: self.fail("no fallback"))
        report = sr.revisit(h, fetch, NOW, state)
        self.assertEqual(report["priced"], 1)
        self.assertEqual(h[f"base:{POOL}"][-1]["price_usd"], 1.5)
        self.assertEqual(h[f"base:{POOL}"][-1]["source"], "DexScreener indicative pair price")

        h, state = history(), {"pools": {}}
        impostor = dp.make_fetch(lambda url: {"pairs": [pair(base="0xOther")]}, lambda url: self.fail("no fallback"))
        report = sr.revisit(h, impostor, NOW, state)
        self.assertEqual(report["identity_mismatch"], 1)
        self.assertEqual(report["priced"], 0)

    def test_dexscreener_silence_never_marks_pool_vanished(self):
        h, state = history(), {"pools": {}}
        fetch = dp.make_fetch(lambda url: {"pairs": []}, lambda url: gecko_payload())
        report = sr.revisit(h, fetch, NOW, state)
        self.assertEqual(report["pool_not_returned"], 0)
        self.assertEqual(report["priced"], 1)


if __name__ == "__main__":
    unittest.main()
