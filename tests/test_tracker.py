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


if __name__ == "__main__":
    unittest.main()
