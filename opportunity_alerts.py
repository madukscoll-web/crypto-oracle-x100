"""Evidence-labelled research notifications. No orders or trading capability.

INELIGIBLE is internal/silent. ENTRY WATCH is a watch subtype, never a BUY.
The original independent audit and decision gate exclusively control VERIFIED BUY.
"""
import copy
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
from urllib.parse import urlsplit
import evidence_audit
import verification
import telegram_validation
import adverse_evidence

ACTIVE={'HIGH-PRIORITY WATCH','ENTRY WATCH','VERIFIED BUY'}
CRITICAL=adverse_evidence.CHECKS


def number(value):
    if isinstance(value,bool):raise ValueError('Boolean measurement')
    value=float(value)
    if not math.isfinite(value):raise ValueError('Nonfinite measurement')
    return value


def fresh(stamp,now,maximum):
    try:
        value=dt.datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
        return value.tzinfo is not None and 0<=now-value.timestamp()<=maximum
    except (ValueError,TypeError,OverflowError):return False


def policy(path=None):
    data=json.loads(pathlib.Path(path or pathlib.Path(__file__).with_name('watch_policy.json')).read_text())
    if data['version']!=1:raise ValueError('Unknown watch policy version')
    for name,floor,ceiling in [('minimum_score',60,100),('minimum_liquidity_usd',50000,1e12),
        ('minimum_volume_24h_usd',100000,1e13),('minimum_trades_1h',40,1e9),
        ('maximum_market_age_seconds',1,900),('maximum_security_age_seconds',1,1800),
        ('cooldown_seconds',60,86400),('failure_retry_seconds',30,3600)]:
        if not floor<=number(data[name])<=ceiling:raise ValueError('Invalid '+name)
    if not .4<=number(data['minimum_buy_share'])<number(data['maximum_buy_share'])<=.8:raise ValueError('Invalid flow range')
    weights=data['weights']
    if set(weights)!={'liquidity','volume','trades','flow','momentum','early_pool'} or any(number(x)<0 for x in weights.values()) or sum(weights.values())!=100:raise ValueError('Weights must sum to 100')
    return data


def score(item,config):
    liq,vol,trades,share,h1,h24,age=[number(item.get(k)) for k in ('liquidity','volume','trades','buy_share','change_h1','change_h24','age_hours')]
    factors=dict(liquidity=min(1,liq/500000),volume=min(1,vol/1000000),trades=min(1,trades/300),
        flow=1 if .52<=share<=.68 else .5,momentum=1 if 0<=h1<=12 and 0<=h24<=60 else .5,
        early_pool=1 if 0<=age<=72 else .5 if age<=720 else 0)
    parts={k:round(config['weights'][k]*max(0,v),2) for k,v in factors.items()}
    return round(sum(parts.values()),2),parts


