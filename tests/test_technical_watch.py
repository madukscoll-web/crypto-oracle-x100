import copy
import datetime as dt
import json
import pathlib
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs

from altcoin_reversal_cli import run
from altcoin_reversal_research import analyze
from asset_identity import key
import technical_watch as alerts

NOW = 1800000000


def fixture(pairs=('BCH_USDT',), now=NOW, adverse=False, thin=False):
    prices = [150-i for i in range(45)] + [120-2*i for i in range(20)] + [80+.65*i for i in range(35)]
    def fetch(url):
        endpoint = urlsplit(url)
        args = parse_qs(endpoint.query)
        if endpoint.path == '/api/v4/spot/currencies':
            return [dict(currency=pair[:-5], delisted=False, trade_disabled=False,
                         chains=([{'name':'ETH','addr':'0x'+'a'*40}] if adverse else [])) for pair in pairs]
        if '/spot/currency_pairs/' in endpoint.path:
            pair = endpoint.path.rsplit('/', 1)[-1]
            return dict(id=pair, base=pair[:-5], quote='USDT', type='normal',
                        trade_status='tradable', st_tag=False, buy_start=1, sell_start=1)
        if endpoint.path.endswith('/spot/candlesticks'):
            period = 604800 if args['interval'] == ['7d'] else 86400
            return [[str(now-(100-i)*period), str(1600 if i==99 else 1000), str(p),
                     str(p+1), str(p-1), str(p), '10'] for i,p in enumerate(prices)]
        if endpoint.path.endswith('/spot/order_book'):
            return dict(current=int(now*1000), update=int(now*1000),
                        asks=[['102.2','0.001' if thin else '1000']], bids=[['102.1','1000']])
        if endpoint.hostname == 'api.gopluslabs.io':
            return {'code':1,'result':{'0x'+'a'*40:{'is_honeypot':'1'}}}
        raise AssertionError('Unexpected source '+url)
    report = run(pairs, fetch=fetch, now=now)
    for row in report['results']:
        row['interval'] = '1d'
        for source in row['provider_evidence']:
            source['retrieved_at'] = dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat()
    return report, fetch


def state():
    return {'version':1,'delivered':{},'daily_counts':{}}


