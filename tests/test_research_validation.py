"""Synthetic protocol tests, never historical market evidence."""
import copy
import datetime as dt
import unittest
from research_validation import MODELS, evaluate, validate_record
from asset_identity import key


def cohort(n=20):
    rows=[];start=dt.datetime(2020,1,1,tzinfo=dt.timezone.utc)
    for i in range(n):
        at=(start+dt.timedelta(days=i*2)).isoformat();end=(start+dt.timedelta(days=i*2+1)).isoformat()
        token='0x'+format(i+1,'040x');asset=key('eth',token);kind='meme' if i%2 else 'utility'
        model=MODELS['meme-v1' if kind=='meme' else 'utility-v1']
        multiple=.5 if i%4<2 else 2
        leg=lambda price,stamp:dict(asset_key=asset,at=stamp,source_url='https://fixture.invalid/quote',origin='SYNTHETIC',price_usd=price,depth_usd=100000,position_usd=100,fees_usd=1,slippage_fraction=.01)
        rows.append(dict(network='eth',token_address=token,asset_key=asset,asset_type=kind,
            cohort_id='SYNTHETIC_COHORT',selection_basis='LAUNCH_COHORT_BEFORE_OUTCOMES',feature_at=at,label_available_at=end,
            features={name:dict(normalized_value=.5,available_at=at,observed_at=at,source_url='https://fixture.invalid/feature',origin='SYNTHETIC') for name in model['weights']},
            execution={'status':'SOURCE_BOUND_EXECUTABLE_SNAPSHOT','entry':leg(1,at),'exit':leg(multiple,end)}))
    return {'records':rows}


class ResearchValidationTests(unittest.TestCase):
    def test_no_data_is_blocked_not_successful_backtest(self):
        self.assertEqual(evaluate({'records':[]})['status'],'BLOCKED')
    def test_walkforward_and_holdout_do_not_claim_calibration(self):
        result=evaluate(cohort());self.assertEqual(result['holdout']['n'],4)
        self.assertTrue(result['folds']);self.assertFalse(result['probabilities_calibrated'])
        self.assertFalse(result['buy_authorized']);self.assertEqual(result['status'],'COMPUTED_NOT_EXTERNALLY_VERIFIED')
    def test_future_available_features_rejected(self):
        data=cohort();row=data['records'][0];next(iter(row['features'].values()))['available_at']=row['label_available_at']
        with self.assertRaisesRegex(ValueError,'Look-ahead'):evaluate(data)
    def test_asset_overlap_is_rejected(self):
        data=cohort();data['records'].append(copy.deepcopy(data['records'][0]))
        with self.assertRaisesRegex(ValueError,'Asset overlap'):evaluate(data)
    def test_chart_return_without_executable_depth_is_rejected(self):
        row=cohort()['records'][0];row['execution']['entry']['depth_usd']=1
        with self.assertRaisesRegex(ValueError,'depth'):validate_record(row)
    def test_winners_only_selection_is_rejected(self):
        data=cohort();data['records'][0]['selection_basis']='CHOSEN_AFTER_100X'
        with self.assertRaisesRegex(ValueError,'retrospectively'):evaluate(data)
    def test_costs_reduce_chart_return(self):
        row=cohort()['records'][2]
        self.assertLess(validate_record(row),2)