def classify(item,config=None,now=None):
    now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    config=config or policy();e=item.get('verification') or {}
    malformed = not isinstance(e, dict) or any(not isinstance(v, dict) for v in e.values())
    if not isinstance(e, dict):e={}
    missing=item.get('mandatory_blockers') or []
    if not isinstance(missing,list):missing=['Malformed mandatory evidence blockers']
    if malformed:missing=['Malformed verification records; independent evidence unavailable']
    if not missing:
        import candidate_evidence
        missing=candidate_evidence.blockers(item)
    result=dict(classification='INELIGIBLE',score=None,components={},reasons=[],missing_checks=list(missing),
                risks=['Can lose the entire allocation; liquidity and exits may disappear','Advanced verification incomplete; no executable entry or guaranteed return'],
                entry=None,observed_at=item.get('observed_at'),eligible_for_buy=False)
    failed=list(item.get('persistent_adverse_reasons') or [])
    failed += [k+': '+reason for k, reason in adverse_evidence.findings(item).items()]
    failed.extend('Prior '+x.get('check','evidence')+': unresolved adverse evidence' for x in item.get('unresolved_prior_adverse_evidence',[]))
    if item.get('risk_category')=='AVOID / HIGH CONCERN':failed.extend(item.get('risk_reasons') or ['Critical security concern'])
    if failed:
        result.update(classification='REJECT',reasons=failed);return result
    if malformed:
        result['reasons']=['Malformed verification records; classification withheld'];return result
    # Caller booleans, scores and watch classifications can never grant BUY.
    import authenticated_admission
    admission = authenticated_admission.evaluate(item, now=now)
    if admission['admitted']:
        result.update(classification='VERIFIED BUY',eligible_for_buy=True,missing_checks=[],
                      reasons=['Authenticated independent mandatory gates passed; manual review required'],
                      risks=['Entire allocation can be lost; liquidity and exits may disappear',
                             'Quotes expire; simulation and review cannot guarantee future execution']);return result
    if admission['safety_verified']:
        result.update(classification='HIGH-PRIORITY WATCH',missing_checks=['Signed entry monitoring required'],
                      reasons=['Authenticated mandatory safety evidence passed; signed entry review requires monitoring'],
                      risks=['Entire allocation can be lost; no BUY signal; recheck fresh evidence'])
        return result
    if item.get('refresh_failed') or item.get('discovery_eligible') is False:
        result['reasons']=['Market refresh unavailable or original market filters failed'];return result
    try:
        token=item['token_address'];network=item['network'];chain=verification.CHAINS[network]
        if not re.fullmatch('0x[0-9a-fA-F]{40}',token):raise ValueError('Exact EVM contract unavailable')
        if item.get('token_identity_status')!='Base token from GeckoTerminal pool relationship':raise ValueError('Independent pool/token relationship unavailable')
        if not fresh(item.get('observed_at'),now,config['maximum_market_age_seconds']):raise ValueError('Market data stale, future-dated or UNKNOWN')
        corroboration=item.get('market_corroboration',{})
        if corroboration.get('status')!='CORROBORATED' or not fresh(corroboration.get('observed_at'),now,config['maximum_market_age_seconds']):raise ValueError('Fresh independent market corroboration unavailable')
        security=e.get('contract_security',{})
        if not fresh(security.get('observed_at'),now,config['maximum_security_age_seconds']):raise ValueError('Preliminary security evidence stale or UNKNOWN')
        endpoint=urlsplit(security.get('url',''))
        if endpoint.hostname!='api.gopluslabs.io' or endpoint.path!=f'/api/v1/token_security/{chain}':raise ValueError('Unbound security provider/chain')
        info=((security.get('raw') or {}).get('result') or {}).get(token.lower())
        if (security.get('raw') or {}).get('code')!=1 or not isinstance(info,dict):raise ValueError('Exact-contract preliminary security response unavailable')
        sec_status,sec_reason=verification.security(info)
        if sec_status=='FAIL':
            result.update(classification='REJECT',reasons=[sec_reason]);return result
        core={'is_honeypot':'0','cannot_sell_all':'0','owner_change_balance':'0','hidden_owner':'0','is_blacklisted':'0','is_open_source':'1'}
        if any(str(info.get(k))!=v for k,v in core.items()) or security.get('status') not in ('LIMITED','UNKNOWN'):
            raise ValueError('Required preliminary security fields UNKNOWN')
        extended=('is_mintable','trading_cooldown','is_proxy','transfer_pausable','slippage_modifiable','personal_slippage_modifiable','selfdestruct')
        unknown=[key for key in extended if str(info.get(key)) not in ('0','1')]
        if unknown:result['missing_checks'].append('Extended preliminary security fields UNKNOWN: '+', '.join(unknown))
        liq,vol,trades,share,h1,h24,price=[number(item.get(k)) for k in ('liquidity','volume','trades','buy_share','change_h1','change_h24','base_token_price_usd')]
        if min(liq,vol,price)<=0 or liq<config['minimum_liquidity_usd'] or vol<config['minimum_volume_24h_usd'] or trades<config['minimum_trades_1h']:raise ValueError('Insufficient measured liquidity, volume or trades')
        if not config['minimum_buy_share']<=share<=config['maximum_buy_share']:raise ValueError('Unbalanced transaction flow')
        if not -3<=h1<=20 or not -15<=h24<=80 or not .5<=vol/liq<=10:raise ValueError('Overextended, deteriorating or abnormal market flow')
        if any(any(word in str(flag).lower() for word in ('wash trading','manipulation')) for flag in item.get('flags',[])):raise ValueError('Market authenticity concern')
        total,parts=score(item,config);result.update(score=total,components=parts)
        if total<config['minimum_score']:raise ValueError('Transparent market score below configured threshold')
        result.update(classification='HIGH-PRIORITY WATCH',reasons=[f'Measured liquidity ${liq:,.0f}, 24h volume ${vol:,.0f}, {trades:g} one-hour trades',f'Balanced buy share {share:.1%}; 1h {h1:+g}%, 24h {h24:+g}%', 'Core exact-contract preliminary flags clear; independent market price corroborated (extended UNKNOWN fields, if any, remain listed)'])
        entry=e.get('entry',{})
        if fresh(entry.get('observed_at'),now,900) and entry.get('source')=='ohlcv':
            # Recompute from actual OHLCV, ignoring caller-provided entry levels.
            analysis=verification.historical_entry(entry.get('raw') or {},now)
            expected='/networks/'+network+'/pools/'+item['address']+'/ohlcv/minute'
            source=urlsplit(entry.get('url',''))
            from urllib.parse import parse_qs,unquote
            args=parse_qs(source.query)
            if source.hostname=='api.geckoterminal.com' and unquote(source.path).endswith(expected) and args.get('aggregate')==['5'] and args.get('currency')==['usd'] and args.get('token')==['base'] and analysis.get('status')=='LIMITED' and abs(price/analysis['entry_reference']-1)<=.05 and price>analysis['invalidation']:
                result.update(classification='ENTRY WATCH',entry=analysis)
                result['reasons'].append('Fresh closed five-minute candles confirm a volume-supported breakout; entry is research only')
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        result['reasons']=[str(exc)]
    return result