class TechnicalWatchTests(unittest.TestCase):
    def deliver(self, report, fetch, old=None, sender=None, now=NOW, negatives=None):
        self.saved = []
        return alerts.deliver(report, old or state(), fetch, sender or (lambda _: True),
                              lambda s:self.saved.append(copy.deepcopy(s)),
                              now=lambda:now, negatives=set() if negatives is None else negatives)

    def test_valid_research_delivers_with_prominent_unknowns_never_buy(self):
        report, fetch = fixture()
        sent = []
        def sender(text):
            sent.append(text)
            return True
        updated, summary = self.deliver(report, fetch, sender=sender)
        self.assertEqual(summary['delivered'], 1)
        self.assertIn('SECURITY / FUNDAMENTALS NOT FULLY VERIFIED', sent[0])
        self.assertIn('NOT APPROVED FOR PURCHASE', sent[0])
        self.assertIn('Invalidation reference:', sent[0])
        self.assertIn('Trigger-to-invalidation distance:', sent[0])
        self.assertIn('Target/risk-reward: UNKNOWN', sent[0])
        self.assertIn('Sources:', sent[0])
        self.assertFalse(summary['buy_authorized'])
        self.assertEqual(self.saved[-1], updated)

    def test_replayed_bounded_paper_plan_is_explicitly_experimental(self):
        report, fetch = fixture()
        for source in report['results'][0]['provider_evidence']:
            if '/spot/candlesticks?' in source['url']:
                for candle in source['raw']:
                    for i in (2,3,4,5):
                        candle[i] = str(100+(float(candle[i])-100)*.3)
        sent=[]
        _, summary=self.deliver(report,fetch,sender=lambda text:sent.append(text) or True)
        self.assertEqual(summary['delivered'],1)
        self.assertIn('EXPERIMENTAL PAPER PLAN',sent[0])
        self.assertIn('Not validated, executable, or approved',sent[0])
        self.assertIn('Entry expires after 3 bars',sent[0])
        self.assertLessEqual(len(sent[0].encode('utf-16-le'))//2,3900)

    def test_no_repeat_on_later_closed_candle_or_next_day_without_material_change(self):
        report, fetch = fixture()
        old, _ = self.deliver(report, fetch)
        report, fetch = fixture(now=NOW+86401)
        _, summary = self.deliver(report, fetch, old, now=NOW+86401)
        self.assertEqual(summary['delivered'], 0)
        self.assertEqual(summary['suppressed']['no_material_change'], 1)

    def test_unconfirmed_receipt_does_not_advance_state(self):
        report, fetch = fixture()
        old, summary = self.deliver(report, fetch, sender=lambda _: None)
        self.assertEqual(summary['failed'], 1)
        self.assertEqual(old, state())
        self.assertFalse(self.saved)

    def test_send_failure_does_not_hide_prior_confirmed_delivery(self):
        report, fetch = fixture(('BCH_USDT','BNB_USDT'))
        sent = []
        def sender(text):
            sent.append(text)
            if len(sent)==2:
                raise OSError('test transport failure')
            return True
        updated, summary = self.deliver(report, fetch, sender=sender)
        self.assertEqual(summary['delivered'], 1)
        self.assertEqual(summary['failed'], 1)
        self.assertEqual(list(updated['delivered']), ['BCH_USDT'])

    def test_unknown_early_token_is_outside_scope(self):
        report, fetch = fixture(('BEAT_USDT',))
        _, summary = self.deliver(report, fetch)
        self.assertEqual(summary['delivered'], 0)

    def test_known_adverse_contract_blocks_even_if_chart_qualifies(self):
        report, fetch = fixture(adverse=True)
        _, summary = self.deliver(report, fetch)
        self.assertEqual(summary['delivered'], 0)
        self.assertIn('Adverse contract capability/sellability finding', summary['suppressed'])

    def test_retained_negative_blocks_before_new_clear_or_unknown_screen(self):
        report, fetch = fixture(adverse=True)
        _, summary = self.deliver(report, fetch, negatives={key('eth','0x'+'a'*40)})
        self.assertIn('Retained exact-contract adverse evidence', summary['suppressed'])

    def test_wide_stale_crossed_or_thin_books_are_silent(self):
        report, fetch = fixture(thin=True)
        _, summary = self.deliver(report, fetch)
        self.assertEqual(summary['delivered'], 0)
        for edit in (lambda b:b.update(current=int((NOW-60)*1000),update=int((NOW-60)*1000)),
                     lambda b:b.update(asks=[['102.2','1000']],bids=[['103','1000']]),
                     lambda b:b.update(asks=[['104','1000']],bids=[['100','1000']])):
            report, original = fixture()
            def changed(url):
                raw = original(url)
                if '/spot/order_book?' in url: edit(raw)
                return raw
            _, summary = self.deliver(report, changed)
            self.assertEqual(summary['delivered'], 0)

    def test_forged_label_missing_provenance_and_stale_reports_are_silent(self):
        for mutate in (lambda r:r.update(as_of='2020-01-01T00:00:00+00:00'),
                       lambda r:r['results'][0].update(provider_evidence=[]),
                       lambda r:r['results'][0].update(buy_authorized=True)):
            report, fetch = fixture()
            mutate(report)
            _, summary = self.deliver(report, fetch)
            self.assertEqual(summary['delivered'], 0)

    def test_two_per_run_three_per_day_and_pair_timeframe_dedup(self):
        report, fetch = fixture(('ADA_USDT','BCH_USDT','BNB_USDT'))
        updated, summary = self.deliver(report, fetch)
        self.assertEqual(summary['delivered'], 2)
        _, summary = self.deliver(report, fetch, updated)
        self.assertEqual(summary['delivered'], 1)
        blocked = state()
        day = dt.datetime.fromtimestamp(NOW,dt.timezone(dt.timedelta(hours=1))).date().isoformat()
        blocked['daily_counts'] = {day:3}
        _, summary = self.deliver(report, fetch, blocked)
        self.assertEqual(summary['delivered'], 0)

    def test_missing_adverse_screen_and_corrupt_state_fail_closed(self):
        report, fetch = fixture()
        with self.assertRaises(ValueError):
            alerts.deliver(report, state(), fetch, lambda _: True, lambda _:None, now=lambda:NOW)
        with self.assertRaises(ValueError):
            self.deliver(report, fetch, {'version':1,'delivered':[]})

    def test_archive_adverse_identity_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)/'evidence.json'
            path.write_text(json.dumps([dict(network='eth',contract='0x'+'a'*40,
                verification={'sellability':{'status':'FAIL'}})]))
            self.assertIn(key('eth','0x'+'a'*40),alerts.known_adverse([path]))
            path.write_text('{')
            with self.assertRaises(ValueError): alerts.known_adverse([path])

    def test_steady_uptrend_is_not_called_a_bullish_reversal(self):
        bars = [dict(timestamp=i+1,open=100+i,close=100+i,high=101+i,low=99+i,
                     volume=1000,closed=True) for i in range(55)]
        result = analyze('BCH/USDT',bars,source='fixture',observed_at='2026-11-05T00:00:00Z')
        self.assertEqual(result['classification'], 'INSUFFICIENT EVIDENCE')
        self.assertFalse(result['metrics']['prior_downtrend'])

    def test_confirmed_receipt_with_failed_persistence_is_an_operational_failure(self):
        report, fetch = fixture()
        def cannot_save(snapshot):
            raise OSError('fixture storage unavailable')
        with self.assertRaisesRegex(RuntimeError, 'state persistence failed'):
            alerts.deliver(report, state(), fetch, lambda _:True, cannot_save,
                           now=lambda:NOW, negatives=set())

    def test_boolean_honeypot_flag_cannot_escape_the_adverse_veto(self):
        report, source = fixture(adverse=True)
        def fetch(url):
            raw = source(url)
            if urlsplit(url).hostname == 'api.gopluslabs.io':
                raw['result']['0x'+'a'*40]['is_honeypot'] = True
            return raw
        _, summary = self.deliver(report, fetch)
        self.assertEqual(summary['delivered'], 0)
        self.assertIn('Adverse contract capability/sellability finding', summary['suppressed'])



