"""Authenticated lifetime-history certification, separate from BUY admission.

Enrollment is local reviewed configuration, never supplied by candidates. Signed
manifests bind exact-asset inception, complete venue inventory, transformations,
security scope and immutable independent source archives. Archive contents are
replayed and their continuity/minima/caps recomputed; completeness flags ignored.
No production reviewer or historical evidence is invented by this module.
"""
import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
import pathlib
import re
import time
import subprocess
import urllib.request

import authenticated_admission as auth
from atl_monitor_core import positive, cap_class
from atl_recovery import assess_recovery

ROOT=pathlib.Path(__file__).resolve().parent
SCHEMA='atl-lifetime-review-v1'
MAX_POINTS=2_000_000


def require(value,reason):
    if not value:raise ValueError(reason)


def stamp(value):return auth.stamp(value)


def identity(value):
    require(isinstance(value,dict),'Exact identity required')
    require(value.get('network') in ('eth','bsc','base','arbitrum','polygon_pos','avax','optimism'),'Unsupported lifetime chain')
    return {'network':value['network'],'contract':auth.address(value['contract'])}


def load_registry():
    return json.loads((ROOT/'atl_lifetime_registry.json').read_text())


def archive_url(reference,registry):
    """Only reviewed repositories and immutable GitHub raw JSON paths are fetched.

    A candidate URL, enrolled arbitrary domain, redirect URL, IP or query can
    never become a fetch destination. Injected fetchers must reject redirects.
    """
    source=registry['sources'][reference['source']]
    repository=source['repository'];prefix=source['path_prefix'];commit=reference['commit'];path=reference['path']
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository),'Invalid enrolled archive repository')
    require(re.fullmatch(r'[0-9a-f]{40}',commit),'Immutable archive commit required')
    require(isinstance(path,str) and re.fullmatch(r'[A-Za-z0-9_/-]+\.json',path)
            and '..' not in path and path.startswith(prefix) and prefix.endswith('/'),'Unreviewed archive path')
    return 'https://raw.githubusercontent.com/'+repository+'/'+commit+'/'+path,source


def reviewed(bundle,registry,trust,asset,now):
    require(isinstance(trust,dict) and trust.get('schema')==auth.VERSION and isinstance(trust.get('reviewers'),dict) and isinstance(trust.get('sources'),dict),'Invalid independent review trust registry')
    payload=bundle['payload'];message=auth.canonical(payload)
    require(len(message)<=500000,'Lifetime manifest exceeds bounds')
    require(payload['schema']==SCHEMA and identity(payload['identity'])==asset,'Lifetime manifest identity mismatch')
    require(0<=now-stamp(payload['observed_at'])<=120 and now<stamp(payload['expires_at'])<=stamp(payload['observed_at'])+120,'Lifetime manifest stale or expired')
    signatures=bundle['signatures'];require(isinstance(signatures,list) and len(signatures)==2,'Two independent lifetime reviewers required')
    organizations=set();keys=set();reviewers=set()
    for signed in signatures:
        name=signed['reviewer'];require(name not in reviewers,'Duplicate lifetime reviewer')
        reviewer=trust['reviewers'][name]
        require(isinstance(reviewer,dict) and isinstance(reviewer.get('scopes'),list) and all(isinstance(x,str) for x in reviewer['scopes']) and reviewer.get('revoked') is False and 'atl_lifetime' in reviewer['scopes'],'Lifetime reviewer not enrolled')
        require(stamp(reviewer['valid_from'])<=now<stamp(reviewer['valid_until']),'Lifetime reviewer authorization expired')
        require(isinstance(reviewer.get('organization'),str) and bool(reviewer['organization'].strip()),'Reviewer organization missing')
        organization=reviewer['organization'].strip().casefold()
        key=auth.verify_signature(reviewer['public_key'],signed['signature'],message)
        require(key not in keys and organization not in organizations,'Lifetime reviewers not independent')
        reviewers.add(name);keys.add(key);organizations.add(organization)
    inception=stamp(payload['first_trade_at']);require(0<inception<now,'Invalid first trading timestamp')
    venues=payload['venues'];require(isinstance(venues,list) and 1<=len(venues)<=20 and len(set(venues))==len(venues),'Complete reviewed venue inventory required')
    require(all(isinstance(v,str) and re.fullmatch('[a-z0-9_-]{1,60}',v) for v in venues),'Invalid venue identity')
    firsts=payload.get('venue_first_trade_at',{v:payload['first_trade_at'] for v in venues})
    require(isinstance(firsts,dict) and set(firsts)==set(venues),'Per-venue inception inventory incomplete')
    require(min(stamp(v) for v in firsts.values())==inception and all(inception<=stamp(v)<now for v in firsts.values()),'Per-venue inception conflicts with global first trade')
    require(payload.get('first_candle_scope')=='POST_LISTING_TRADES_ONLY','Reviewed first-candle comparability scope absent')
    # Nonempty unresolved migration records are never treated as comparable.
    require(payload['transformations']==[],'Migration/redenomination requires a dedicated independently reviewed conversion adapter')
    require(payload['instrument']=='ORDINARY_CRYPTO','Excluded or unresolved instrument type')
    scope=payload['security_review']
    require(scope['verdict']=='VERIFIED_RESEARCH_ONLY' and identity(scope['identity'])==asset,'Lifetime security clearance absent')
    require(0<=now-stamp(scope['observed_at'])<=7200 and now<stamp(scope['expires_at'])<=stamp(scope['observed_at'])+7200,'Lifetime security clearance stale')
    controls=scope['controls']
    required={'identity','sellability','taxes','authority','lp_controls','holders','circulation','vesting','bridge_backing'}
    require(set(controls)==required and all(v in ('VERIFIED','NOT_APPLICABLE') for v in controls.values()),'Security scope incomplete, conflicting or adverse')
    require(all(controls[k]=='VERIFIED' for k in required-{'bridge_backing'}),'Mandatory security controls cannot be not applicable')
    return payload,sorted(reviewers),hashlib.sha256(message).hexdigest()


