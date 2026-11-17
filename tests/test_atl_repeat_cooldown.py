import datetime as dt
import unittest
from decimal import Decimal

from atl_evidence import dossier, notify, repeat_guard, REPEAT_COOLDOWN_DAYS
from test_atl_evidence import AT, NOW, inputs, transport

ENV = dict(TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='42')


def build(low):
    observation, details, chart = inputs()
    observation['provider_atl_candidate']['source_atl_usd'] = low
    return dossier(observation, details, chart, observed_at=AT, now=NOW.timestamp())


def sends(log):
    return [x for x in log if x[0] == 'sendMessage']


class RepeatGuardTests(unittest.TestCase):
    def test_first_alert_has_no_previous(self):
        self.assertIsNone(repeat_guard(None, '1', NOW.timestamp()))

    def test_small_further_drop_inside_cooldown_is_suppressed(self):
        prev = dict(at=(NOW - dt.timedelta(days=1)).isoformat(), low='1.00')
        self.assertEqual(repeat_guard(prev, '0.95', NOW.timestamp()), 'SUPPRESS')

    def test_ten_percent_drop_or_expired_cooldown_allows_repeat(self):
        prev = dict(at=(NOW - dt.timedelta(days=1)).isoformat(), low='1.00')
        self.assertEqual(repeat_guard(prev, '0.90', NOW.timestamp()), prev)
        old = dict(at=(NOW - dt.timedelta(days=REPEAT_COOLDOWN_DAYS)).isoformat(), low='1.00')
        self.assertEqual(repeat_guard(old, '0.99', NOW.timestamp()), old)

    def test_corrupt_or_naive_records_fail_closed(self):
        for bad in ({}, dict(at='nonsense', low='1'), dict(at=NOW.isoformat(), low='0'),
                    dict(at=NOW.replace(tzinfo=None).isoformat(), low='1'), dict(at=AT, low='abc')):
            self.assertEqual(repeat_guard(bad, '0.5', NOW.timestamp()), 'SUPPRESS')


class RepeatNotifyTests(unittest.TestCase):
    def test_falling_coin_with_new_lows_is_not_realerted_daily(self):
        state, log = {}, []
        self.assertEqual(notify([build('.99')], state, ENV, transport(log), now=NOW.timestamp())['delivered'], 1)
        second = notify([build('.97')], state, ENV, transport(log), now=NOW.timestamp())
        self.assertEqual(second['delivered'], 0)
        self.assertEqual(second['decisions'][0]['status'], 'REPEAT_COOLDOWN')
        self.assertEqual(len(sends(log)), 1)
        self.assertFalse(second['buy_authorized'])

    def test_repeat_after_cooldown_is_sent_and_labelled(self):
        state, log = {}, []
        notify([build('.99')], state, ENV, transport(log), now=NOW.timestamp())
        record = state['research_last_by_asset']['example']
        self.assertEqual(Decimal(record['low']), Decimal('.99'))
        record['at'] = (NOW - dt.timedelta(days=8)).isoformat()
        result = notify([build('.97')], state, ENV, transport(log), now=NOW.timestamp())
        self.assertEqual(result['delivered'], 1)
        text = sends(log)[-1][1]['text']
        self.assertTrue(text.startswith('🚨 <b>ALL-TIME LOW WATCH</b>'))
        self.assertIn('Repeat alert', text)
        self.assertEqual(Decimal(state['research_last_by_asset']['example']['low']), Decimal('.97'))

    def test_failed_delivery_does_not_start_cooldown(self):
        state = {}
        notify([build('.99')], state, ENV, transport([], wrong=True), now=NOW.timestamp())
        self.assertNotIn('research_last_by_asset', state)


if __name__ == '__main__':
    unittest.main()
