"""Exercise partial provider refreshes through the production scanner and alerts."""
import contextlib
import copy
import datetime as dt
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import crypto_oracle_scanner as scanner
import telegram_notify as telegram

TOKEN = '0x' + '1' * 40
POOL = '0x' + '2' * 40


def pool():
    return dict(id='base_' + POOL, attributes=dict(
        address=POOL, name='Offline regression fixture',
        pool_created_at=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat(),
        base_token_price_usd='0.04', reserve_in_usd='350000', volume_usd={'h24': '800000'},
        transactions={'h1': {'buys': 60, 'sells': 40}},
        price_change_percentage={'h1': '6', 'h24': '18'}),
        relationships={'base_token': {'data': {'id': 'base_' + TOKEN}}})


def refresh():
    return dict(data=pool(), included=[dict(type='token', id='base_' + TOKEN,
        attributes=dict(address=TOKEN, symbol='FIXTURE'))])


class MissingMarketTests(unittest.TestCase):
    def setUp(self):
        optional = patch.object(scanner.hourly_evidence, "collect_safely")
        optional.start()
        self.addCleanup(optional.stop)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        cwd = os.getcwd()
        os.chdir(self.folder.name)
        self.addCleanup(os.chdir, cwd)

    def enrich(self, payload):
        item = scanner.inspect(pool(), 'base')
        def fetch(url):
            if '?include=' in url:
                return copy.deepcopy(payload)
            raise OSError('Offline optional-provider fixture')
        with patch.object(scanner.time, 'sleep'):
            scanner.enrich(item, fetch=fetch, delay=0)
        return item

    def assert_wait(self, item):
        self.assertEqual(scanner.setup_assessment(item)[0], 'WAIT')
        self.assertEqual(scanner.entry_setup(item)[0], 'INSUFFICIENT DATA')
        self.assertEqual(scanner.decision_summary(item)[0], 'WAIT AND VERIFY')
        self.assertFalse(scanner.evidence_audit.audit(item)['trade_ready'])

    def test_original_missing_volume_refresh_reaches_classifiers_and_telegram(self):
        payload = refresh()
        del payload['data']['attributes']['volume_usd']
        item = self.enrich(payload)
        self.assertIsNone(item['volume'])
        self.assert_wait(item)
        with patch.dict(os.environ, TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='fixture'), patch(
                'telegram_notify.urllib.request.urlopen', return_value=io.StringIO(
                    json.dumps(dict(ok=True, result={'message_id': 1})))) as send:
            self.assertTrue(scanner.send_telegram(item))
        text = parse_qs(send.call_args.args[0].data.decode())['text'][0]
        self.assertIn('24h volume: $UNKNOWN', text)
        self.assertIn('FINAL DECISION: WAIT AND VERIFY', text)
        self.assertNotIn('FINAL DECISION: BUY', text)

    def test_unavailable_and_invalid_refresh_fields_remain_unknown(self):
        for path in (('reserve_in_usd',), ('volume_usd', 'h24'),
                     ('transactions', 'h1', 'buys'), ('transactions', 'h1', 'sells'),
                     ('price_change_percentage', 'h1'), ('price_change_percentage', 'h24')):
            for value in (None, 'bad', 'NaN', 'Infinity', True):
                with self.subTest(path=path, value=value):
                    payload = refresh()
                    target = payload['data']['attributes']
                    for part in path[:-1]:
                        target = target[part]
                    target[path[-1]] = value
                    item = self.enrich(payload)
                    self.assert_wait(item)

    def test_all_unknown_market_metrics_can_be_notified_without_buy(self):
        item = self.enrich(refresh())
        for field in ('liquidity', 'volume', 'buys', 'sells', 'trades', 'buy_share'):
            item[field] = None
        with patch.dict(os.environ, TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='fixture'), patch(
                'telegram_notify.urllib.request.urlopen', return_value=io.StringIO(
                    json.dumps(dict(ok=True, result={'message_id': 1})))) as send:
            self.assertTrue(scanner.send_telegram(item))
        text = parse_qs(send.call_args.args[0].data.decode())['text'][0]
        for label in ('Liquidity: $UNKNOWN', '24h volume: $UNKNOWN', '1h trades: UNKNOWN', '1h buy share: UNKNOWN'):
            self.assertIn(label, text)
        self.assertIn('FINAL DECISION: WAIT AND VERIFY', text)
        for field in ('buys', 'sells'):
            for value in (-1, 1.5):
                with self.subTest(field=field, value=value):
                    payload = refresh()
                    payload['data']['attributes']['transactions']['h1'][field] = value
                    item = self.enrich(payload)
                    self.assertIsNone(item['trades'])
                    self.assertIsNone(item['buy_share'])
                    self.assert_wait(item)

    def test_failed_refresh_cannot_reuse_discovery_market_values(self):
        for payload in ({}, {'data': {'attributes': {'address': 'wrong-pool'}}}):
            item = self.enrich(payload)
            for field in ('liquidity', 'volume', 'trades', 'buy_share', 'change_h1', 'change_h24'):
                self.assertIsNone(item[field])
            self.assertEqual(item['base_token_price_usd'], 0)
            self.assertEqual(scanner.setup_assessment(item)[0], 'WAIT')
            self.assertEqual(scanner.decision_summary(item)[0], 'WAIT AND VERIFY')

    def test_zero_observations_and_negative_price_changes_are_not_missing(self):
        payload = refresh()
        payload['data']['attributes'].update(volume_usd={'h24': '0'},
            transactions={'h1': {'buys': 0, 'sells': 10}},
            price_change_percentage={'h1': '-2', 'h24': '-5'})
        item = self.enrich(payload)
        self.assertEqual(item['volume'], 0)
        self.assertEqual(item['buy_share'], 0)
        self.assertEqual(item['change_h1'], -2)
        self.assertEqual(scanner.missing_market_fields(item), [])
        self.assertEqual(scanner.entry_setup(item)[0], 'WAIT')

    def test_missing_data_never_overrides_security_rejection(self):
        item = scanner.inspect(pool(), 'base')
        item.update(volume=None, risk_category='AVOID / HIGH CONCERN', risk_reasons=['Honeypot'])
        self.assertEqual(scanner.decision_summary(item)[0], 'DISCARD')
        self.assertEqual(scanner.setup_assessment(item)[0], 'REJECT')

    def test_production_scan_completes_and_saves_state_after_partial_refresh(self):
        payload = refresh()
        del payload['data']['attributes']['volume_usd']
        def fetch(url):
            if '?include=' in url:
                return copy.deepcopy(payload)
            if '/new_pools?' in url:
                return {'data': [pool()]}
            if '/trending_pools?' in url or '/tokens/' in url:
                return {'data': []}
            return {'code': 0}
        def collected(collector, item):
            item['verification'] = {'sellability': {'status': 'LIMITED', 'reason': 'Fixture simulation'}}
            item['gate_spot'] = {'status': 'UNKNOWN', 'reason': 'Fixture absent listing'}
        with patch.object(scanner.hourly_evidence, 'collect_safely', side_effect=collected), patch.object(scanner, 'NETWORKS', ('base',)), patch.object(scanner, 'PAGES_PER_NETWORK', 1), patch.object(
                scanner, 'fetch_json', side_effect=fetch), patch.object(scanner.time, 'sleep'), patch.object(
                scanner.fundamental_evidence, 'collect', return_value={}), patch.object(
                scanner.market_corroboration, 'check', return_value={'status': 'UNKNOWN'}), patch.dict(
                os.environ, TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='fixture'), patch(
                'telegram_notify.urllib.request.urlopen', return_value=io.StringIO(
                    json.dumps(dict(ok=True, result={'message_id': 1})))):
            report = scanner.main()
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['alerts_delivered'], 0)
        self.assertEqual(report['gate_paper_candidates'], 0)
        gate_report = json.loads(pathlib.Path('gate_candidate_report.json').read_text())
        self.assertIn('No documented', gate_report['errors'][0])
        evidence = json.loads(pathlib.Path('evidence_report.json').read_text())[0]
        self.assertEqual(evidence['verification']['sellability']['status'], 'LIMITED')
        self.assertEqual(evidence['gate_spot']['status'], 'UNKNOWN')
        self.assertNotIn('base:' + POOL, scanner.load_state())
        self.assertEqual(json.loads(pathlib.Path('scan_summary.json').read_text())['status'], 'completed')

    def test_unexpected_scanner_error_is_nonzero_and_failure_alert_is_deliverable(self):
        pathlib.Path('scan_summary.json').write_text('{"status":"completed"}')
        output = io.StringIO()
        with patch.object(scanner, 'main', side_effect=TypeError('secret-token secret-chat')), contextlib.redirect_stdout(output):
            self.assertEqual(scanner.cli(), 1)
        report = json.loads(pathlib.Path('scan_summary.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertIn('TypeError', output.getvalue())
        self.assertNotIn('secret-token', output.getvalue() + json.dumps(report))
        with self.assertRaises(telegram.NotificationError):
            telegram.workflow_message('completion')
        with patch.dict(os.environ, TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='fixture',
                        GITHUB_REPOSITORY='owner/repo', GITHUB_RUN_ID='123', FAILED_STAGES='scan=failure'), patch(
                'telegram_notify.urllib.request.urlopen', return_value=io.StringIO(
                    json.dumps(dict(ok=True, result={'message_id': 2})))) as send:
            self.assertTrue(telegram.send_message(telegram.workflow_message('failure')))
        text = parse_qs(send.call_args.args[0].data.decode())['text'][0]
        self.assertIn('workflow FAILED', text)
        self.assertIn('scan=failure', text)

    def test_failure_to_write_diagnostics_still_exits_nonzero(self):
        output = io.StringIO()
        with patch.object(scanner, 'main', side_effect=TypeError('private detail')), patch.object(
                pathlib.Path, 'write_text', side_effect=OSError('private filesystem detail')), contextlib.redirect_stdout(output):
            self.assertEqual(scanner.cli(), 1)
        self.assertIn('Could not write failed scan summary', output.getvalue())
        self.assertNotIn('private', output.getvalue())


if __name__ == '__main__':
    unittest.main()

