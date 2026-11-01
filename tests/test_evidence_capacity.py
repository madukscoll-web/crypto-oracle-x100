"""Bounded evidence assessment capacity: never change buy eligibility."""
import unittest
from crypto_oracle_scanner import evidence_capacity

class EvidenceCapacityTests(unittest.TestCase):
    def test_default_and_invalid(self):
        self.assertEqual(evidence_capacity("6"), 6)
        self.assertEqual(evidence_capacity(None), 6)
        self.assertEqual(evidence_capacity("invalid"), 6)
    def test_bounded_opt_in(self):
        self.assertEqual(evidence_capacity("8"), 8)
        self.assertEqual(evidence_capacity("1000"), 8)
        self.assertEqual(evidence_capacity("0"), 1)
        self.assertEqual(evidence_capacity("-5"), 1)
