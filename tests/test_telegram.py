import io
import json
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner

class TelegramTests(unittest.TestCase):
    def item(self):
        item = {key: 'UNVERIFIED' for key in (
            'network', 'name', 'pool_class', 'token_age', 'token_symbol',
            'token_address', 'token_identity_status', 'previous_pools',
            'contract_security', 'holder_concentration', 'liquidity_lock',
            'security_details', 'security_fields', 'holder_details',
            'security_source', 'return_probabilities', 'source', 'observed_at', 'url')}
        item.update(flags=[], score=0, age_hours=0, liquidity=0, volume=0,
                    trades=0, buys=0, sells=0, buy_share=0,
                    risk_category='WAIT / VERIFY', risk_reasons=['Unavailable'])
        return item

    def test_missing_credentials_do_not_send(self):
        with patch.dict(scanner.os.environ, {}, clear=True), patch.object(scanner.urllib.request, 'urlopen') as send:
            with self.assertRaises(RuntimeError):
                scanner.send_telegram(self.item())
            send.assert_not_called()

    def test_delivery_requires_api_confirmation(self):
        for ok in (True, False):
            body = io.BytesIO(json.dumps({'ok': ok, 'result': {'message_id': 123, 'chat': {'id': -123}} if ok else None}).encode())
            with patch.dict(scanner.os.environ, dict(TELEGRAM_BOT_TOKEN='fixture', TELEGRAM_CHAT_ID='-123')), patch.object(scanner.urllib.request, 'urlopen', return_value=body) as send:
                if ok:
                    scanner.send_telegram(self.item())
                    request = send.call_args.args[0]
                    from urllib.parse import parse_qs
                    text = parse_qs(request.data.decode())['text'][0]
                    self.assertIn('FINAL DECISION: WAIT AND VERIFY', text[:1000])
                    self.assertLessEqual(len(text), 4096)
                else:
                    with self.assertRaises(RuntimeError):
                        scanner.send_telegram(self.item())