def replay(reference,registry,asset,payload,fetch,now):
    url,source=archive_url(reference,registry)
    raw=fetch(url)
    require(hashlib.sha256(auth.canonical(raw)).hexdigest()==reference['sha256'],'Historical archive digest conflict')
    require(raw['source_id']==reference['source'],'Historical source identity mismatch')
    require(raw['schema']=='atl-minute-archive-v1' and identity(raw['identity'])==asset,'Historical archive identity mismatch')
    require(raw['quote']=='USD_PER_WHOLE_TOKEN' and raw['transformations']==payload['transformations'],'Noncomparable price basis')
    require(0<=now-stamp(raw['observed_at'])<=120,'Historical archive stale')
    require(set(raw['venues'])==set(payload['venues']),'Incomplete venue coverage')
    interval=raw.get('interval_seconds',60)
    require(type(interval) is int and interval in (60,3600,86400),'Unsupported historical candle interval')
    end=int(now//interval*interval)
    market=raw['market'];price=positive(market['price_usd']);supply=positive(market['circulating_supply']);cap=positive(market['circulating_market_cap_usd'])
    require(None not in (price,supply,cap) and abs(cap-price*supply)/cap<=Decimal('.02'),'Circulating capitalization inconsistent')
    require(0<=now-stamp(market['observed_at'])<=120,'Market archive stale')
    lows=[];rows_by_venue={};total=0
    for venue in payload['venues']:
        first=stamp(payload.get('venue_first_trade_at',{}).get(venue,payload['first_trade_at']))
        start=int(first//interval*interval)
        rows=raw['venues'][venue]
        require(isinstance(rows,list) and len(rows)==(end-start)//interval and rows,'Missing historical candles or complete lifetime evidence')
        total+=len(rows);require(total<=MAX_POINTS,'Historical archive exceeds bounded replay size')
        parsed=[]
        for index,row in enumerate(rows):
            require(isinstance(row,list) and len(row)==6 and type(row[0]) is int and row[0]==start+index*interval,'Historical gap, duplicate or chronology conflict')
            opening,high,low,close,volume=(positive(x) for x in row[1:])
            require(None not in (opening,high,low,close) and isinstance(row[5],(str,int,float)) and not isinstance(row[5],bool),'Invalid historical OHLCV')
            volume=auth.number(row[5])
            require(low<=min(opening,close)<=max(opening,close)<=high,'Invalid historical candle bounds')
            lows.append(low);parsed.append((row[0],opening,high,low,close,volume))
        rows_by_venue[venue]=parsed
        # Coarser closed bars alone leave today's/hour's unobserved tail. Require
        # actual source OHLC for that partial interval through fresh observation.
        if now>end:
            partial=raw.get('partial_candles',{}).get(venue)
            require(isinstance(partial,list) and len(partial)==6 and type(partial[0]) is int and partial[0]==end,'Current partial-range low evidence missing')
            op,hi,lo,cl=(positive(x) for x in partial[1:5])
            require(None not in (op,hi,lo,cl) and lo<=min(op,cl)<=max(op,cl)<=hi,'Invalid current partial OHLC')
            auth.number(partial[5]);lows.append(lo)
    require(isinstance(source.get('organization'),str),'Independent archive organization missing')
    organization=source['organization'].strip().casefold()
    require(organization and organization not in ('unknown',''),'Independent archive organization missing')
    # Known common-owner providers cannot be counted as independent archives.
    if organization in ('geckoterminal','coingecko'):organization='coingecko'
    return dict(url=url,organization=organization,minimum=min(lows),price=price,supply=supply,cap=cap,
                earliest=int(stamp(payload['first_trade_at'])),through=now,rows=total,venues=rows_by_venue,interval_seconds=interval,
                fresh_until=min(stamp(raw['observed_at']),stamp(market['observed_at']))+120)


def recovery(source,venue,now):
    rows=source['venues'][venue];hours={}
    if source['interval_seconds']==86400:return {'status':'INSUFFICIENT EVIDENCE','reason':'Daily history cannot establish hourly recovery'}
    if source['interval_seconds']==3600:
        candles=[dict(at=dt.datetime.fromtimestamp(r[0]+3600,dt.timezone.utc).isoformat(),closed=True,low=str(r[3]),high=str(r[2]),close=str(r[4]),volume=str(r[5])) for r in rows]
        return assess_recovery(candles[-30:],comparable=True,venue_verified=True,now=dt.datetime.fromtimestamp(now,dt.timezone.utc))
    for row in rows:
        hour=row[0]//3600*3600
        if hour+3600<=now:hours.setdefault(hour,[]).append(row)
    candles=[]
    for hour,points in sorted(hours.items()):
        if len(points)!=60 or points[0][0]!=hour:continue
        candles.append(dict(at=dt.datetime.fromtimestamp(hour+3600,dt.timezone.utc).isoformat(),closed=True,
            low=str(min(x[3] for x in points)),high=str(max(x[2] for x in points)),close=str(points[-1][4]),volume=str(sum(x[5] for x in points))))
    return assess_recovery(candles[-30:],comparable=True,venue_verified=True,now=dt.datetime.fromtimestamp(now,dt.timezone.utc))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Historical archive redirects are prohibited')


def fetch_archive(url):
    # URL is constructed from reviewed repository/commit/path by archive_url.
    # Never send credentials or follow a provider-controlled redirect.
    opener=urllib.request.build_opener(_NoRedirect())
    request=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'crypto-oracle-atl-replay/1.0'})
    with opener.open(request,timeout=8) as response:
        payload=response.read(8_000_001)
    require(len(payload)<=8_000_000,'Historical archive exceeds free bounded replay byte budget')
    return json.loads(payload)


def evaluate(bundle,asset,fetch=None,*,now):
    """Never BUY: genuine complete evidence may qualify a research classification.

    `fetch` is called only for fixed immutable reviewed archive URLs. No candidate
    URLs, direct IPs or arbitrary source endpoints are accepted. A trusted fetch
    implementation must refuse redirects and apply an execution request budget.
    """
    result=dict(status='UNVERIFIED',classification=None,lifetime_verified=False,buy_authorized=False,orders_allowed=False,blockers=[])
    try:
        asset=identity(asset);registry=load_registry();trust=auth.load_trust()
        fetch=fetch or fetch_archive
        require(registry['schema']==SCHEMA and isinstance(registry['sources'],dict),'Invalid lifetime registry')
        payload,reviewers,digest=reviewed(bundle,registry,trust,asset,now)
        refs=payload['archives'];require(isinstance(refs,list) and len(refs)==2,'Two independent lifetime archives required')
        require(len({x['source'] for x in refs})==len(refs) and len({x['sha256'] for x in refs})==len(refs),'Duplicate or copied lifetime source archives')
        sources=[replay(ref,registry,asset,payload,fetch,now) for ref in refs]
        require(len({x['organization'] for x in sources})==len(sources),'Lifetime source organizations not independent')
        minima=[x['minimum'] for x in sources];prices=[x['price'] for x in sources];supplies=[x['supply'] for x in sources];caps=[x['cap'] for x in sources]
        for values,name in ((minima,'Historical minimum'),(prices,'Current price'),(supplies,'Circulating supply'),(caps,'Market cap')):
            require(max(values)/min(values)<=Decimal('1.01'),name+' source conflict')
        cap=min(caps);category=cap_class(cap,verified=True,fresh=True)
        require(category in ('MID_CAP','HIGH_CAP'),'Outside target circulating capitalization')
        require(all(cap_class(x,verified=True,fresh=True)==category for x in caps),'Source market-cap boundary conflict')
        low=min(minima);price=max(prices);above=(price/low-1)*100
        # All sources must agree the current print meets the low, within 1bp
        # precision. A lower live print is not accepted on a lone source.
        label=None
        if all(p<=low*Decimal('1.0001') for p in prices):label='ALL TIME LOW'
        elif 0<=above<=5:label='NEAR ALL TIME LOW'
        recoveries=[recovery(s,payload['recovery_venue'],now) for s in sources] if payload.get('recovery_venue') in payload['venues'] else []
        recovered=recoveries[0] if recoveries else {'status':'NO_TRIGGER'}
        if label is None and 5<above<=20 and recoveries and all(r['status']=='TECHNICAL WATCH' for r in recoveries):label='ATL RECOVERY WATCH'
        result.update(status='VERIFIED_RESEARCH' if label else 'VERIFIED_NO_EVENT',classification=label,lifetime_verified=True,
            identity=asset,market_cap_usd=str(cap),cap_category=category,price_usd=str(price),low_usd=str(low),percent_above=str(above),
            earliest_observation=payload['first_trade_at'],coverage_through=dt.datetime.fromtimestamp(sources[0]['through'],dt.timezone.utc).isoformat(),
            sources=[x['url'] for x in sources],reviewers=reviewers,evidence_sha256=digest,expires_at=dt.datetime.fromtimestamp(min(stamp(payload['expires_at']),stamp(payload['security_review']['expires_at']),*(x['fresh_until'] for x in sources)),dt.timezone.utc).isoformat(),recovery=recovered,
            precision='1bp',scope='Independently reviewed venue inventory; research only, final owner purchase approval required')
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError,OSError,subprocess.SubprocessError) as exc:
        result['blockers']=[str(exc) if isinstance(exc,ValueError) else 'Lifetime evidence missing, malformed or unavailable']
    return result


