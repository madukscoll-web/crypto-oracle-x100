import inspect
import unittest
import urllib.error
from unittest.mock import patch

import crypto_oracle_scanner as scanner
import oracle_http

HOST = "api.geckoterminal.com"
POOL = "0x" + "b" * 40
TOKEN = "0x" + "a" * 40
URL = f"https://{HOST}/api/v2/networks/base/pools/{POOL}?include=base_token,quote_token"


def too_many():
    return urllib.error.HTTPError(URL, 429, "Too Many Requests", {}, None)


def pool_payload():
    return {"data": {"id": "base_" + POOL, "attributes": {"address": POOL, "reserve_in_usd": "250000",
            "volume_usd": {"h24": "500000"}, "transactions": {"h1": {"buys": 70, "sells": 60}},
            "price_change_percentage": {"h1": "2", "h24": "5"}, "base_token_price_usd": "1.5"},
            "relationships": {"base_token": {"data": {"id": "base_" + TOKEN}},
                              "quote_token": {"data": {"id": "base_0x" + "c" * 40}}}},
            "included": [{"type": "token", "id": "base_" + TOKEN, "attributes": {"address": TOKEN, "symbol": "ABC"}},
                         {"type": "token", "id": "base_0x" + "c" * 40, "attributes": {"address": "0x" + "c" * 40, "symbol": "WETH"}}]}


class EnrichmentWaitTests(unittest.TestCase):
    def setUp(self):
        scanner._ENRICH_WAIT["used"] = 0.0
        scanner._RATE_WAIT["used"] = 0.0
        oracle_http._COOLDOWN_UNTIL.pop(HOST, None)
        self.addCleanup(oracle_http._COOLDOWN_UNTIL.pop, HOST, None)

    def test_short_cooldown_waited_then_retried_once(self):
        calls, sleeps = [], []
        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 60
                raise too_many()
            return {"ok": True}
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            self.assertEqual(scanner.fetch_enrichment(URL), {"ok": True})
        self.assertEqual((len(calls), len(sleeps)), (2, 1))
        self.assertGreater(scanner._ENRICH_WAIT["used"], 55)
        self.assertEqual(scanner._RATE_WAIT["used"], 0.0)   # discovery budget is separate

    def test_budget_exhaustion_raises_without_sleeping(self):
        scanner._ENRICH_WAIT["used"] = scanner.ENRICH_RATE_LIMIT_WAIT_BUDGET_SECONDS - 10
        oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 60
        sleeps = []
        def fetch(url): raise too_many()
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(urllib.error.HTTPError):
                scanner.fetch_enrichment(URL)
        self.assertEqual(sleeps, [])

    def test_long_cooldown_and_non_429_errors_are_not_waited(self):
        sleeps = []
        oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 600
        def limited(url): raise too_many()
        with patch.object(scanner, "fetch_json", limited), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(urllib.error.HTTPError):
                scanner.fetch_enrichment(URL)
        err = urllib.error.HTTPError(URL, 500, "boom", {}, None)
        def server(url): raise err
        with patch.object(scanner, "fetch_json", server), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(urllib.error.HTTPError):
                scanner.fetch_enrichment(URL)
        self.assertEqual(sleeps, [])

    def item(self):
        return {"network": "base", "address": POOL, "key": "base:" + POOL, "discovery_mode": "new_pools"}

    def test_enrich_resolves_identity_after_waiting_out_a_429(self):
        calls, sleeps = [], []
        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 45
                raise too_many()
            return pool_payload() if "/pools/" + POOL in url else {"data": []}
        item = self.item()
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append), \
             patch.object(scanner, "SECURITY_CHAIN_IDS", {}):
            scanner.enrich(item, delay=0)
        self.assertEqual(item["token_address"], TOKEN)
        self.assertTrue(item["token_identity_status"].startswith("Base token"))

    def test_without_the_wait_identity_stays_unverified(self):
        def fetch(url):
            oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 600
            raise too_many()
        item = self.item()
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", lambda s: None):
            scanner.enrich(item, delay=0)
        self.assertEqual(item["token_address"], "UNVERIFIED")   # still fail-closed

    def test_optional_previous_pool_lookup_never_spends_wait_budget(self):
        calls, sleeps = [], []
        def fetch(url):
            calls.append(url)
            if "/tokens/" in url:
                oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 30
                raise too_many()
            return pool_payload()
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append), \
             patch.object(scanner, "SECURITY_CHAIN_IDS", {}):
            scanner.enrich(self.item(), delay=0)
        self.assertEqual([x for x in sleeps if x > 0], [])   # sleep(0) is pacing, not a wait
        self.assertEqual(scanner._ENRICH_WAIT["used"], 0.0)

    def test_budget_is_reset_each_run_and_default_enrich_uses_the_waiting_fetch(self):
        self.assertIn('_ENRICH_WAIT["used"] = 0.0', inspect.getsource(scanner.main))
        self.assertIn("fetch or fetch_enrichment", inspect.getsource(scanner.enrich))


if __name__ == "__main__":
    unittest.main()
