import unittest
import technical_watch
import crypto_oracle_scanner as scanner


class PlainEnglishTests(unittest.TestCase):
    def test_reversal_summary_says_nothing_was_bought_and_names_pair(self):
        text = technical_watch.plain_summary('EARLY BULLISH REVERSAL WATCH', {'pair': 'AVAX_USDT'})
        self.assertIn('AVAX_USDT', text)
        self.assertIn('NOT bought anything', text)
        self.assertIn('unconfirmed', text)

    def test_unknown_classification_still_explained(self):
        self.assertIn('human to review', technical_watch.plain_summary('OTHER', {'pair': 'X_USDT'}))

    def test_readable_times(self):
        self.assertEqual(scanner.readable_observed('2026-11-12T00:17:35.115604+00:00'), '12 Nov 2026 00:17 UTC')
        self.assertEqual(scanner.readable_observed('garbage'), 'garbage')
        self.assertEqual(technical_watch.readable_utc('2026-11-12T00:17:35+00:00'), '12 Nov 2026 00:17 UTC')


if __name__ == '__main__':
    unittest.main()