def evidence_marks(item):
    return sorted(k+':'+str(v.get('status')) for k,v in (item.get('verification') or {}).items()
                  if isinstance(v,dict) and v.get('status') in ('LIMITED','CORROBORATED') and k not in ('entry',))


def snapshot(item,result):
    return dict(classification=result['classification'],score=result.get('score'),price=item.get('base_token_price_usd'),
        liquidity=item.get('liquidity'),marks=evidence_marks(item),entry=result.get('entry'),token=item.get('token_address'))


def plan(item,result,state,config=None,now=None):
    """Record observations separately from confirmed deliveries; retry failed sends."""
    config=config or policy();now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    key=item['key'];old=state.get(key,{})
    record=copy.deepcopy(old);record.update(network=item['network'],pool_address=item['address'],observed_at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),
        classification=result['classification'],last_snapshot={k:copy.deepcopy(item.get(k)) for k in ('key','network','address','name','token_address','token_symbol','observed_at','liquidity','volume','trades','buy_share','change_h1','change_h24','age_hours','base_token_price_usd','price_source','url','flags','pool_class','score','discovery_token_hint')})
    if result['classification']=='REJECT':
        record['unresolved_adverse_reasons']=sorted(set(record.get('unresolved_adverse_reasons',[])+result['reasons']))
    state[key]=record
    previous=old.get('delivered');current=snapshot(item,result);event=None;urgent=False
    if not previous:
        if result['classification'] in ACTIVE:event='NEW '+result['classification']
    else:
        before=previous['snapshot'];was=before['classification'] in ACTIVE;active=result['classification'] in ACTIVE
        if was and before.get('token')!=current['token']:event='WATCH INVALIDATED: TOKEN IDENTITY CHANGED';urgent=True
        elif was and not active:event='REJECT: NEW ADVERSE EVIDENCE' if result['classification']=='REJECT' else 'WATCH INVALIDATED: EVIDENCE OR MARKET DETERIORATED';urgent=True
        elif active:
            try:
                invalidation=(before.get('entry') or {}).get('invalidation')
                if was and invalidation and number(current['price'])<=number(invalidation):event='ENTRY INVALIDATED: OBSERVED PRICE BELOW HISTORICAL INVALIDATION';urgent=True
                elif was and (number(current['liquidity'])<=number(before['liquidity'])*.75 or number(current['price'])<=number(before['price'])*.8 or number(current['score'])<=number(before['score'])-15):event='SIGNIFICANT DETERIORATION';urgent=True
                elif result['classification']!=before['classification']:event='CLASSIFICATION CHANGED: '+result['classification']
                elif set(current['marks'])-set(before.get('marks',[])):event='NEW EVIDENCE CONFIRMED (SCOPED CHECKS)'
                elif number(current['score'])>=number(before['score'])+10 or number(current['liquidity'])>=number(before['liquidity'])*1.3:event='MATERIAL MARKET IMPROVEMENT'
            except (ValueError,TypeError):pass
        if event and not urgent and now-previous['at']<config['cooldown_seconds']:return None
    if not event:return None
    # A rejected/ineligible delivered state does not generate repetitive WAITs.
    fingerprint=hashlib.sha256(json.dumps(dict(event=event,snapshot=current),sort_keys=True).encode()).hexdigest()
    if previous and previous.get('fingerprint')==fingerprint:return None
    failed=record.get('failed_attempt') or {}
    if now-failed.get('at',-1e12)<config['failure_retry_seconds']:return None
    return dict(event=event,snapshot=current,fingerprint=fingerprint,at=now)


