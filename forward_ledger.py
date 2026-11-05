"""Append-only hash-linked signal/model/price events. Tamper-evident, not tamper-proof.

Quotes, costs and depth are unknown unless the original execution validator passes.
Historical imports are labelled LEGACY_UNKNOWN, never backfilled model predictions.
"""
import datetime as dt
import hashlib
import json
import pathlib
import os
import re
from asset_identity import key

PATH = pathlib.Path('forward_events.jsonl')
ZERO = '0'*64
POLICY_FILES = ('watch_policy.json','canonical_outcomes.py','crypto_oracle_scanner.py','opportunity_alerts.py',
                'authenticated_admission.py','admission_trust.json','adverse_evidence.py','sequential_simulation.py')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def model_version(root=None):
    root=pathlib.Path(root) if root is not None else pathlib.Path(__file__).parent
    files={name:(root/name).read_text() for name in POLICY_FILES}
    return 'research-policy-sha256:'+digest(files)


def read(path=PATH):
    path=pathlib.Path(path)
    if not path.exists():return []
    rows=[];previous=ZERO
    for line in path.read_text().splitlines():
        row=json.loads(line);claimed=row.pop('hash')
        if row.get('previous_hash')!=previous or digest(row)!=claimed:
            raise ValueError('Forward ledger integrity failure; refusing overwrite')
        row['hash']=claimed;rows.append(row);previous=claimed
    return rows


def append(events,path=PATH):
    path=pathlib.Path(path);rows=read(path);ids={row['event_id'] for row in rows}
    previous=rows[-1]['hash'] if rows else ZERO
    count=0;added=[]
    for event in events:
        event=dict(event)
        event_id=digest(event)
        if event_id in ids:continue
        row={'event_id':event_id,'previous_hash':previous,'recorded_at':dt.datetime.now(dt.timezone.utc).isoformat(),'event':event}
        row['hash']=digest(row);added.append(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
        ids.add(event_id);previous=row['hash'];count+=1
    if added:
        # Preserve every existing byte, but publish a complete extension atomically.
        # A killed/interrupted writer cannot expose a partial JSON event.
        prefix=path.read_bytes() if path.exists() else b''
        temp=path.with_suffix(path.suffix+'.tmp')
        with temp.open('wb') as stream:
            stream.write(prefix);stream.write(''.join(added).encode())
            stream.flush();os.fsync(stream.fileno())
        temp.replace(path)
    return count


def capture(history,items,path=PATH):
    rows=read(path);known={row['event']['pool_key'] for row in rows if row['event']['kind']=='SIGNAL'}
    events=[];version=model_version()
    revision=os.environ.get('GITHUB_SHA','')
    revision=revision if re.fullmatch('[0-9a-fA-F]{40}',revision) else None
    run_id=os.environ.get('GITHUB_RUN_ID','')
    run_id=run_id if run_id.isascii() and run_id.isdecimal() and 0<len(run_id)<=24 else None
    items=list(items)
    current_keys={item.get('key') for item in items}
    # Seed retained historical signals even when no current candidate matches.
    # These imports preserve observed prices, but never invent old model features.
    for pool, observations in history.items():
        if pool not in current_keys and isinstance(observations,list) and observations:
            items.append({'key':pool,'network':pool.split(':',1)[0],
                          'token_address':observations[0].get('token_address'),
                          'observed_at':None})
    for item in items:
        pool=item.get('key');observations=history.get(pool,[])
        if not observations:continue
        network=item.get('network') or pool.split(':',1)[0]
        try:identity=key(network,item['token_address'])
        except (KeyError,ValueError):continue
        first=observations[0]
        if pool not in known:
            imported=first['at']!=item.get('observed_at')
            events.append(dict(kind='SIGNAL',pool_key=pool,asset_key=identity,network=network,
                token_address=item['token_address'],at=first['at'],price_usd=first['price_usd'],
                model_version='LEGACY_UNKNOWN' if imported else version,
                source_revision=None if imported else revision,source_run_id=None if imported else run_id,
                import_source_revision=revision if imported else None,import_run_id=run_id if imported else None,
                model_parameters=None if imported else json.loads(pathlib.Path(__file__).with_name('watch_policy.json').read_text()),
                classification='LEGACY_RESEARCH_SIGNAL' if imported else item.get('canonical_outcome','INSUFFICIENT EVIDENCE'),
                historical_import=imported,features=None if imported else {k:item.get(k) for k in ('liquidity','volume','buy_share','change_h1','change_h24')},
                execution_adjusted_return=None,execution_evidence='UNVERIFIED'))
            known.add(pool)
        # Only a price accepted by the existing tracker can become a sample.
        matched=next((r for r in observations if r['at']==item.get('observed_at')),None)
        if matched:
            events.append(dict(kind='PRICE',pool_key=pool,asset_key=identity,at=matched['at'],price_usd=matched['price_usd'],
                model_version=version,source_revision=revision,source_run_id=run_id,source=matched['source'],liquidity_usd=item.get('liquidity'),
                liquidity_scope='Provider pool reserve; not executable depth',execution_costs_usd=None))
    count=append(events,path)
    return {'status':'HASH_CHAIN_VERIFIED','events_appended':count,'events_total':len(read(path)),
            'model_version':version,'liquidity_adjusted_returns':None,
            'false_positive_rate':None,'limitation':'No authenticated size-specific round-trip execution costs or mature labelled cohort; no adjusted return or false-positive rate inferred'}

