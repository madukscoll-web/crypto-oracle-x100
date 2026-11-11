import datetime as dt
import unittest

import signal_revisit as sr
from oracle_http import ProviderRateLimited

NOW = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)
TOKEN = "0x" + "a" * 40
POOL = "0x" + "b" * 40


def iso(hours_ago):
    return (NOW - dt.timedelta(hours=hours_ago)).isoformat()


def hist(hours_ago=30, price=1.0, pool=POOL, network="base"):
    return {f"{network}:{pool}": [{"at": iso(hours_ago), "price_usd": price, "token_address": TOKEN,
                                   "entry_pattern": "MOMENTUM WATCH", "market_setup": "x", "source": "s"}]}


def pool_payload(price="0.8", reserve="50000", token=TOKEN, pool=POOL, network="base"):
    return {"data": [{"attributes": {"address": pool, "base_token_price_usd": price, "reserve_in_usd": reserve},
                      "relationships": {"base_token": {"data": {"id": f"{network}_{token}"}}}}]}


def state():
    return {"version": 1, "pools": {}}


class RevisitTests(unittest.TestCase):
    def test_signal_not_rediscovered_still_gets_priced(self):
        h = hist()
        report = sr.revisit(h, lambda url: pool_payload(), NOW, state())
        self.assertEqual(report["priced"], 1)
        self.assertEqual(len(h[f"base:{POOL}"]), 2)
        self.assertEqual(h[f"base:{POOL}"][-1]["price_usd"], 0.8)

    def test_history_is_append_only(self):
        h = hist(); before = list(h[f"base:{POOL}"])
        sr.revisit(h, lambda url: pool_payload(), NOW, state())
        self.assertEqual(h[f"base:{POOL}"][:1], before)

    def test_recent_observation_not_repriced(self):
        h = hist(hours_ago=0.2)
        calls = []
        report = sr.revisit(h, lambda url: calls.append(url) or pool_payload(), NOW, state())
        self.assertEqual((report["due"], calls), (0, []))

    def test_old_signals_stop_being_revisited(self):
        self.assertEqual(sr.revisit(hist(hours_ago=800), lambda u: pool_payload(), NOW, state())["due"], 0)

    def test_rate_limit_stops_cleanly_without_raising(self):
        def fetch(url): raise ProviderRateLimited("429")
        h = hist(); report = sr.revisit(h, fetch, NOW, state())
        self.assertEqual(report["stopped"], "RATE_LIMITED")
        self.assertEqual(len(h[f"base:{POOL}"]), 1)

    def test_provider_error_and_malformed_response_do_not_raise(self):
        def boom(url): raise OSError("down")
        self.assertEqual(sr.revisit(hist(), boom, NOW, state())["stopped"], "PROVIDER_ERROR")
        self.assertEqual(sr.revisit(hist(), lambda u: {"data": "x"}, NOW, state())["stopped"], "MALFORMED_RESPONSE")

    def test_pool_missing_three_times_is_vanished_and_not_retried(self):
        h, st = hist(), state()
        for i in range(3):
            report = sr.revisit(h, lambda u: {"data": []}, NOW + dt.timedelta(hours=i + 1), st)
        self.assertEqual(st["pools"][f"base:{POOL}"]["status"], "VANISHED")
        self.assertEqual(sr.due(h, st, NOW + dt.timedelta(hours=10)), [])

    def test_different_base_token_is_never_spliced(self):
        h, st = hist(), state()
        report = sr.revisit(h, lambda u: pool_payload(token="0x" + "c" * 40), NOW, st)
        self.assertEqual(report["identity_mismatch"], 1)
        self.assertEqual(len(h[f"base:{POOL}"]), 1)

    def test_thin_liquidity_flagged_unrealizable(self):
        st = state()
        report = sr.revisit(hist(), lambda u: pool_payload(reserve="900"), NOW, st)
        self.assertEqual(report["unrealizable"], 1)
        self.assertEqual(st["pools"][f"base:{POOL}"]["status"], "UNREALIZABLE")

    def test_invalid_price_is_not_recorded(self):
        for bad in ("0", "-1", "nan", None, "abc"):
            h = hist()
            sr.revisit(h, lambda u, b=bad: pool_payload(price=b), NOW, state())
            self.assertEqual(len(h[f"base:{POOL}"]), 1, bad)

    def test_batches_bounded_and_networks_not_starved(self):
        h = {}
        for n in range(70):
            h.update(hist(pool="0x%040x" % (n + 1), network="base"))
        h.update(hist(pool="So1" + "1" * 40, network="solana"))
        urls = []
        report = sr.revisit(h, lambda url: urls.append(url) or {"data": []}, NOW, state(), max_batches=2)
        self.assertEqual(report["batches"], 2)
        self.assertTrue(any("/networks/solana/" in u for u in urls))

    def test_solana_addresses_are_case_sensitive(self):
        pool = "AbCdEf" + "1" * 38
        h = hist(pool=pool, network="solana")
        h[f"solana:{pool}"][0]["token_address"] = "TokenAbC"
        payload = {"data": [{"attributes": {"address": pool, "base_token_price_usd": "2", "reserve_in_usd": "90000"},
                             "relationships": {"base_token": {"data": {"id": "solana_TokenAbC"}}}}]}
        self.assertEqual(sr.revisit(h, lambda u: payload, NOW, state())["priced"], 1)


