"""Offline regression coverage for transport, reporting and state safety."""
import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import crypto_oracle_scanner as scanner
import market_corroboration
import oracle_http
import telegram_notify as telegram


def response(payload):
    return io.StringIO(json.dumps(payload))


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "private-test-token", "TELEGRAM_CHAT_ID": "private-test-chat"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_delivery_requires_message_id(self):
        with patch('telegram_notify.urllib.request.urlopen', return_value=response({"ok": True, "result": {"message_id": 1}})) as send:
            self.assertTrue(telegram.send_message("test"))
            self.assertEqual(send.call_args.kwargs['timeout'], 20)
            self.assertEqual(send.call_args.args[0].method, 'POST')

    def test_unconfirmed_result_fails(self):
        with patch('telegram_notify.urllib.request.urlopen', return_value=response({"ok": True, "result": {}})):
            with self.assertRaises(telegram.NotificationError):
                telegram.send_message('test')

    def test_missing_secret_fails_without_request(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}), patch('telegram_notify.urllib.request.urlopen') as send:
            with self.assertRaises(telegram.NotificationError):
                telegram.send_message('test')
            send.assert_not_called()

    def test_429_respects_retry_after(self):
        limited = urllib.error.HTTPError('secret-url', 429, 'limited', {'Retry-After': '3'}, None)
        with patch('telegram_notify.urllib.request.urlopen', side_effect=[limited, response({"ok": True, "result": {"message_id": 2}})]), patch('telegram_notify.time.sleep') as sleep:
            self.assertTrue(telegram.send_message('test'))
            sleep.assert_called_once_with(3)

    def test_errors_and_logs_never_contain_credentials(self):
        capture = io.StringIO()
        error = urllib.error.URLError('https://api.telegram.org/botprivate-test-token/sendMessage private-test-chat')
        with patch('telegram_notify.urllib.request.urlopen', side_effect=error), patch('telegram_notify.time.sleep'), contextlib.redirect_stdout(capture):
            with self.assertRaises(telegram.NotificationError) as raised:
                telegram.send_message('test')
        for secret in ('private-test-token', 'private-test-chat'):
            self.assertNotIn(secret, str(raised.exception) + capture.getvalue())

    def test_permanent_403_not_retried(self):
        error = urllib.error.HTTPError('secret-url', 403, 'forbidden', {}, None)
        with patch('telegram_notify.urllib.request.urlopen', side_effect=error) as send:
            with self.assertRaisesRegex(telegram.NotificationError, 'HTTP 403'):
                telegram.send_message('test')
            self.assertEqual(send.call_count, 1)

    def test_failure_notification_links_diagnostic_stages(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_RUN_ID': '123', 'FAILED_STAGES': 'state=failure'}):
            message = telegram.workflow_message('failure')
        self.assertIn('state=failure', message)
        self.assertIn('/owner/repo/actions/runs/123', message)


class HttpTests(unittest.TestCase):
    def setUp(self):
        oracle_http._LAST_REQUEST.clear()

    def test_transient_503_then_success(self):
        error = urllib.error.HTTPError('https://example.test', 503, 'down', {}, None)
        with patch('oracle_http.urllib.request.urlopen', side_effect=[error, response({'data': []})]), patch('oracle_http.time.sleep'):
            self.assertEqual(oracle_http.get_json('https://example.test'), {'data': []})

    def test_timeout_retries_are_bounded(self):
        with patch('oracle_http.urllib.request.urlopen', side_effect=TimeoutError) as send, patch('oracle_http.time.sleep'):
            with self.assertRaises(TimeoutError):
                oracle_http.get_json('https://example.test')
            self.assertEqual(send.call_count, 3)

    def test_permanent_404_not_retried(self):
        error = urllib.error.HTTPError('https://example.test', 404, 'missing', {}, None)
        with patch('oracle_http.urllib.request.urlopen', side_effect=error) as send:
            with self.assertRaises(urllib.error.HTTPError):
                oracle_http.get_json('https://example.test')
            self.assertEqual(send.call_count, 1)

    def test_non_object_payload_rejected(self):
        with patch('oracle_http.urllib.request.urlopen', return_value=response([])):
            with self.assertRaises(ValueError):
                oracle_http.get_json('https://example.test')

    def test_retry_delay_is_finite_and_bounded(self):
        self.assertEqual(oracle_http.retry_delay({'Retry-After': '9999'}, 0), 60)
        self.assertEqual(oracle_http.retry_delay({'Retry-After': 'NaN'}, 0), 12)

    def test_requests_are_paced_per_host(self):
        oracle_http._LAST_REQUEST['example.test'] = 100
        with patch('oracle_http.time.monotonic', return_value=100), patch('oracle_http.time.sleep') as sleep, patch('oracle_http.urllib.request.urlopen', return_value=response({})):
            oracle_http.get_json('https://example.test')
            sleep.assert_called_once_with(oracle_http.MIN_INTERVAL)


class ScanOperationTests(unittest.TestCase):
    def setUp(self):
        optional = patch.object(scanner.hourly_evidence, "collect_safely")
        optional.start()
        self.addCleanup(optional.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        previous = os.getcwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, previous)
        for obj, name, value in ((scanner, 'NETWORKS', ('base',)), (scanner, 'PAGES_PER_NETWORK', 1),
                                 (scanner, 'STATE_FILE', pathlib.Path('reported_pools.json')),
                                 (scanner, 'WATCH_STATE_FILE', pathlib.Path('watchlist_state.json'))):
            handle = patch.object(obj, name, value)
            handle.start()
            self.addCleanup(handle.stop)
        handle = patch('crypto_oracle_scanner.time.sleep')
        handle.start()
        self.addCleanup(handle.stop)

    def test_no_candidates_still_produces_completion_summary(self):
        with patch.object(scanner, 'fetch_json', return_value={'data': []}), patch.object(scanner, 'send_telegram') as send:
            report = scanner.main()
        self.assertEqual(report['candidates'], 0)
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(report['successful_feeds'], 2)
        self.assertIn('No qualifying tokens found', telegram.workflow_message('completion'))
        send.assert_not_called()

    def test_malformed_rows_are_counted_without_losing_remaining_observations(self):
        with patch.object(scanner, 'fetch_json', return_value={'data': [None, {'attributes': {}}]}):
            report = scanner.main()
        counts = report['filter_audit']['discovery_observations']
        self.assertEqual(report['observations'], 4)
        self.assertEqual(report['filter_audit']['discovery_observation_count'], 4)
        self.assertEqual(counts, {'malformed_pool_observation': 2, 'missing_pool_creation_time': 2})

    def test_provider_outage_is_failure_not_empty_success(self):
        with patch.object(scanner, 'fetch_json', side_effect=TimeoutError):
            with self.assertRaises(SystemExit):
                scanner.main()
        self.assertEqual(json.loads(pathlib.Path('scan_summary.json').read_text())['status'], 'failed')
        with self.assertRaises(telegram.NotificationError):
            telegram.workflow_message('completion')

    def test_malformed_discovery_payload_is_failure(self):
        with patch.object(scanner, 'fetch_json', return_value={'error': 'provider down'}):
            with self.assertRaises(SystemExit):
                scanner.main()

    def test_corrupt_alert_state_fails_closed(self):
        pathlib.Path('reported_pools.json').write_text('{invalid')
        with self.assertRaises(RuntimeError):
            scanner.load_state()

    def test_atomic_alert_state_round_trip(self):
        scanner.save_state({'base:one', 'solana:two'})
        self.assertEqual(scanner.load_state(), {'base:one', 'solana:two'})
        self.assertFalse(pathlib.Path('reported_pools.json.tmp').exists())

    def test_failed_priority_alert_preserves_transition_for_retry(self):
        from test_signals import sample
        item = sample(pool_class='NEW POOL')
        # A previously delivered token is deliberately deduplicated; test
        # delivery failure retry for an eligible token not yet delivered.
        scanner.save_state(set())
        original = {'setup': 'WAIT', 'observed_at': '2026-01-01', 'network': 'base', 'pool_address': '0xpool'}
        scanner.save_watchlist({item['key']: original})
        with patch.object(scanner, 'fetch_json', side_effect=[{'data': []}, {'data': []}, {'data': {}}]), patch.object(scanner, 'inspect', return_value=item), patch.object(scanner, 'enrich'), patch.object(scanner.market_corroboration, 'check', return_value={'status': 'UNKNOWN'}), patch.object(scanner, 'send_telegram', side_effect=telegram.NotificationError('test failure')), patch.object(scanner, 'telegram_eligible', return_value=True):
            with self.assertRaises(SystemExit):
                scanner.main()
        self.assertEqual(scanner.load_watchlist()[item['key']], original)

    def test_revisited_signal_absent_from_discovery_reaches_forward_ledger(self):
        import datetime as dt
        import forward_ledger
        from test_signals import sample
        token='0x'+'a'*40;pool='0x'+'b'*40;pool_key='base:'+pool
        stamp=dt.datetime.now(dt.timezone.utc)
        item=sample(key=pool_key,address=pool,token_address=token,pool_class='EXISTING POOL',
                    observed_at=stamp.isoformat(),base_token_price_usd=1.25)
        scanner.save_watchlist({pool_key:{'network':'base','pool_address':pool,'observed_at':'2020-01-01','setup':'WAIT'}})
        scanner.signal_tracker.save({pool_key:[{'at':(stamp-dt.timedelta(days=1)).isoformat(),
            'price_usd':1,'token_address':token,'source':'Fixture indicative history'}]})
        with patch.object(scanner,'fetch_json',side_effect=[{'data':[]},{'data':[]},{'data':{'id':'tracked'}}]), \
             patch.object(scanner,'inspect',return_value=item), patch.object(scanner,'enrich'), \
             patch.object(scanner.fundamental_evidence,'collect',return_value={}), \
             patch.object(scanner.evidence_checks,'review',return_value={}), \
             patch.object(scanner.market_corroboration,'check',return_value={'status':'UNKNOWN'}), \
             patch.object(scanner,'entry_setup',return_value=('MOMENTUM WATCH','Fixture')), \
             patch.object(scanner,'price_evidence',return_value=(True,'Fixture')), \
             patch.object(scanner,'watchlist_transition',return_value=None), \
             patch.object(scanner.gate_spot_candidates,'hourly',return_value={'errors':[],'candidates':[]}):
            report=scanner.main()
        self.assertEqual(report['candidates'],0)
        events=forward_ledger.read()
        self.assertEqual([r['event']['kind'] for r in events],['SIGNAL','PRICE'])
        self.assertEqual(events[-1]['event']['price_usd'],1.25)

    def test_nonfinite_number_rejected(self):
        for value in ('NaN', 'Infinity', '-Infinity'):
            self.assertEqual(scanner.number(value), 0)

    def test_malformed_corroboration_remains_unknown(self):
        result = market_corroboration.check({'network': 'base', 'address': '0xpool'}, lambda _: {'pairs': [None]})
        self.assertEqual(result['status'], 'UNKNOWN')

