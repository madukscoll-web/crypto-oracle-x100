import datetime as dt
import tempfile
import pathlib
import unittest

from gate_alert_state import eligible_alerts, mark_delivered, read_state, save_state

NOW = dt.datetime(2026, 10, 20, 12, tzinfo=dt.timezone.utc)
P = {"pair": "ABC_USDT", "status": "WATCHLIST_ONLY"}

class AlertStateTests(unittest.TestCase):
    def test_batch_dedup(self):
        self.assertEqual(len(eligible_alerts([P, P], {}, NOW)), 1)
    def test_cooldown(self):
        state = {"ABC_USDT": (NOW - dt.timedelta(hours=3)).isoformat()}
        self.assertEqual(eligible_alerts([P], state, NOW), [])
        self.assertEqual(len(eligible_alerts([P], state, NOW + dt.timedelta(hours=25))), 1)
    def test_future_state_fails_closed(self):
        state = {"ABC_USDT": (NOW + dt.timedelta(hours=2)).isoformat()}
        self.assertEqual(eligible_alerts([P], state, NOW), [])
    def test_only_research_proposals(self):
        self.assertEqual(eligible_alerts([{**P, "status":"BUY CANDIDATE"}], {}, NOW), [])
    def test_max_zero(self):
        self.assertEqual(eligible_alerts([P], {}, NOW, max_alerts=0), [])
    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "state.json"
            state = {}
            mark_delivered(state, "ABC_USDT", NOW)
            save_state(path, state)
            self.assertEqual(read_state(path), state)

if __name__ == "__main__":
    unittest.main()
