"""Provider wire fixtures; no network calls or real token safety claims."""
import datetime as dt
import io
import json
import os
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner
import telegram_notify as telegram
import oracle_http

TOKEN = '0x' + '1'*40
POOL = '0x' + '2'*40
QUOTE = '0x' + '3'*40


def identity(pool=POOL):
    return dict(data=dict(attributes=dict(address=pool, base_token_price_usd='1'),
                         relationships=dict(base_token={'data': {'id': 'base_token'}},
                                            quote_token={'data': {'id': 'quote_token'}})),
                included=[dict(type='token', id='base_token', attributes=dict(address=TOKEN, symbol='FIXTURE')),
                          dict(type='token', id='quote_token', attributes=dict(address=QUOTE, symbol='QUOTE'))])


class AdapterIntegrationTests(unittest.TestCase):
    def item(self):
        return dict(network='base', address=POOL, key='base:'+POOL)

    def test_wrong_pool_identity_never_queries_security(self):
        value = self.item()
        with patch.object(scanner, 'fetch_json', return_value=identity('wrong')) as fetch, patch.object(scanner.time, 'sleep'):
            scanner.enrich(value)
        self.assertEqual(value['token_address'], 'UNVERIFIED')
        self.assertEqual(fetch.call_count, 1)

    def test_successful_security_response_preserves_findings_and_digest(self):
        value = self.item()
        fields = dict(is_honeypot='1', total_supply='100')
        with patch.object(scanner, 'fetch_json', side_effect=[identity(), {'data': []}, {'code': 1, 'result': {TOKEN: fields}}]), patch.object(scanner.time, 'sleep'):
            scanner.enrich(value)
        self.assertEqual(value['risk_category'], 'AVOID / HIGH CONCERN')
        self.assertEqual(value['quote_token_address'], QUOTE)
        self.assertEqual(value['security_provider_evidence']['values']['total_supply'], '100')
        self.assertEqual(len(value['security_provider_evidence']['response_sha256']), 64)
        self.assertEqual(scanner.decision_summary(value)[0], 'DISCARD')

    def test_error_response_cannot_supply_fake_security(self):
        value = self.item()
        with patch.object(scanner, 'fetch_json', side_effect=[identity(), {'data': []}, {'code': 0, 'result': {TOKEN: {'is_honeypot': '0'}}}]), patch.object(scanner.time, 'sleep'):
            scanner.enrich(value)
        self.assertEqual(value['risk_category'], 'WAIT / VERIFY')
        self.assertNotIn('security_provider_evidence', value)

    def test_telegram_requires_positive_integer_receipt(self):
        for fake in (None, False, 0, -1, '123', []):
            body = io.StringIO(json.dumps(dict(ok=True, result={'message_id': fake})))
            with patch.dict(os.environ, TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='fixture'), patch('telegram_notify.urllib.request.urlopen', return_value=body):
                with self.assertRaises(telegram.NotificationError):
                    telegram.send_message('fixture')

    def test_telegram_unicode_limit_preserves_valid_prefix(self):
        value = telegram.bounded_text('DECISION: WAIT\n' + '🔎'*4096)
        self.assertLessEqual(len(value.encode('utf-16-le'))//2, 4096)
        self.assertTrue(value.startswith('DECISION: WAIT'))
        value.encode('utf-8')

    def test_optional_http_no_retry_budget(self):
        oracle_http._LAST_REQUEST.clear()
        with patch('oracle_http.urllib.request.urlopen', side_effect=TimeoutError) as fetch, patch('oracle_http.time.sleep'):
            with self.assertRaises(TimeoutError):
                oracle_http.get_json('https://fixture.invalid', retries=0, timeout=5)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.kwargs['timeout'], 5)
