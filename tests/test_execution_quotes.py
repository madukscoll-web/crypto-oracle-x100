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
        self.assertEqual(calls[1]['sellAmount'], '198')
        self.assertEqual(calls[1]['buyToken'], A)
        self.assertNotIn(ENV['ZEROX_API_KEY'], str(result))

    def test_missing_config_does_not_call_provider(self):
        def forbidden(*args):
            self.fail('Unexpected network call')
        self.assertEqual(collect({}, {}, forbidden)['status'], 'UNSUPPORTED')

    def test_malformed_or_failed_quote_never_verifies(self):
        for raw in ({}, {'liquidityAvailable': False}, {'liquidityAvailable': True}):
            self.assertEqual(collect(dict(network='eth', token_address=B), ENV,
                                     lambda *args: raw)['status'], 'UNKNOWN')

class StrictQuoteTests(unittest.TestCase):
    def raw(self):
        return dict(liquidityAvailable=True,sellToken=A,buyToken=B,sellAmount='100',buyAmount='200',minBuyAmount='198',
                    transaction=dict(to=T,data='0x1234',gas='100',gasPrice='2',value='0'),issues=dict(simulationIncomplete=False))
    def test_fractional_boolean_and_excess_slippage_rejected(self):
        from execution_quotes import validate
        for field,value in (('sellAmount',True),('sellAmount','100.5'),('minBuyAmount','197'),('buyAmount','NaN')):
            raw=self.raw();raw[field]=value
            with self.assertRaises(ValueError):validate(raw,A,B,100)
    def test_reverse_failure_preserves_first_quote_for_diagnostics(self):
        calls=[]
        def provider(*args):
            calls.append(1)
            if len(calls)==2:raise OSError('offline')
            return self.raw()
        result=collect(dict(network='eth',token_address=B),ENV,provider)
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(len(result['raw']),1)
