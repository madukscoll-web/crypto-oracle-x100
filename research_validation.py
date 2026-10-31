"""Versioned, uncalibrated ranking and purged walk-forward/holdout validation.

An offline consistency test is not source authentication. A real point-in-time
cohort and independent execution evidence are mandatory before performance claims.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from asset_identity import key

MODELS = {
 'meme-v1': {'type':'meme','weights':{'liquidity_valuation':.30,'organic_wallet_growth':.25,'flow_quality':.25,'momentum_quality':.20}},
 'utility-v1': {'type':'utility','weights':{'liquidity_valuation':.20,'retained_users':.25,'revenue_quality':.25,'developer_retention':.15,'dilution_quality':.15}},
}


def stamp(value):
    value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('Point-in-time timestamp needs timezone')
    return value.astimezone(dt.timezone.utc)


def finite(value):
    if isinstance(value,bool):raise ValueError('Boolean is not measurement')
    value=float(value)
    if not math.isfinite(value):raise ValueError('Nonfinite input')
    return value


def score(record, model):
    weights=MODELS[model]['weights'];at=stamp(record['feature_at']);parts={}
    for name,weight in weights.items():
        observation=record['features'][name]
        if stamp(observation['available_at'])>at or stamp(observation['observed_at'])>at:
            raise ValueError('Look-ahead feature leakage')
        if not observation.get('source_url','').startswith('https://') or not observation.get('origin'):
            raise ValueError('Feature provenance missing')
        value=finite(observation['normalized_value'])
        if not 0<=value<=1:raise ValueError('Normalized feature outside documented range')
        parts[name]=weight*value
    return {'score':round(sum(parts.values())*100,6),'components':parts,
            'status':'UNCALIBRATED_HEURISTIC','model_version':model,
            'model_hash':hashlib.sha256(json.dumps(MODELS[model],sort_keys=True).encode()).hexdigest()}


def validate_record(record):
    if key(record['network'],record['token_address'])!=record['asset_key']:
        raise ValueError('Historical chain/contract identity mismatch')
    if record['asset_type'] not in ('meme','utility'):raise ValueError('Unknown research stratum')
    feature=stamp(record['feature_at']);end=stamp(record['label_available_at'])
    if feature>=end:raise ValueError('Label not strictly after entry features')
    if not record.get('cohort_id') or record.get('selection_basis')!='LAUNCH_COHORT_BEFORE_OUTCOMES':
        raise ValueError('Winners-only or retrospectively selected sample')
    execution=record['execution']
    if execution['status']!='SOURCE_BOUND_EXECUTABLE_SNAPSHOT':raise ValueError('Historical execution evidence missing')
    # Position size must fit contemporaneously measured entry and exit depth.
    for leg in ('entry','exit'):
        e=execution[leg]
        if e['asset_key']!=record['asset_key']:raise ValueError('Execution asset mismatch')
        if not e.get('source_url','').startswith('https://') or not e.get('origin'):
            raise ValueError('Execution provenance missing')
        if stamp(e['at'])!= (feature if leg=='entry' else end):raise ValueError('Execution timestamp mismatch')
        if min(finite(e['price_usd']),finite(e['depth_usd']),finite(e['position_usd']))<=0:
            raise ValueError('Invalid historical execution')
        if finite(e['depth_usd'])<finite(e['position_usd']):raise ValueError('Position exceeds recorded executable depth')
        if min(finite(e['fees_usd']),finite(e['slippage_fraction']))<0 or finite(e['slippage_fraction'])>=1:
            raise ValueError('Invalid historical costs')
    entry,exit=execution['entry'],execution['exit']
    size=finite(entry['position_usd'])
    units=(size-finite(entry['fees_usd']))/(finite(entry['price_usd'])*(1+finite(entry['slippage_fraction'])))
    if units<=0:raise ValueError('Entry costs consume position')
    proceeds=units*finite(exit['price_usd'])*(1-finite(exit['slippage_fraction']))-finite(exit['fees_usd'])
    # Exit depth must cover actual liquidation not just a caller's smaller size.
    if max(finite(exit['position_usd']),proceeds)>finite(exit['depth_usd']):raise ValueError('Exit proceeds exceed verified depth')
    return proceeds/size


def evaluate(dataset):
    records=dataset['records'];base={'scope':'OFFLINE_SOURCE_CONSISTENCY_ONLY','probabilities_calibrated':False,
        'buy_authorized':False,'orders_allowed':False,'models':MODELS,'records':len(records)}
    if not records:
        return dict(base,status='BLOCKED',reason='No source-bound winners-and-failures cohort',blockers=dataset.get('blockers',[]),folds=[],holdout=None)
    ids=[r['asset_key'] for r in records]
    if len(set(ids))!=len(ids):raise ValueError('Asset overlap: one observation per asset in this protocol')
    prepared=[]
    for record in records:
        multiple=validate_record(record)
        model='meme-v1' if record['asset_type']=='meme' else 'utility-v1'
        prepared.append(dict(record=record,multiple=multiple,ranking=score(record,model)['score']))
    prepared.sort(key=lambda r:stamp(r['record']['feature_at']))
    if len(prepared)<20:return dict(base,status='BLOCKED',reason='At least 20 independent source-bound assets required',folds=[],holdout=None)
    # Require matched losing outcomes in every stratum; no winner-only study.
    for kind in {r['record']['asset_type'] for r in prepared}:
        group=[r for r in prepared if r['record']['asset_type']==kind]
        if not any(r['multiple']<1 for r in group) or not any(r['multiple']>=1 for r in group):
            raise ValueError('Missing winning or failed controls in stratum')
    split=int(len(prepared)*.8);development,holdout=prepared[:split],prepared[split:]
    def metrics(rows):
        strata={}
        for kind in sorted({r['record']['asset_type'] for r in rows}):
            group=[r for r in rows if r['record']['asset_type']==kind]
            ranked=sorted(group,key=lambda r:r['ranking'],reverse=True);top=ranked[:max(1,len(group)//4)]
            strata[kind]={'n':len(group),'top_quartile_positive_fraction':sum(r['multiple']>1 for r in top)/len(top),
                'baseline_positive_fraction':sum(r['multiple']>1 for r in group)/len(group),
                'top_quartile_false_positive_fraction':sum(r['multiple']<=1 for r in top)/len(top),
                'observed_100x_count':sum(r['multiple']>=100 for r in group),'observed_1000x_count':sum(r['multiple']>=1000 for r in group)}
        return {'n':len(rows),'by_asset_type':strata}
    folds=[]
    for offset in range(8,len(development),4):
        test=development[offset:offset+4];cutoff=stamp(test[0]['record']['feature_at'])
        train=[r for r in development[:offset] if stamp(r['record']['label_available_at'])<cutoff]
        folds.append(dict(train_count=len(train),purged_count=offset-len(train),test=metrics(test),
            parameters='Fixed versioned heuristic, no fitting or retrospective tuning'))
    # No historical label arriving after the holdout starts can inform selection.
    cutoff=stamp(holdout[0]['record']['feature_at'])
    allowed=sum(stamp(r['record']['label_available_at'])<cutoff for r in development)
    return dict(base,status='COMPUTED_NOT_EXTERNALLY_VERIFIED',folds=folds,holdout=metrics(holdout),
                matured_development_count=allowed,limitations=['Provenance records are not independent source authentication',
                'Fixed heuristics remain uncalibrated; this does not authorize any recommendation'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=evaluate(json.loads(Path(args.dataset).read_text()));Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('models','folds')}))
