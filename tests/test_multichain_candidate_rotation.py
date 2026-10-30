import unittest
from multichain_candidate_rotation import rotate

class RotationTests(unittest.TestCase):
    def test_round_robin(self):
        candidates = [{"network": n, "token_address": str(i)}
                      for n in ("solana", "eth", "base") for i in range(3)]
        result = rotate(candidates, per_run=3)
        self.assertEqual([x["network"] for x in result["selected"]],
                         ["solana", "eth", "base"])
        self.assertFalse(result["buy_authorized"])
    def test_cursor_shifts_first_chain(self):
        candidates = [{"network": n, "token_address": "a"} for n in ("solana", "eth")]
        self.assertEqual(rotate(candidates, per_run=1, cursor=1)["selected"][0]["network"], "eth")
    def test_planned_chains_excluded(self):
        result = rotate([{"network": "sui", "token_address": "a"}])
        self.assertEqual(result["selected"], [])
    def test_dedup(self):
        item = {"network": "solana", "token_address": "abc"}
        self.assertEqual(len(rotate([item, item])["selected"]), 1)
    def test_invalid_budget(self):
        with self.assertRaises(ValueError):
            rotate([], per_run=0)

if __name__ == "__main__":
    unittest.main()
