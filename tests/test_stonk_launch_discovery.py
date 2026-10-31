import unittest
from stonk_launch_discovery import parse_launches, run


class StonkLaunchTests(unittest.TestCase):
    def test_degraded_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_launches({"degraded": True, "pools": []})
        with self.assertRaises(ValueError):
            parse_launches({"pools": []})

    def test_empty_valid_ledger(self):
        report = run(fetch=lambda url: {"degraded": False, "pools": []})
        self.assertEqual(report["count"], 0)
        self.assertFalse(report["buy_authorized"])
        self.assertFalse(report["telegram_transmission"])

    def test_malformed_token_excluded(self):
        rows, invalid = parse_launches({"degraded": False, "pools": [{"mint": "invalid!"}]})
        self.assertEqual(rows, [])
        self.assertEqual(invalid, 1)


if __name__ == "__main__":
    unittest.main()