def notice(result):
    """Do not call with serialized results; use qualified_notice to replay first."""
    raise ValueError('Replayed signed lifetime evidence required')


def qualified_notice(bundle,asset,fetch=None,*,now):
    result=evaluate(bundle,asset,fetch,now=now)
    if result['status']!='VERIFIED_RESEARCH':return result,None
    from research_notice import _issue
    body=('SIGNED LIFETIME RESEARCH. NOT A BUY APPROVAL.\nName/symbol: '+str(bundle['payload'].get('name','UNKNOWN'))[:100]+'/'+str(bundle['payload'].get('symbol','UNKNOWN'))[:40]+'\n'+result['identity']['network']+':'+result['identity']['contract']
          +'\nObserved USD price: '+result['price_usd']+'; lifetime low: '+result['low_usd']
          +'; above low: '+result['percent_above']+'%\nCirculating market cap USD: '+result['market_cap_usd']
          +'\nLifetime coverage: '+result['earliest_observation']+' through '+result['coverage_through']
          +'\nSource observation UTC: '+bundle['payload']['observed_at']+'; venues: '+', '.join(bundle['payload']['venues'])+'\nEvidence expires: '+result['expires_at']+'\nReviewers: '+', '.join(result['reviewers'])
          +'\nSecurity clearance is scoped signed research; changes and total loss remain possible.\n'
          +'Entry/invalidation/profit targets: not established by an ATL alone. No automatic orders.\nSources: '+'\n'.join(result['sources']))
    return result,_issue(result['classification'],body)


