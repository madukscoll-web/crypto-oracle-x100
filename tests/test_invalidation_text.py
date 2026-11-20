import unittest

import technical_followup as f
from research_notice import _issue, verified_text

ROW = {"pair": "NEAR_USDT", "alert": {"interval": "4h", "invalidation": "3.098",
                                      "delivered_at": "2026-11-19T10:38:22.589696+00:00"}}
BOOK = {"best_bid": "3"}
SAMPLE = {"observed_at": "2026-11-20T10:17:30.574080+00:00",
          "source_url": "https://api.gateio.ws/api/v4/spot/order_book?currency_pair=NEAR_USDT&limit=20&with_id=true"}


class InvalidationTextTests(unittest.TestCase):
    def test_plain_english_with_local_and_utc_times(self):
        text = f.invalidation_text(ROW, BOOK, SAMPLE)
        self.assertEqual(text.splitlines()[0], "INVALIDATED SETUP")
        self.assertIn("In Plain English", text)
        self.assertIn("The NEAR reversal watch sent on 19 Nov 2026 is cancelled", text)
        self.assertIn("fell to 3 USDT, below the 3.098 USDT level", text)
        self.assertIn("19 Nov 2026, 11:38 WAT (10:38 UTC)", text)
        self.assertIn("20 Nov 2026, 11:17 WAT (10:17 UTC)", text)
        self.assertIn("bought nothing", text)
        self.assertNotIn("Withdraw this hypothesis", text)
        self.assertNotIn(".589696", text)

    def test_still_a_valid_signed_notice_and_never_a_buy(self):
        notice = _issue("INVALIDATED SETUP", f.invalidation_text(ROW, BOOK, SAMPLE))
        text = verified_text(notice)
        self.assertTrue(text.startswith("INVALIDATED SETUP"))
        self.assertNotIn("BUY CANDIDATE", text)
        self.assertLess(len(text), 3900)

    def test_unparseable_time_is_shown_raw_not_invented(self):
        row = {"pair": "NEAR_USDT", "alert": dict(ROW["alert"], delivered_at="unknown")}
        self.assertIn("Watch first sent: unknown", f.invalidation_text(row, BOOK, SAMPLE))
        self.assertEqual(f._when("2026-11-20T10:17:30"), "2026-11-20T10:17:30")


if __name__ == "__main__":
    unittest.main()
