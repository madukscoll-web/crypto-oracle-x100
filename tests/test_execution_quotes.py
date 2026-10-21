import unittest
from execution_quotes import collect

A, B, T = ('0x' + x * 40 for x in ('a', 'b', 'c'))
ENV = dict(ZEROX_API_KEY='offline-fixture', ORACLE_TAKER_ADDRESS=T,
           ORACLE_FUNDING_TOKEN=A, ORACLE_ORDER_BASE_UNITS='100')

class QuoteTests(unittest.TestCase):
    def test_two_legs_bind_amounts_and_identity(self):
        calls = []
        def transport(url, key):
            from urllib.parse import urlparse, parse_qs
            q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
            calls.append(q)
            return dict(liquidityAvailable=True, sellToken=q['sellToken'], buyToken=q['buyToken'],
                        sellAmount=q['sellAmount'], buyAmount='200', minBuyAmount='198',
                        transaction=dict(to=T, data='0x1234', gas='100', gasPrice='2', value='0'),
                        issues=dict(simulationIncomplete=False))
        result = collect(dict(network='eth', token_address=B), ENV, transport)
        self.assertEqual(result['status'], 'LIMITED')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]['sellAmount'], '200')
        self.assertEqual(calls[1]['buyToken'], A)
        self.assertNotIn(ENV['ZEROX_API_KEY'], str(result))

    def test_missing_config_does_not_call_provider(self):
        def forbidden(*args):
            self.fail('Unexpected network call')
        self.assertEqual(collect({}, {}, forbidden)['status'], 'UNKNOWN')

    def test_malformed_or_failed_quote_never_verifies(self):
        for raw in ({}, {'liquidityAvailable': False}, {'liquidityAvailable': True}):
            self.assertEqual(collect(dict(network='eth', token_address=B), ENV,
                                     lambda *args: raw)['status'], 'UNKNOWN')
