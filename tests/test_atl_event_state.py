import tempfile
import unittest
from pathlib import Path
from atl_event_state import event_key, load_state, eligible_event, confirm_delivery

class EventTests(unittest.TestCase):
    def test_dedup_and_new_baseline(self):
        a = event_key("eip155:1/native:eth", "NEAR ALL-TIME LOW | WATCH", "low1", "r1")
        b = event_key("eip155:1/native:eth", "NEAR ALL-TIME LOW | WATCH", "low2", "r1")
        self.assertNotEqual(a, b)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            flags = dict(identity_verified=True, observation_fresh=True,
                         history_validated=True, evidence_qualified=True, security_passed=True)
            self.assertTrue(eligible_event(load_state(p), a, **flags))
            self.assertFalse(confirm_delivery(p, a, {"ok": True}, "2026-11-07T00:00:00Z"))
            self.assertTrue(eligible_event(load_state(p), a, **flags))
            self.assertTrue(confirm_delivery(p, a, {"ok": True, "result": {"message_id": 123}}, "2026-11-07T00:00:00Z"))
            self.assertFalse(eligible_event(load_state(p), a, **flags))
            self.assertTrue(eligible_event(load_state(p), b, **flags))
            flags["security_passed"] = False
            self.assertFalse(eligible_event(load_state(p), b, **flags))
    def test_reject_buy_and_incomplete(self):
        with self.assertRaises(ValueError):
            event_key("eth", "BUY CANDIDATE | MANUAL REVIEW", "low", "rev")
        with self.assertRaises(ValueError):
            event_key("", "ALL-TIME LOW | WATCH", "low", "rev")

if __name__ == "__main__":
    unittest.main()

