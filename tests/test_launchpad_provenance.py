import unittest
from launchpad_provenance import attribute_launchpad


class LaunchpadProvenanceTests(unittest.TestCase):
    def test_missing_origin_is_unverified(self):
        self.assertEqual(attribute_launchpad({"platform": "pump.fun", "network": "solana",
                                               "contract": "abc"})["status"], "UNVERIFIED")

    def test_chain_mismatch_is_unverified(self):
        result = attribute_launchpad({"platform": "four.meme", "network": "solana",
                                      "contract": "abc", "origin_url": "https://example.org/a"})
        self.assertEqual(result["platform"], "UNKNOWN")

    def test_claimed_origin_is_not_verified(self):
        result = attribute_launchpad({"platform": "pump.fun", "network": "solana",
                                      "contract": "abc", "origin_url": "https://example.org/a"})
        self.assertIn("VERIFICATION REQUIRED", result["status"])


if __name__ == "__main__":
    unittest.main()