def collect(dossiers,*,now):
    """One locally enrolled exact-contract manifest/run; no enrollment side effects.

    Registry manifests contain authentic signed bundles keyed network:contract.
    Empty registry is a normal explicit evidence dependency, not a certificate.
    """
    registry=load_registry()
    manifests=registry.get('manifests')
    if not isinstance(manifests,dict):raise ValueError('Invalid enrolled lifetime manifests')
    result=dict(status='NO_ENROLLED_LIFETIME_EVIDENCE',assessed=0,findings=[],buy_authorized=False,orders_allowed=False)
    for d in dossiers:
        for asset in d.get('asset',{}).get('contracts',[]):
            if asset.get('network') not in ('eth','bsc','base','arbitrum','polygon_pos','avax','optimism'):continue
            try:exact=identity(asset)
            except (ValueError,TypeError,KeyError):continue
            key=exact['network']+':'+exact['contract'];bundle=manifests.get(key)
            if bundle is None:continue
            veto=None
            if d.get('instrument',{}).get('status')!='ORDINARY_CRYPTO_RESEARCH' or d.get('history',{}).get('conflicting') is not False:
                veto='Live instrument type unknown/excluded or historical evidence conflicting'
            try:current_age=now-stamp(d['observed_at'])
            except (ValueError,TypeError,KeyError):current_age=-1
            if not 0<=current_age<=120:veto='Live exact-asset metadata stale or unavailable'
            if veto:
                return dict(status='UNVERIFIED',assessed=1,findings=[dict(identity=exact,lifetime_verified=False,classification=None,blockers=[veto])],buy_authorized=False,orders_allowed=False),None
            finding,notice=qualified_notice(bundle,exact,now=now)
            # A fresh provider observation conflicting with authenticated prices
            # cannot be silently replaced by the more favourable dataset.
            if finding['lifetime_verified']:
                observed=positive(d.get('price_usd'))
                reviewed_price=positive(finding['price_usd'])
                live_cap=positive(d.get('circulating_market_cap_usd'));reviewed_cap=positive(finding['market_cap_usd'])
                if observed is None or live_cap is None or abs(observed/reviewed_price-1)>Decimal('.01') or abs(live_cap/reviewed_cap-1)>Decimal('.01'):
                    finding.update(status='UNVERIFIED',classification=None,lifetime_verified=False,
                                   blockers=['Live collector conflicts with independently reviewed price/circulating cap']);notice=None
            result.update(status=finding['status'],assessed=1,findings=[finding])
            return result,notice
    return result,None