def acknowledge(state,key,notification):
    state[key]['delivered']=copy.deepcopy(notification)
    state[key].pop('failed_attempt',None)


def failed(state,key,now):state[key]['failed_attempt']={'at':now}


def format_alert(item,result,event='NEW WATCH',example=False):
    import authenticated_admission
    admission = authenticated_admission.evaluate(item)
    qualified = result.get('classification') == 'VERIFIED BUY' and admission['admitted'] and not example
    def measurement(key,prefix='',suffix=''):
        try:return prefix+format(number(item.get(key)),'.8g')+suffix
        except (ValueError,TypeError):return 'UNKNOWN'
    title=('BUY CANDIDATE — MANUAL REVIEW' if qualified else 'WAIT/VERIFY' if result['classification']=='VERIFIED BUY' else 'WATCH UPDATE — NO ACTIVE SETUP' if result['classification']=='INELIGIBLE' else result['classification']);missing=list(result.get('missing_checks') or ([] if qualified else ['Mandatory verification completeness UNKNOWN']))
    # All missing checks must survive Telegram's per-message limit; send chunks.
    lines=[('EXAMPLE — NOT A LIVE SIGNAL\n' if example else '')+'CRYPTO-ORACLE X100 — '+title,
        'Authenticated mandatory evidence gates passed; expires with the executable quote' if qualified else 'NOT A VERIFIED BUY SIGNAL',
        'Event: '+event,'Network: '+str(item.get('network','UNKNOWN')),
        'Contract: '+str(item.get('token_address','UNKNOWN')),'Pool: '+str(item.get('address','UNKNOWN')),
        'Observed price: '+measurement('base_token_price_usd','USD ')+' (indicative, not executable)',
        'Market observed UTC: '+str(item.get('observed_at','UNKNOWN')),
        'Price source: '+str(item.get('price_source','UNKNOWN')),
        'Liquidity: '+measurement('liquidity','USD ')+' | 24h volume: '+measurement('volume','USD '),
        valuation(item),
        'Momentum: 1h '+measurement('change_h1',suffix='%')+' | 24h '+measurement('change_h24',suffix='%')+' | buy share '+measurement('buy_share')+' | trades '+measurement('trades'),
        'Pool age hours: '+measurement('age_hours')+'; token launch age UNKNOWN',
        'Watch score: '+str(result.get('score') if result.get('score') is not None else 'UNKNOWN')+'/100 (activity, not safety/profit probability)',
        'Score components: '+json.dumps(result.get('components',{}),sort_keys=True),
        'WHY OF INTEREST / DECISION:']+['- '+x for x in result.get('reasons',[])]+['AVAILABLE SECURITY EVIDENCE:']
    for key in ('contract_security','sellability','holders','liquidity','tokenomics','contract_source','custody','nft_custody','supply_comparison','tokenized_stock_reference'):
        entry=(item.get('verification') or {}).get(key,{})
        lines.append('- '+key+': '+entry.get('status','UNKNOWN')+'; observed '+str(entry.get('observed_at','UNKNOWN'))+'; '+entry.get('reason','Unavailable'))
    if result.get('entry'):
        entry=result['entry'];lines+=['ENTRY WATCH: historical reference '+str(entry['entry_reference'])+'; observed invalidation '+str(entry['invalidation'])+'; candle UTC '+dt.datetime.fromtimestamp(entry['candle_at'],dt.timezone.utc).isoformat(), 'These are observed historical levels, not executable entry/stop orders. Targets: UNKNOWN.']
    if title=='VERIFIED BUY' and not example:
        quote=item.get('execution_evidence') or {}
        lines+=['EXECUTION AND RISK EVIDENCE: '+json.dumps({k:quote.get(k,'UNKNOWN') for k in ('provider','quote_id','amount_in','amount_out','expires_at','fees','slippage','entry','invalidation','risk')},sort_keys=True)]
    import project_context
    lines += [project_context.summary(item.get('project_context'), expected={'network':item.get('network'),'token_address':item.get('token_address')})]
    lines+=['EXACT MISSING MANDATORY CHECKS:']+['- '+x for x in missing]+['MAJOR RISKS:']+['- '+x for x in result.get('risks',[])]+['Research: '+str(item.get('url','UNKNOWN')),'Automated trading DISABLED. Recheck fresh evidence before any decision.']
    return '\n'.join(lines)


