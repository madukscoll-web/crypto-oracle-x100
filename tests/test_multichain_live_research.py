import unittest
from multichain_live_research import run

class Adapter:
    network = "solana"
    def __init__(self, fetch): pass
    def discover(self):
        return {"rows": [{"network": "solana",
            "token_address": "So11111111111111111111111111111111111111112",
            "address": "11111111111111111111111111111111"}],
            "failures": [], "observations": []}

class RunnerTests(unittest.TestCase):
    def test_read_only_and_dedup(self):
        result = run(1, 0, fetch=lambda url: {}, adapters=(Adapter, Adapter))
        self.assertEqual(result["unique_tokens"], 1)
        self.assertEqual(len(result["selected"]), 1)
        self.assertFalse(result["buy_authorized"])
        self.assertFalse(result["telegram_transmission"])
    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            run(0, fetch=lambda url: {}, adapters=())

if __name__ == "__main__":
    unittest.main()
