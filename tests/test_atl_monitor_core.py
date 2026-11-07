import unittest
from decimal import Decimal
from atl_monitor_core import cap_class, classify_low, labeled_message, LABELS

class ATLCoreTests(unittest.TestCase):
    def test_cap_boundaries(self):
        self.assertEqual(cap_class(200000000, verified=True, fresh=True), "MID_CAP")
        self.assertEqual(cap_class(1000000000, verified=True, fresh=True), "MID_CAP")
        self.assertEqual(cap_class(1000000001, verified=True, fresh=True), "HIGH_CAP")
        self.assertEqual(cap_class(199999999, verified=True, fresh=True), "EXCLUDED")
        self.assertEqual(cap_class(1000000000, verified=True), "UNVERIFIED")
        self.assertEqual(cap_class(1000000000, verified=True, fresh=True, conflicting=True), "UNVERIFIED")
    def test_price_validation(self):
        for value in (0, -1, True, "NaN", "Infinity", "invalid"):
            self.assertEqual(classify_low(value, 1, comparable=True)["status"], "UNAVAILABLE")
    def test_five_percent_and_lifetime(self):
        self.assertEqual(classify_low("1.05", 1, lifetime_complete=True, comparable=True)["status"], "NEAR ALL-TIME LOW")
        self.assertEqual(classify_low("1.05", 1, comparable=True)["status"], "NEAR OBSERVED LOW")
        self.assertEqual(classify_low("1.05001", 1, lifetime_complete=True, comparable=True)["status"], "NO_EVENT")
    def test_new_low_requires_corroboration(self):
        self.assertEqual(classify_low(".9", 1, lifetime_complete=True, comparable=True)["status"], "UNVALIDATED_LOW")
        self.assertEqual(classify_low(".9", 1, lifetime_complete=True, comparable=True, corroborated=True)["status"], "ALL-TIME LOW")
        self.assertEqual(classify_low(".9", 1, comparable=True, corroborated=True)["status"], "LOWEST OBSERVED PRICE")
    def test_incomparable_is_unavailable(self):
        self.assertEqual(classify_low(1, 2)["status"], "UNAVAILABLE")
    def test_labels(self):
        for label in LABELS:
            self.assertTrue(labeled_message(label, "Research only").startswith(label + "\n"))
        with self.assertRaises(ValueError):
            labeled_message("VERIFIED BUY", "x")

if __name__ == "__main__":
    unittest.main()