def format_admission_alert(item):
    """A fresh authenticated decision; caller-supplied classifications are ignored."""
    import authenticated_admission
    admission = authenticated_admission.evaluate(item)
    if not admission['safety_verified']:
        raise ValueError('Authenticated BUY admission unavailable or expired')
    lines = ['CRYPTO-ORACLE X100 — '+('BUY CANDIDATE — MANUAL REVIEW' if admission['admitted'] else 'WATCHLIST — SIGNED ENTRY MONITORING; NO BUY SIGNAL'),
             'Network: '+str(item['network']), 'Contract: '+str(item['token_address']),
             'Pool: '+str(item['address']), 'Discovery source: '+str(item.get('source','UNKNOWN'))[:160],
             'Independent reviewers: '+', '.join(admission['reviewers']),
             'Evidence SHA-256: '+admission['bundle_sha256'], 'Expires: '+admission['expires_at'],
             'Security/LP controls/beneficial ownership/tokenomics/sequential exit: PASS within signed review scope']
    for section, metrics in admission['summary'].items():
        lines.append(section.upper()+': '+json.dumps(metrics,sort_keys=True))
    lines += ['Signed risk budget is a planned reference, not guaranteed stop execution or a maximum possible loss.',
              'Price plan uses USD per whole token; public-book USDT is not assumed equal to USD.',
              'Final human approval is still required. Target and validated risk/reward: UNKNOWN.',
              'Unresolved mandatory evidence gaps: none within this signed review scope.',
              'Risks: entire allocation can be lost; liquidity, authority and prices can change. Simulation cannot guarantee future execution.',
              'Recheck evidence and quote expiration before manual action. Automatic trading DISABLED.']
    import project_context
    lines.append(project_context.summary(item.get('project_context'), expected={'network':item.get('network'),'token_address':item.get('token_address')}))
    message='\n'.join(lines)
    if len(message.encode('utf-16-le'))//2>4096:
        raise ValueError('Admission alert exceeds safe Telegram length')
    return message


