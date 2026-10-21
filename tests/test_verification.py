import datetime as dt
import unittest
from verification import collect, historical_entry, honeypot, holders, risk_plan, security, tokenomics
from crypto_oracle_scanner import decision_summary

TOKEN = '0x' + 'a' * 40

class VerificationTests(unittest.TestCase):
    def test_independent_simulation_requires_identity(self):
        raw = {'token': {'address': TOKEN}, 'simulationSuccess': True,
               'honeypotResult': {'isHoneypot': False},
               'simulationResult': {'buyTax': 0, 'sellTax': 0, 'transferTax': 0}}
        self.assertEqual(honeypot(raw, TOKEN)[0], 'LIMITED')
        self.assertEqual(honeypot(raw, '0xwrong')[0], 'UNKNOWN')
        raw['simulationSuccess'] = False
        self.assertEqual(honeypot(raw, TOKEN)[0], 'UNKNOWN')

    def test_honeypot_and_nonfinite_tax(self):
        raw = {'token': {'address': TOKEN}, 'simulationSuccess': True,
               'honeypotResult': {'isHoneypot': True}}
        self.assertEqual(honeypot(raw, TOKEN)[0], 'FAIL')
        raw['honeypotResult']['isHoneypot'] = False
        raw['simulationResult'] = dict(buyTax=0, sellTax='NaN', transferTax=0)
        self.assertEqual(honeypot(raw, TOKEN)[0], 'UNKNOWN')

    def test_unknown_is_not_security_clearance(self):
        self.assertEqual(security({})[0], 'UNKNOWN')
        self.assertEqual(security({'is_proxy': '1'})[0], 'FAIL')
        self.assertEqual(tokenomics({'total_supply': 100, 'is_mintable': '1'})[0], 'FAIL')
        self.assertEqual(tokenomics({'total_supply': 100, 'is_mintable': '0'})[0], 'UNKNOWN')

    def test_holder_data_does_not_prove_distribution(self):
        for rows in ([], [{'percent': '.01'}], [{'percent': 'nan'}], [{'percent': 2}]):
            self.assertEqual(holders({'holders': rows})[0], 'UNKNOWN')

    def test_provider_failures_and_unsupported_chain(self):
        def offline(url):
            raise OSError('offline')
        result = collect({'network': 'eth', 'token_address': TOKEN, 'address': 'pool'}, offline)
        self.assertTrue(all(x['status'] == 'UNKNOWN' for x in result.values()))
        result = collect({'network': 'solana', 'token_address': 'mint'}, offline)
        self.assertEqual(result['integration']['status'], 'UNKNOWN')

    def test_risk_includes_costs_and_total_loss_exposure(self):
        result = risk_plan(1000, 10, 9, .01, .005, 1000000)
        self.assertLessEqual(result['allocation_usd'], 100)
        self.assertLessEqual(result['planned_loss_usd'], 10)
        self.assertEqual(result['total_loss_exposure_usd'], result['allocation_usd'])
        for invalid in (float('nan'), True, -1):
            with self.assertRaises(ValueError):
                risk_plan(invalid, 10, 9, .01, .005, 1000000)

    def test_closed_candle_breakout_and_gaps(self):
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        start = int(now // 300) * 300 - 21 * 300
        rows = [[start + i * 300, 10, 11, 9, 10, 100] for i in range(21)]
        rows[-1][2:6] = [11.2, 9, 11.1, 200]
        raw = {'data': {'attributes': {'ohlcv_list': rows}}}
        self.assertEqual(historical_entry(raw, now)['status'], 'LIMITED')
        rows[3][0] += 1
        self.assertEqual(historical_entry(raw, now)['status'], 'UNKNOWN')

    def test_independent_adverse_report_vetoes(self):
        item = {'risk_category': 'RESEARCH CANDIDATE — LIMITED CHECKS',
                'verification': {'sellability': {'status': 'FAIL'}}}
        decision, reason = decision_summary(item)
        self.assertEqual(decision, 'WAIT AND VERIFY')
        self.assertIn('failed', reason)

if __name__ == '__main__':
    unittest.main()
