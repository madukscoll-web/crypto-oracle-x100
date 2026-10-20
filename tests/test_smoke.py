import unittest
import crypto_oracle_scanner as scanner

class ScannerSmokeTest(unittest.TestCase):
    def test_networks_configured(self):
        self.assertTrue(scanner.NETWORKS)

    def test_alert_limit_positive(self):
        self.assertGreater(scanner.MAX_ALERTS_PER_RUN, 0)

if __name__ == '__main__':
    unittest.main()
