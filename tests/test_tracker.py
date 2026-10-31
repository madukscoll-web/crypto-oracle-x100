import datetime as dt
import unittest
import signal_tracker as tracker


def item(at, price=0.1):
    return {"key": "base:pool", "token_address": "0x123",
            "base_token_price_usd": price, "observed_at": at,
            "entry_pattern": "MOMENTUM WATCH", "market_setup": "PRIORITY VERIFY"}


class TrackerTests(unittest.TestCase):
    def test_duplicate_rejected(self):
        history = {}
        stamp = "2026-10-01T12:00:00+00:00"
        self.assertTrue(tracker.record(history, item(stamp)))
        self.assertFalse(tracker.record(history, item(stamp)))

    def test_invalid_price_rejected(self):
        self.assertFalse(tracker.record({}, item("2026-10-01T12:00:00+00:00", 0)))
        self.assertFalse(tracker.record({}, item("2026-10-01T12:00:00+00:00", float("nan"))))

    def test_horizon_measured_only_with_observation(self):
        history = {}
        tracker.record(history, item("2026-10-01T12:00:00+00:00", 0.1))
        tracker.record(history, item("2026-10-02T12:30:00+00:00", 0.11))
        values = tracker.outcomes(history["base:pool"])
        self.assertEqual(values[0]["status"], "OBSERVED")
        self.assertAlmostEqual(values[0]["change_percent"], 10)
        self.assertEqual(values[1]["status"], "PENDING")

    def test_non_signal_not_recorded(self):
        history = {}
        lead = item("2026-10-01T12:00:00+00:00")
        lead["entry_pattern"] = "WAIT"
        self.assertFalse(tracker.record(history, lead))
        self.assertEqual(history, {})

    def test_token_identity_change_rejected(self):
        history = {}
        self.assertTrue(tracker.record(history, item("2026-10-01T12:00:00+00:00")))
        changed = item("2026-10-02T12:00:00+00:00")
        changed["token_address"] = "0xother"
        self.assertFalse(tracker.record(history, changed))
        self.assertEqual(len(history["base:pool"]), 1)

    def test_late_sample_not_mislabelled(self):
        history = {}
        tracker.record(history, item("2026-10-01T12:00:00+00:00", 0.1))
        tracker.record(history, item("2026-10-05T12:00:00+00:00", 0.2))
        self.assertEqual(tracker.outcomes(history["base:pool"])[0]["status"], "NO_TIMELY_SAMPLE")

    def test_backdated_sample_cannot_rewrite_entry(self):
        history = {}
        tracker.record(history, item("2026-10-02T12:00:00+00:00", .1))
        self.assertFalse(tracker.record(history, item("2026-10-01T12:00:00+00:00", .001)))
        self.assertEqual(history["base:pool"][0]["price_usd"], .1)

    def test_capacity_preserves_original_entry_and_all_signals(self):
        from unittest.mock import patch
        import tempfile, pathlib
        history = {}
        tracker.record(history, item("2026-10-01T12:00:00+00:00", .1))
        with patch.object(tracker, "MAX_OBSERVATIONS", 1):
            self.assertFalse(tracker.record(history, item("2026-10-02T12:00:00+00:00", .2)))
        other = item("2026-10-01T12:00:00+00:00"); other["key"] = "base:other"
        with patch.object(tracker, "MAX_TOKENS", 1):
            self.assertFalse(tracker.record(history, other))
        history["base:legacy"] = list(history["base:pool"])
        with tempfile.TemporaryDirectory() as folder, patch.object(tracker, "MAX_TOKENS", 1):
            path = pathlib.Path(folder) / "history.json"
            tracker.save(history, path)
            self.assertEqual(tracker.load(path), history)

    def test_solana_case_change_never_splices_history(self):
        history = {}
        lead = item("2026-10-01T12:00:00+00:00")
        lead.update(key="solana:pool", token_address="Abc", network="solana")
        tracker.record(history, lead)
        lead.update(observed_at="2026-10-02T12:00:00+00:00", token_address="abc")
        self.assertFalse(tracker.record(history, lead))

    def test_boolean_price_is_not_measurement(self):
        self.assertFalse(tracker.record({}, item("2026-10-01T12:00:00+00:00", True)))

    def test_long_horizons_and_sampled_drawdown(self):
        rows = [{"at": f"2026-10-0{i+1}T12:00:00+00:00", "price_usd": p}
                for i, p in enumerate([1, 2, .5, 1.5])]
        result = tracker.sampled_risk(rows)
        self.assertEqual(result["maximum_favorable_excursion_percent"], 100)
        self.assertEqual(result["maximum_adverse_excursion_percent"], -50)
        self.assertEqual(result["maximum_drawdown_percent"], -75)
        self.assertIsNone(result["execution_adjusted_returns"])
        self.assertIn(2160, tracker.HORIZONS_HOURS)
        self.assertIn(8760, tracker.HORIZONS_HOURS)


if __name__ == "__main__":
    unittest.main()
