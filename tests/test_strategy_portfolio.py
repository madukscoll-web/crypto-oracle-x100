import unittest
from unittest.mock import patch
import strategy_lab as lab
import strategy_portfolio as portfolio


def candles(n=300):
    return [dict(timestamp=1700006400+i*86400,open=100.,high=101.,low=99.,
                 close=100.,volume=1_000_000.,closed=True) for i in range(n)]


class PortfolioTests(unittest.TestCase):
    def test_capital_is_counted_once(self):
        result=portfolio.replay({p:candles() for p in ('A','B','C','D')},'range_breakout',lab.policy())
        self.assertAlmostEqual(result['final_marked_equity_usdt'],1000.)
        self.assertEqual(result['closed_trades'],0)
        self.assertFalse(result['strategy_validated'])

    def test_global_pending_and_open_limit(self):
        def plan(pair,strategy,history,p):
            return dict(entry=100.,stop=95.,target=110.,signal_at=history[-1]['timestamp'])
        with patch('strategy_lab.plan',side_effect=plan):
            result=portfolio.replay({p:candles() for p in ('A','B','C','D','E')},'range_breakout',lab.policy())
        self.assertLessEqual(result['maximum_occupied_slots'],3)
        self.assertGreater(result['deferred_signals_due_to_slots'],0)
        self.assertLess(result['final_marked_equity_usdt'],1000.)
        self.assertTrue(all(t['quantity']*t['entry']<=20 for t in result['trades']))

    def test_no_synthetic_common_history(self):
        self.assertEqual(portfolio.replay({'A':candles(100)},'range_breakout',lab.policy())['status'],'INSUFFICIENT_COMMON_HISTORY')
        c=candles();c.pop(200)
        with self.assertRaises(ValueError):portfolio.replay({'A':c,'B':candles()},'range_breakout',lab.policy())