class TimeframeReceiptTests(unittest.TestCase):
    def test_weekly_receipt_does_not_suppress_new_daily_setup(self):
        report, fetch = fixture()
        previous = state()
        previous['delivered']['BCH_USDT'] = dict(delivered_at=dt.datetime.fromtimestamp(NOW,dt.timezone.utc).isoformat(),
            classification='EARLY REVERSAL WATCH',entry_trigger=200,invalidation=50,interval='1w')
        sent=[]
        updated, summary=alerts.deliver(report,previous,fetch,lambda text:sent.append(text) or True,
            lambda _:None,now=lambda:NOW,negatives=set())
        self.assertEqual(summary['delivered'],1)
        self.assertEqual(len(sent),1)
        self.assertIn('BCH_USDT|1w',updated['delivered_by_setup'])
        self.assertIn('BCH_USDT|1d',updated['delivered_by_setup'])
        # The same daily setup remains suppressed after the legacy pair pointer
        # is changed by a weekly delivery.
        updated['delivered']['BCH_USDT']=updated['delivered_by_setup']['BCH_USDT|1w']
        _, summary=alerts.deliver(report,updated,fetch,lambda _:self.fail('Duplicate daily delivery'),
            lambda _:None,now=lambda:NOW,negatives=set())
        self.assertEqual(summary['delivered'],0)
        self.assertEqual(summary['suppressed']['cooldown'],1)

    def test_corrupt_setup_receipts_refuse_transport(self):
        report, fetch=fixture()
        previous=state();previous['delivered_by_setup']=[]
        with self.assertRaises(ValueError):
            alerts.deliver(report,previous,fetch,lambda _:self.fail('Corrupt dedup state'),
                lambda _:None,now=lambda:NOW,negatives=set())


class ConciseResearchMessageTests(unittest.TestCase):
    def test_live_book_and_closed_reference_are_separate_and_source_bound(self):
        report,fetch=fixture()
        row=report['results'][0]
        screened=alerts.screen(row,row['research'],alerts.PublicGate(fetch),
            [{'currency':'BCH','delisted':False,'trade_disabled':False,'chains':[]}],set(),lambda:NOW)
        text=alerts.message(row,row['research'],screened)
        self.assertIn('Live bid/ask: 102.1/102.2 USDT',text)
        self.assertIn('last closed candle:',text)
        self.assertIn('Candle source: https://api.gateio.ws/api/v4/spot/candlesticks?',text)
        self.assertIn('Reassess at the next closed candle',text)
        self.assertIn('NOT A BUY SIGNAL',text)
        self.assertIn('supply/unlocks',text)
        self.assertNotIn('Dev commits/4w: UNKNOWN',text)
        self.assertLess(len(text),2400)