class SummaryTests(unittest.TestCase):
    def history_with_outcomes(self, n, ratio):
        h = {}
        for i in range(n):
            key = "base:0x%040x" % (i + 1)
            h[key] = [{"at": iso(30), "price_usd": 1.0, "token_address": TOKEN},
                      {"at": iso(5.9), "price_usd": ratio, "token_address": TOKEN}]
        return h

    def test_small_sample_refuses_conclusion(self):
        summary = sr.performance_summary(self.history_with_outcomes(5, 1.5), state(), NOW)
        self.assertIn("INSUFFICIENT SAMPLE", summary["conclusion"])
        self.assertEqual(summary["horizons"]["24"]["measured"]["n"], 5)

    def test_assumed_cost_is_labelled_and_applied(self):
        summary = sr.performance_summary(self.history_with_outcomes(3, 1.1), state(), NOW)
        row = summary["horizons"]["24"]
        self.assertTrue(summary["cost_is_assumption"])
        self.assertAlmostEqual(row["measured"]["median_percent"] - row["net_of_assumed_cost"]["median_percent"], 3.0)

    def test_unrealizable_exit_counts_as_total_loss_in_conservative_view(self):
        h = self.history_with_outcomes(2, 1.5)
        st = state()
        st["pools"]["base:0x%040x" % 1] = {"status": "UNREALIZABLE"}
        row = sr.performance_summary(h, st, NOW)["horizons"]["24"]
        self.assertEqual(row["measured"]["positive"], 2)
        self.assertEqual(row["conservative"]["positive"], 1)
        self.assertEqual(row["conservative"]["mean_percent"], (-100 + 50) / 2)

    def test_vanished_pool_past_horizon_counts_as_loss_even_without_sample(self):
        h = {"base:" + POOL: [{"at": iso(30), "price_usd": 1.0, "token_address": TOKEN}]}
        st = state(); st["pools"]["base:" + POOL] = {"status": "VANISHED"}
        row = sr.performance_summary(h, st, NOW)["horizons"]["24"]
        self.assertIsNone(row["measured"])
        self.assertEqual(row["conservative"]["median_percent"], -100.0)

    def test_empty_history_is_safe(self):
        self.assertEqual(sr.performance_summary({}, state(), NOW)["tracked"], 0)

    def test_state_roundtrip_and_validation(self):
        import tempfile, pathlib, json
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "s.json"
            self.assertEqual(sr.load_state(path), {"version": 1, "pools": {}})
            st = state(); st["pools"]["k"] = {"status": "ACTIVE"}
            sr.save_state(st, path); self.assertEqual(sr.load_state(path), st)
            path.write_text("[]")
            with self.assertRaises(ValueError): sr.load_state(path)


if __name__ == "__main__":
    unittest.main()