def valuation(item):
    from decimal import Decimal
    e=item.get('verification') or {};supply=e.get('supply_comparison') or {}
    stock=e.get('tokenized_stock_reference') or {}
    try:
        if stock.get('status')=='LIMITED' and stock.get('metrics',{}).get('normalized_supply_matches_pinned') is True:
            total=Decimal(stock['metrics']['pinned_total_tokens'])
        elif supply.get('status')=='LIMITED' and (((supply.get('raw') or {}).get('observations') or {}).get('blockscout') or {}).get('matches_pinned_total') is True:
            raw=supply['raw'];total=Decimal(str(raw['total_supply_base_units'])+'e-'+str(raw['decimals']))
        else:raise ValueError('No reconciled supply')
        price=Decimal(str(item['base_token_price_usd']))
        if not price.is_finite() or price<=0 or not total.is_finite() or total<=0:raise ValueError('Invalid valuation input')
        return f'Indicative gross token valuation: USD {total*price:.8g} (reconciled supply × indicative price; circulating market cap and future FDV UNKNOWN)'
    except (KeyError,TypeError,ValueError,ArithmeticError):
        return 'Valuation: UNKNOWN — no independently reconciled circulating valuation'


def chunks(text,limit=3600):
    """Telegram limit is UTF-16 based; never truncate missing-check disclosures."""
    output=[];current=''
    for char in text:
        if len((current+char).encode('utf-16-le'))//2>limit:output.append(current);current=''
        current+=char
    if current:output.append(current)
    return [f'[{i+1}/{len(output)}] '+part for i,part in enumerate(output)]


def deliver(item,result,event,env,transport=telegram_validation.request,example=False,parts=None,completed=None,on_part=None):
    if not example:
        import canonical_outcomes
        verified = canonical_outcomes.assess(item)
        audit = evidence_audit.audit(item)
        if (verified.get('outcome') not in ('ENTRY WATCH', 'VERIFIED BUY')
                or verified.get('critical_gaps')
                or not (audit.get('trade_ready') is True or audit.get('admission', {}).get('safety_verified') is True)):
            raise RuntimeError('Individual alert withheld: critical evidence incomplete')
    token,chat=(env.get(k,'').strip() for k in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'))
    if not token or not chat:raise RuntimeError('Telegram destination or authentication missing')
    # Resolve destination once and require every message to return its ID.
    target=transport(token,'getChat',{'chat_id':chat})
    target_id=str((target.get('result') or {}).get('id',''))
    if target.get('ok') is not True or not target_id or (not chat.startswith('@') and chat!=target_id):raise RuntimeError('Telegram destination not confirmed')
    for index,text in enumerate(parts or chunks(format_alert(item,result,event,example))):
        if index in (completed or []):continue
        response=transport(token,'sendMessage',{'chat_id':chat,'text':text,'disable_web_page_preview':'true'})
        sent=response.get('result') or {}
        if response.get('ok') is not True or not sent.get('message_id') or str((sent.get('chat') or {}).get('id',''))!=target_id:raise RuntimeError('Telegram did not confirm destination delivery')
        if on_part:on_part(index)
    return True


def send_notification(item,result,notification,state,env,persist,transport=telegram_validation.request):
    """Persistent multipart outbox; only acknowledged parts are skipped on retry.

    Network acceptance before a process crash can still cause an at-least-once
    duplicate; Telegram offers no idempotency key. No false success is recorded.
    """
    record=state[item['key']]
    pending=record.get('pending_delivery') or {}
    if pending.get('fingerprint')!=notification['fingerprint']:
        pending=dict(fingerprint=notification['fingerprint'],parts=chunks(format_alert(item,result,notification['event'])),completed=[])
        record['pending_delivery']=pending
        persist()
    def confirmed(index):
        pending['completed'].append(index)
        persist()
    deliver(item,result,notification['event'],env,transport=transport,parts=pending['parts'],completed=pending['completed'],on_part=confirmed)
    acknowledge(state,item['key'],notification)
    record.pop('pending_delivery',None)
    persist()