def telegram_request(token,method,data):
    require(method in ('getChat','sendMessage'),'Unsupported ATL transport method')
    import urllib.parse
    request=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,
        data=urllib.parse.urlencode(data).encode(),method='POST')
    with urllib.request.build_opener(_NoRedirect()).open(request,timeout=8) as response:
        payload=response.read(100001)
    require(len(payload)<=100000,'Oversized Telegram response')
    return json.loads(payload)


def deliver(dossiers,state,env,transport,*,now,persist=None):
    """Revalidate enrolled signed manifests before any qualified transport.

    Caller Boolean verdicts/results are never accepted. Confirmed state advances
    only after the exact destination and positive Bot API message ID are proven.
    """
    from research_notice import verified_text
    from telegram_receipts import confirmed
    started=time.monotonic()
    report,notice=collect(dossiers,now=now)
    report.update(delivered=0,failed=0)
    if notice is None:return report
    finding=report['findings'][0]
    day=dt.datetime.fromtimestamp(now,dt.timezone(dt.timedelta(hours=1))).date().isoformat()
    fingerprint=hashlib.sha256(auth.canonical({k:finding[k] for k in ('identity','classification','low_usd','earliest_observation')})).hexdigest()
    if state.get('qualified_confirmed_day')==day:
        report['delivery_status']='DAILY_DEDUP';return report
    if fingerprint in state.get('qualified_confirmed',{}):
        report['delivery_status']='UNCHANGED_EVIDENCE_DEDUP';return report
    token,chat=(env.get(k,'').strip() for k in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'))
    if not token or not chat:
        report['delivery_status']='TRANSPORT_NOT_CONFIGURED';report['failed']=1;return report
    receipt_accepted=False
    try:
        target=transport(token,'getChat',{'chat_id':chat});result=target.get('result') or {};destination=result.get('id')
        require(target.get('ok') is True and type(destination) is int and destination!=0,'Qualified destination unconfirmed')
        if chat.startswith('@'):
            require('@'+str(result.get('username','')).casefold()==chat.casefold(),'Qualified destination alias mismatch')
        else:require(str(destination)==chat,'Qualified destination mismatch')
        effective_now=now+(time.monotonic()-started)
        require(effective_now<stamp(finding['expires_at']),'Qualified evidence expired during validation/transport')
        message=verified_text(notice)
        require(len(message.encode('utf-16-le'))//2<=3900,'Qualified disclosure exceeds message limit')
        receipt=transport(token,'sendMessage',{'chat_id':chat,'text':message,'disable_web_page_preview':'true'})
        require(confirmed(receipt,str(destination)),'Qualified delivery receipt unconfirmed')
        receipt_accepted=True
        state['qualified_confirmed_day']=day
        state.setdefault('qualified_confirmed',{})[fingerprint]=dict(message_id=receipt['result']['message_id'],
            evidence_sha256=finding['evidence_sha256'],confirmed_at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),
            identity=finding['identity'],classification=finding['classification'])
        state['qualified_confirmed']=dict(list(state['qualified_confirmed'].items())[-200:])
        report.update(delivered=1,delivery_status='BOT_API_CONFIRMED',message_id=receipt['result']['message_id'])
        if persist is not None:persist(state)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,AttributeError):
        report.update(failed=1,delivery_status='STATE_PERSISTENCE_FAILED' if receipt_accepted else 'DELIVERY_FAILED')
    return report
