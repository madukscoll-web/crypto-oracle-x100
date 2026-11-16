"""Source-bound ATL research dossiers. No BUY or lifetime claim from provider ATL.

Live collection can establish a provider-ID/contract association and bounded
observed history. Neither establishes independently validated lifetime coverage.
The only live notification supported here is explicitly UNVERIFIED research.
"""
import datetime as dt
from decimal import Decimal
import hashlib
import html
import json
import re
from urllib.parse import urlsplit

from atl_monitor_core import positive, ATL_UNIVERSE_FLOOR
from telegram_receipts import confirmed

DETAILS = 'https://api.coingecko.com/api/v3/coins/'
MAX_AGE = 7200
EXCLUDED = ('stablecoin', 'wrapped', 'tokenized', 'tokenised', 'money market',
            'pegged', 'yield-bearing', 'liquid staking', 'liquid restaking')
NETWORKS = {'ethereum':'eth','binance-smart-chain':'bsc','base':'base',
            'arbitrum-one':'arbitrum','polygon-pos':'polygon_pos',
            'avalanche':'avax','optimistic-ethereum':'optimism','solana':'solana'}


def stamp(value):
    value = dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timezone required')
    return value.timestamp()


def fresh(value, now, maximum=MAX_AGE):
    try:return 0 <= now-stamp(value) <= maximum
    except (ValueError,TypeError,OverflowError):return False


def slug(value):
    if not isinstance(value,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,99}',value):
        raise ValueError('Exact provider asset identifier required')
    return value


def text(value):
    return ' '.join(str(value).split())[:160]


def identity(details, identifier):
    """Bind provider ID and reported platform contract, never infer from ticker."""
    if not isinstance(details,dict) or details.get('id') != slug(identifier):
        raise ValueError('Provider identity mismatch')
    platforms = details.get('platforms')
    if not isinstance(platforms,dict):
        raise ValueError('Exact platform metadata missing')
    contracts=[]
    for platform,contract in platforms.items():
        if not contract or platform not in NETWORKS:continue
        network=NETWORKS[platform]
        if network == 'solana':
            if not isinstance(contract,str) or not re.fullmatch('[1-9A-HJ-NP-Za-km-z]{32,44}',contract):
                raise ValueError('Malformed Solana identity')
        elif not isinstance(contract,str) or not re.fullmatch('0x[0-9a-fA-F]{40}',contract):
            raise ValueError('Malformed contract identity')
        contracts.append({'network':network,'contract':contract if network=='solana' else contract.lower()})
    return dict(provider_id=identifier,contracts=sorted(contracts,key=lambda x:(x['network'],x['contract'])),
                binding='PROVIDER_METADATA_ONLY',independently_verified=False)


def instrument(details):
    categories=details.get('categories')
    if not isinstance(categories,list) or not categories or any(not isinstance(x,str) for x in categories):
        return {'status':'UNKNOWN','reason':'Instrument categories unavailable'}
    hits=sorted({word for word in EXCLUDED for category in categories if word in category.casefold()})
    return dict(status='EXCLUDED' if hits else 'ORDINARY_CRYPTO_RESEARCH',
                reason=', '.join(hits) if hits else 'No excluded instrument category reported',
                categories=categories)


def history(raw, identifier, source_url, observed_at, now):
    """Validate bounded USD observations; never infer lifetime from chart length."""
    if source_url != DETAILS+slug(identifier)+'/market_chart?vs_currency=usd&days=365&interval=daily':
        raise ValueError('Unbound history source')
    if not fresh(observed_at,now):raise ValueError('Stale history retrieval')
    rows=raw.get('prices') if isinstance(raw,dict) else None
    if not isinstance(rows,list) or not 2 <= len(rows) <= 1000:
        raise ValueError('Missing bounded historical observations')
    points=[]
    for row in rows:
        if not isinstance(row,list) or len(row)!=2 or isinstance(row[0],bool):
            raise ValueError('Malformed historical price')
        at=positive(row[0]);price=positive(row[1])
        if at is None or price is None or at/1000 > Decimal(str(now)):
            raise ValueError('Invalid or future historical observation')
        points.append((at/1000,price))
    if any(b[0]<=a[0] for a,b in zip(points,points[1:])):
        raise ValueError('Duplicate or unordered history')
    if now-float(points[-1][0]) > MAX_AGE:raise ValueError('Stale historical endpoint')
    minimum=min(points,key=lambda x:x[1])
    return dict(provider_id=identifier,organization='coingecko',source_url=source_url,
        observed_at=observed_at,earliest_observation=dt.datetime.fromtimestamp(float(points[0][0]),dt.timezone.utc).isoformat(),
        latest_observation=dt.datetime.fromtimestamp(float(points[-1][0]),dt.timezone.utc).isoformat(),
        minimum_price_usd=str(minimum[1]),minimum_at=dt.datetime.fromtimestamp(float(minimum[0]),dt.timezone.utc).isoformat(),
        points=len(points),maximum_gap_seconds=str(max(b[0]-a[0] for a,b in zip(points,points[1:]))),
        coverage='DAILY_SAMPLES_LIMITED_TO_365_DAYS',lifetime_complete=False,
        limitation='Daily samples omit intraday lows; the available range does not prove lifetime coverage.')


def independent_history(histories):
    """Reconcile observed minima without allowing caller completeness booleans.

    Independent organizations and point-in-time exact-contract histories plus
    inception/redenomination evidence are required before lifetime certification.
    This reconciler never certifies such absent evidence from precomputed flags.
    """
    result=dict(status='UNVERIFIED',lifetime_verified=False,independent_sources=0,
                conflicting=False,earliest_observation=None,minima=[],
                gaps=['Independently sourced exact-contract full trading history required',
                      'First-trade/inception provenance and venue coverage required',
                      'Migration, redenomination and split inventory/reconciliation required',
                      'Intraday low coverage and independent circulating supply required'])
    if not isinstance(histories,list):raise ValueError('History list required')
    organizations=set();identifiers=set();values=[]
    for item in histories:
        if not isinstance(item,dict):raise ValueError('Malformed history assessment')
        if item.get('organization') not in ('coingecko','gate'):
            raise ValueError('Unknown historical organization')
        url=urlsplit(item.get('source_url',''))
        if (url.scheme!='https' or url.hostname not in ('api.coingecko.com','api.gateio.ws')
                or url.username or url.password):raise ValueError('Untrusted historical provenance')
        organizations.add(item['organization']);identifiers.add(item['provider_id'])
        low=positive(item.get('minimum_price_usd'))
        if low is None:raise ValueError('Invalid history minimum')
        values.append(low);result['minima'].append({'source_url':item['source_url'],'minimum_price_usd':str(low)})
        earliest=item['earliest_observation'];stamp(earliest)
        if result['earliest_observation'] is None or stamp(earliest)<stamp(result['earliest_observation']):
            result['earliest_observation']=earliest
    if len(identifiers)>1:raise ValueError('Historical asset identity conflict')
    result['independent_sources']=len(organizations)
    result['conflicting']=bool(values and max(values)/min(values)>Decimal('1.05'))
    if result['conflicting']:result['status']='CONFLICTING'
    return result


def gate_listing(asset, evidence, now):
    """Exact contract join, never ticker matching or native/wrapped aliasing."""
    from asset_identity import key, GATE_CHAINS
    if not isinstance(evidence,dict) or not fresh(evidence.get('observed_at'),now,900):
        return dict(status='UNVERIFIED',reason='Fresh Gate metadata unavailable',pairs=[])
    contracts={key(x['network'],x['contract']) for x in asset['contracts']}
    currencies=evidence.get('currencies');pairs=evidence.get('pairs')
    if not isinstance(currencies,list) or not isinstance(pairs,list):
        return dict(status='UNVERIFIED',reason='Gate metadata malformed',pairs=[])
    matched=[]
    for currency in currencies:
        if not isinstance(currency,dict) or currency.get('delisted') is not False or currency.get('trade_disabled') is not False:continue
        bound=set()
        for chain in currency.get('chains') or []:
            if not isinstance(chain,dict):continue
            network=GATE_CHAINS.get(chain.get('name'))
            if network and chain.get('addr'):
                try:bound.add(key(network,chain['addr']))
                except ValueError:continue
        if not bound & contracts:continue
        for pair in pairs:
            if (isinstance(pair,dict) and pair.get('base')==currency.get('currency')
                    and pair.get('quote')=='USDT' and pair.get('id')==str(currency.get('currency'))+'_USDT'
                    and pair.get('trade_status')=='tradable' and pair.get('type')=='normal'
                    and pair.get('st_tag') is False and pair.get('delisting_time') in (None,0)):
                matched.append(pair['id'])
    matched=sorted(set(matched))
    return dict(status='EXACT_CONTRACT_METADATA_MATCH' if len(matched)==1 else 'UNVERIFIED',
                pairs=matched,source_urls=['https://api.gateio.ws/api/v4/spot/currencies','https://api.gateio.ws/api/v4/spot/currency_pairs'],reason='Provider metadata contract join; not independent security' if len(matched)==1 else 'Missing or ambiguous exact-contract Gate spot mapping')


def dossier(observation,details,chart,*,observed_at,now,gate_evidence=None,venue=None,onchain=None):
    identifier=slug(observation['provider_id'])
    if not fresh(observed_at,now) or not fresh(observation['provider_last_updated'],now):
        raise ValueError('Stale market or metadata evidence')
    asset=identity(details,identifier);kind=instrument(details)
    market=details.get('market_data') or {}
    if not fresh(market.get('last_updated') or details.get('last_updated'),now):
        raise ValueError('Stale details market evidence')
    price,cap,supply=(positive(market.get(k,{}).get('usd') if k!='circulating_supply' else market.get(k))
                      for k in ('current_price','market_cap','circulating_supply'))
    if None in (price,cap,supply) or cap<ATL_UNIVERSE_FLOOR or abs(cap-price*supply)/cap>Decimal('.05'):
        raise ValueError('Invalid circulating market cap observation')
    if abs(price/positive(observation['indicative_price_usd'])-1)>Decimal('.05'):
        raise ValueError('Market/detail price conflict')
    lead=observation.get('provider_atl_candidate')
    if not isinstance(lead,dict) or positive(lead.get('source_atl_usd')) is None:
        raise ValueError('Provider low discovery lead missing')
    low=positive(lead['source_atl_usd']);percent=(price/low-1)*100
    try:
        low_at=stamp(lead.get('source_atl_date'))
    except (ValueError,TypeError,OverflowError) as exc:
        raise ValueError('Invalid provider ATL date') from exc
    if low_at > stamp(observation['provider_last_updated']):
        raise ValueError('Future provider ATL date')
    if percent < -5:
        raise ValueError('Current price materially below provider ATL; reconciliation required')
    if percent>5:raise ValueError('No longer near provider low')
    assessments=[];gaps=[]
    try:
        assessments=[history(chart,identifier,DETAILS+identifier+'/market_chart?vs_currency=usd&days=365&interval=daily',observed_at,now)]
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        gaps.append(str(exc))
    historical=independent_history(assessments)
    # Compare daily-range minima with the separately reported provider lifetime low.
    # A higher daily minimum is expected for partial history, never corroboration.
    historical['provider_reported_low_usd']=str(low)
    historical['provider_reported_low_at']=lead.get('source_atl_date')
    if assessments and positive(assessments[0]['minimum_price_usd']) < low*Decimal('.95'):
        historical['status']='CONFLICTING';historical['conflicting']=True
        gaps.append('Observed historical minimum conflicts with provider ATL')
    eligible=(kind['status']=='ORDINARY_CRYPTO_RESEARCH' and bool(asset['contracts'])
              and (bool(assessments) or chart == {}) and not historical['conflicting'])
    gaps+=historical['gaps']+['On-chain contract identity/security not independently verified',
         'Executable liquidity and order-book depth not verified']
    if not asset['contracts']:gaps.append('Supported exact-contract representation unavailable')
    if isinstance(gate_evidence,dict):
        # Retain only exact matching metadata, not whole exchange catalogs per dossier.
        from asset_identity import GATE_CHAINS, key
        wanted={key(x['network'],x['contract']) for x in asset['contracts']}
        currencies=[]
        for currency in gate_evidence.get('currencies',[]) if isinstance(gate_evidence.get('currencies'),list) else []:
            if not isinstance(currency,dict):continue
            for chain in currency.get('chains') or []:
                if not isinstance(chain,dict):continue
                network=GATE_CHAINS.get(chain.get('name'))
                if network is None:continue
                try:match=key(network,chain.get('addr')) in wanted
                except (ValueError,TypeError):match=False
                if match:currencies.append(currency);break
        names={c.get('currency') for c in currencies}
        gate_evidence=dict(observed_at=gate_evidence.get('observed_at'),currencies=currencies,
            pairs=[p for p in gate_evidence.get('pairs',[]) if isinstance(p,dict) and p.get('base') in names] if isinstance(gate_evidence.get('pairs'),list) else [])
    listing=gate_listing(asset,gate_evidence,now)
    if gate_evidence is not None and listing['status']!='EXACT_CONTRACT_METADATA_MATCH':
        eligible=False;gaps.append(listing['reason'])
    venue_block=None;verified=[]
    if venue is not None:
        # Venue evidence is informational: it can only withhold (a lower traded
        # price than the claimed ATL), never grant eligibility, BUY or orders.
        try:
            import gate_history
            if listing['status']!='EXACT_CONTRACT_METADATA_MATCH' or len(listing['pairs'])!=1:
                raise ValueError('No single exact Gate pair')
            gate_history.validate(venue,listing['pairs'][0],now)
            venue_block=venue
            if gate_history.below_reported_low(venue['history'],low):
                historical['conflicting']=True;historical['status']='CONFLICTING';eligible=False
                gaps.append('Gate venue traded below the provider-reported ATL; provider ATL not corroborated')
            elif not gate_history.covers_date(venue['history'],low_at):
                gaps.append('Gate venue history begins after the provider-reported low date; low not checked on Gate')
            intraday=venue.get('intraday')
            if intraday is not None:
                if intraday['day']!=dt.datetime.fromtimestamp(low_at,dt.timezone.utc).date().isoformat():
                    raise ValueError('Venue intraday day does not match the provider low date')
                if Decimal(intraday['minimum_price_usd'])<low*Decimal('.95'):
                    historical['conflicting']=True;historical['status']='CONFLICTING';eligible=False
                    gaps.append('Gate hourly candles on the provider low date traded below the provider ATL; not corroborated')
                else:
                    verified.append('Gate hourly low on the provider low date: '+intraday['minimum_price_usd']+' USDT ('
                        +str(intraday['hours_covered'])+'/24 hours covered); not below the provider low')
        except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
            venue_block=None   # rejected evidence is not displayed or trusted
            gaps.append('Gate venue history rejected: '+str(exc)[:120])
    onchain_block=None
    if onchain is not None:
        # On-chain facts can only withhold; they never grant eligibility or BUY.
        try:
            import atl_onchain
            entries=atl_onchain.validate(onchain,asset,now)
            onchain_block=entries
            proven=[e for e in entries if e['identity']=='VERIFIED']
            for e in proven:verified.extend(e['facts'])
            if proven:
                gaps[:]=[g for g in gaps if g!='On-chain contract identity/security not independently verified']
                gaps.append('On-chain security review incomplete: pool/liquidity controls, holder concentration and sell route not verified')
            for e in entries:
                if e['security_status']=='FAIL':
                    eligible=False;gaps.append('On-chain red flag: '+e['security_reason'])
            if len(entries)==1 and entries[0]['total_supply'] and len(asset['contracts'])==1:
                if supply>Decimal(entries[0]['total_supply'])*Decimal('1.01'):
                    eligible=False;gaps.append('Provider circulating supply exceeds on-chain total supply; conflict')
        except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
            onchain_block=None
            gaps.append('On-chain evidence rejected: '+str(exc)[:120])
    if venue_block is not None and venue_block.get('intraday') is not None:
        gaps[:]=[('Independent circulating supply (vesting and unlocks) required' if g=='Intraday low coverage and independent circulating supply required' else g) for g in gaps]
    digest=hashlib.sha256(json.dumps({'identity':asset,'low':str(low),'type':kind['status']},sort_keys=True).encode()).hexdigest()
    return dict(schema_version=1,classification='UNVERIFIED ATL RESEARCH WATCH',
        name=text(details.get('name','UNKNOWN')),symbol=text(details.get('symbol','UNKNOWN')),
        asset=asset,instrument=kind,gate_listing=listing,observed_at=observed_at,price_usd=str(price),
        circulating_market_cap_usd=str(cap),market_cap_status='PROVIDER_REPORTED_NOT_INDEPENDENTLY_VERIFIED',
        percent_above_provider_low=str(percent),provider_low_usd=str(low),
        provider_low_at=lead['source_atl_date'],
        evidence_class='PROVIDER_REPORTED_ATL_NOT_CORROBORATED',
        volume_24h_usd=str(positive((market.get('total_volume') or {}).get('usd')) or 'UNKNOWN'),
        liquidity_status='UNKNOWN',history=historical,historical_assessments=assessments,gaps=gaps,
        source_urls=[DETAILS+identifier]+[x['source_url'] for x in assessments]+listing.get('source_urls',[])+(venue_block['history']['source_urls'][:1] if venue_block else []),
        venue_history=venue_block,onchain_evidence=onchain_block,verified_facts=verified,
        telegram_research_eligible=eligible,evidence_fingerprint=digest,
        buy_authorized=False,orders_allowed=False,
        _source_input=dict(observation=observation,details=details,chart=chart,observed_at=observed_at,gate_evidence=gate_evidence,venue=venue,onchain=onchain))


def distance_text(percent):
    value=Decimal(percent)
    if value<0:
        return format(abs(value),'.2f')+'% BELOW the recorded low (price is at or under it; a fresh low is possible)'
    return format(value,'.2f')+'% above the low (how far price has risen from it)'


HUMAN_REQUIRED=('Independently sourced exact-contract full trading history','First-trade/inception provenance',
                'Migration, redenomination','circulating supply')


def venue_text(d):
    """Plain-text Gate venue lines; empty when no validated venue evidence."""
    v=d.get('venue_history')
    if not v:return ''
    h=v['history'];b=v.get('book')
    try:
        above=(Decimal(d['price_usd'])/Decimal(h['minimum_price_usd'])-1)*100
        above_text=format(above,'+.2f')+'%'
    except (ValueError,ArithmeticError,KeyError):above_text='unknown'
    text=('Gate venue history: '+str(h['candles'])+' daily candles from '+h['earliest_candle_at'][:10]
          +('' if h.get('reaches_first_candle') else ' (truncated)')+'; lowest daily low '+h['minimum_price_usd']
          +' USDT on '+h['minimum_at'][:10]+'; price is '+(above_text[1:]+' below it' if above_text.startswith('-') else above_text+' above it')+'. Venue only; not a verified lifetime low.\n')
    if b:
        text+=('Gate book: spread '+b['spread_bps']+' bps; depth within 1% bid/ask '+b['bid_depth_usdt_1pct']+'/'
               +b['ask_depth_usdt_1pct']+' USDT (top '+str(b['levels_read'])+' levels, lower bound).\n')
    return text


def format_research(d):
    # Hardcoded classification: no caller label, Boolean or provider ATL grants BUY.
    contracts='; '.join(x['network']+':'+x['contract'] for x in d['asset']['contracts'])
    return ('UNVERIFIED ATL RESEARCH WATCH\nNOT A VERIFIED ALL-TIME LOW. NOT A BUY SIGNAL.\n'
        +text(d['name'])+' ('+text(d['symbol'])+')\n'+contracts+'\n'
        +'Gate spot mapping: '+', '.join(d['gate_listing']['pairs'])+' ('+d['gate_listing']['status']+')\n'
        +'Identity source: CoinGecko platform metadata; independent chain verification pending.\n'
        +'Observed USD price: '+d['price_usd']+' at '+d['observed_at']+'\n'
        +'Circulating market cap USD: '+d['circulating_market_cap_usd']+' (provider reported; unverified)\n'
        +'Provider-reported low USD: '+d['provider_low_usd']+' at '+d['provider_low_at']+'; above low: '+d['percent_above_provider_low']+'%\n'
        +venue_text(d)
        +'24h volume USD: '+d['volume_24h_usd']+'; executable liquidity: UNKNOWN\n'
        +('Historical coverage: '+text(d['history']['earliest_observation'])+' onward; daily samples, limited to 365 days.\n' if d['historical_assessments'] else 'Historical coverage: unavailable; provider-reported ATL only.\n')
        +'Technical reversal, entry, invalidation and targets: NOT ESTABLISHED.\n'
        +'Security, tokenomics and fundamentals: NOT VERIFIED. Full loss is possible.\n'
        +'Missing: '+'; '.join(d['gaps'])+'\nSources: '+'\n'.join(d['source_urls']))


def format_research_html(d,compact=False):
    """Escape provider text; preserve values and full dates without claiming BUY."""
    escape=lambda value: html.escape(str(value),quote=True)
    def money(value):
        number=positive(value)
        return '$'+format(number,',f') if number is not None else 'Unknown'
    def date(value):
        return dt.datetime.fromtimestamp(stamp(value),dt.timezone.utc).strftime('%d %b %Y %H:%M UTC')
    venue=d.get('venue_history') or {}
    venue_lines=[];depth_text='Unknown'
    if venue.get('history'):
        h=venue['history'];b=venue.get('book')
        try:above=distance_text((Decimal(d['price_usd'])/Decimal(h['minimum_price_usd'])-1)*100).replace('the recorded low','the lowest closed daily low').replace('(price is at or under it; a fresh low is possible)','(a new venue low today)').replace('above the low (how far price has risen from it)','above the lowest closed daily low')
        except (ValueError,ArithmeticError,KeyError):above='Unknown'
        venue_lines=['', '📜 <b>Gate Venue History</b>',
            '• <b>Coverage:</b> '+str(h['candles'])+' daily candles from '+escape(h['earliest_candle_at'][:10])
                +('' if h.get('reaches_first_candle') else ' (truncated)')+' (Gate spot only)',
            '• <b>Lowest Daily Low:</b> '+money(h['minimum_price_usd'])+' on '+escape(h['minimum_at'][:10]),
            '• <b>Distance From Venue Low:</b> '+above,
            '• <b>Note:</b> Venue-only history; not a verified lifetime all-time low.']
        if b:
            depth_text=('Gate book bid $'+format(Decimal(b['bid_depth_usdt_1pct']),',f')+' / ask $'
                        +format(Decimal(b['ask_depth_usdt_1pct']),',f')+' within 1% (top '+str(b['levels_read'])
                        +' levels, lower bound); spread '+escape(b['spread_bps'])+' bps')
    lines=['🚨 <b>ALL-TIME LOW WATCH</b>',
        '<i>Unverified ATL Research Watch</i>',
        '⚠️ <b>NOT A VERIFIED ALL-TIME LOW • NOT A BUY SIGNAL</b>',
        *([] if compact else ['', '🧭 <b>In Plain English</b>',
        escape(d['name'])+' is trading close to the lowest price its data provider has on record. '
        'That does not prove it is the true all-time low, and it does not mean the price will rise. '
        'Research alert only; the bot has bought nothing and nothing is required from you.']),
        '', '<b>Token Identity</b>',
        '• <b>Asset:</b> '+escape(d['name'])+' ('+escape(d['symbol'].upper())+')']
    names={'eth':'Ethereum','bsc':'BNB Smart Chain','solana':'Solana','base':'Base',
           'arbitrum':'Arbitrum','polygon_pos':'Polygon','avax':'Avalanche','optimism':'Optimism'}
    for contract in d['asset']['contracts']:
        lines+=['• <b>Chain:</b> '+escape(names.get(contract['network'],contract['network'])),
                '• <b>Contract:</b> <code>'+escape(contract['contract'])+'</code>']
    lines+=['• <b>Mapping:</b> '+escape(', '.join(d['gate_listing']['pairs']) or 'Unverified')+' (Gate Spot metadata)',
        '• <b>Identity source:</b> CoinGecko metadata; independent chain verification pending.',
        '', '📊 <b>Market Data</b>',
        '• <b>Observed Price:</b> '+money(d['price_usd'])+' ('+date(d['observed_at'])+')',
        '• <b>Provider Low:</b> '+money(d['provider_low_usd'])+' ('+date(d['provider_low_at'])+')',
        '• <b>Distance From Low:</b> '+distance_text(d['percent_above_provider_low']),
        '• <b>24h Volume:</b> '+money(d['volume_24h_usd'])+' (provider reported)',
        '• <b>Circulating Market Cap:</b> '+money(d['circulating_market_cap_usd'])+' (unverified)',
        '• <b>Liquidity Depth:</b> '+depth_text,
        *venue_lines,
        '', '⚙️ <b>Technical &amp; Risk Assessment</b>',
        ('• <b>Historical Coverage:</b> Daily samples from '+date(d['history']['earliest_observation'])+'; bounded 365-day request, not full lifetime.' if d['historical_assessments'] else '• <b>Historical Coverage:</b> Unavailable; provider-reported ATL only.'),
        '• <b>Technical Setup:</b> Entry / invalidation / targets NOT established.',
        '• <b>Security &amp; Fundamentals:</b> NOT verified. High risk / full loss possible.',
        ]
    if d.get('verified_facts'):
        lines+=['', '✅ <b>Checked by the bot</b>']+['• '+escape(fact) for fact in d['verified_facts']]
    human=[g for g in d['gaps'] if any(k in g for k in HUMAN_REQUIRED)]
    other=[g for g in d['gaps'] if g not in human]
    if human:
        lines+=['', '🙋 <b>Needs a human to confirm</b> (the bot will not guess these)']+['• '+escape(g) for g in human]
        lines+=['<i>These clear only when sourced evidence is added to the ATL registry.</i>']
    if other:
        lines+=['', '❗ <b>Not verified yet</b>']+['• '+escape(g) for g in other]
    lines+=['', '<b>Sources</b>']+[escape(url) for url in d['source_urls']]
    return '\n'.join(lines)


REPEAT_COOLDOWN_DAYS=7
REPEAT_DROP_PERCENT=10


def repeat_guard(previous,low,now):
    """Decide whether a fresh low for an already-alerted asset may be sent again.

    Returns None (first alert for this asset), the previous record (repeat allowed:
    the low fell a further REPEAT_DROP_PERCENT or the cooldown expired), or
    'SUPPRESS'. A corrupt record suppresses rather than re-alerts (fail-closed).
    """
    if previous is None:
        return None
    try:
        sent=dt.datetime.fromisoformat(str(previous['at']).replace('Z','+00:00'))
        if sent.tzinfo is None:return 'SUPPRESS'
        previous_low=Decimal(str(previous['low']));current_low=Decimal(str(low))
        if previous_low<=0 or current_low<=0:return 'SUPPRESS'
    except (KeyError,TypeError,ValueError,ArithmeticError):
        return 'SUPPRESS'
    if now-sent.timestamp()>=REPEAT_COOLDOWN_DAYS*86400:
        return previous
    if current_low<=previous_low*(1-Decimal(REPEAT_DROP_PERCENT)/100):
        return previous
    return 'SUPPRESS'


def notify(dossiers,state,env,transport,*,now):
    """Up to three distinct unverified research messages/day, confirmed Bot API receipts.

    Evidence qualification remains research-only. Failed receipts never advance
    dedup state. Caller persists returned state with the serialized scanner state.
    """
    day=dt.datetime.fromtimestamp(now,dt.timezone(dt.timedelta(hours=1))).date().isoformat()
    delivery=dict(delivered=0,failed=0,status='NO_ELIGIBLE_RESEARCH',buy_authorized=False,decisions=[])
    decisions=delivery['decisions']
    def receipt_day(receipt):
        try:
            stamp=dt.datetime.fromisoformat(receipt['at'].replace('Z','+00:00'))
            return stamp.astimezone(dt.timezone(dt.timedelta(hours=1))).date().isoformat() if stamp.tzinfo else None
        except (KeyError,TypeError,ValueError,AttributeError):
            return None
    confirmed_today=sum(receipt_day(receipt)==day for receipt in state.get('research_confirmed',{}).values()
                        if isinstance(receipt,dict))
    if confirmed_today>=3:
        delivery['status']='DAILY_LIMIT'
        decisions.extend(dict(provider_id=x.get('asset',{}).get('provider_id'),status='DAILY_LIMIT') for x in dossiers if isinstance(x,dict))
        return delivery
    for supplied in dossiers:
        decision=dict(provider_id=supplied.get('asset',{}).get('provider_id') if isinstance(supplied,dict) else None,status='WITHHELD')
        decisions.append(decision)
        try:
            source=supplied['_source_input']
            d=dossier(source['observation'],source['details'],source['chart'],
                      observed_at=source['observed_at'],now=now,gate_evidence=source.get('gate_evidence'),venue=source.get('venue'),onchain=source.get('onchain'))
        except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
            decision.update(status='REPLAY_FAILED',reason=str(exc)[:200])
            continue
        if (d.get('classification')!='UNVERIFIED ATL RESEARCH WATCH'
                or d.get('telegram_research_eligible') is not True
                or d.get('buy_authorized') is not False or d.get('orders_allowed') is not False
                or not fresh(d.get('observed_at'),now)
                or d.get('instrument',{}).get('status')!='ORDINARY_CRYPTO_RESEARCH'
                or d.get('history',{}).get('conflicting') is not False):
            decision.update(status='EVIDENCE_WITHHELD',reason='; '.join(d['gaps']));continue
        # Re-read durable prior warnings at send time; outages cannot clear them.
        try:
            import technical_watch
            retained=technical_watch.retained_negatives(json.loads((technical_watch.ROOT/'technical_watch_state.json').read_text()))
            from asset_identity import key
            if any(key(x['network'],x['contract']) in retained for x in d['asset']['contracts']):
                delivery['status']='WITHHELD_RETAINED_ADVERSE';decision['status']=delivery['status'];continue
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            delivery['status']='ADVERSE_STATE_UNAVAILABLE';decision['status']=delivery['status'];continue
        fingerprint=d['evidence_fingerprint']
        if fingerprint in state.get('research_confirmed',{}):
            decision['status']='UNCHANGED_CONFIRMED_CONDITION';continue
        # A coin in a steady decline sets a slightly lower provider low every day or
        # two, which changes the fingerprint. Re-alert the same asset only after a
        # further material drop or a full cooldown, so one falling coin cannot
        # monopolise the feed. This only suppresses repeats; it never admits an alert.
        asset_id=str(d['asset'].get('provider_id'))
        previous=repeat_guard(state.get('research_last_by_asset',{}).get(asset_id),d['provider_low_usd'],now)
        if previous=='SUPPRESS':
            decision.update(status='REPEAT_COOLDOWN',reason='Same asset alerted within '+str(REPEAT_COOLDOWN_DAYS)
                            +' days and the low has not fallen a further '+str(REPEAT_DROP_PERCENT)+'%');continue
        token,chat=(env.get(k,'').strip() for k in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'))
        if not token or not chat:
            delivery['status']='TRANSPORT_NOT_CONFIGURED';decision['status']=delivery['status'];return delivery
        try:
            target=transport(token,'getChat',{'chat_id':chat})
            result=target.get('result') or {};destination=result.get('id')
            if (target.get('ok') is not True or type(destination) is not int or destination==0
                    or (not chat.startswith('@') and str(destination)!=chat)
                    or (chat.startswith('@') and '@'+str(result.get('username','')).casefold()!=chat.casefold())):
                raise ValueError('Destination not confirmed')
            from research_notice import _issue, verified_text
            message=verified_text(_issue('UNVERIFIED ATL RESEARCH WATCH',format_research(d).split('\n',1)[1]))
            # Only the freshly replayed, capability-checked dossier reaches HTML.
            message=format_research_html(d)
            if len(message.encode('utf-16-le'))//2>3900:
                message=format_research_html(d,compact=True)   # drop the plain-English block rather than lose the alert
            if previous is not None:
                message+=('\n\n🔁 <b>Repeat alert:</b> last sent '+html.escape(str(previous['at'])[:10])+' when the low was $'
                          +html.escape(str(previous['low']))+'. The low has since fallen a further '+str(REPEAT_DROP_PERCENT)
                          +'%+ or '+str(REPEAT_COOLDOWN_DAYS)+' days have passed.')
            if len(message.encode('utf-16-le'))//2>3900:raise ValueError('Research message too long')
            receipt=transport(token,'sendMessage',{'chat_id':chat,'text':message,'parse_mode':'HTML','disable_web_page_preview':'true'})
            if not confirmed(receipt,str(destination)):raise ValueError('Delivery not confirmed')
            state['research_confirmed_day']=day
            state.setdefault('research_confirmed',{})[fingerprint]=dict(at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),message_id=receipt['result']['message_id'])
            # Bound state without forgetting recent confirmed conditions.
            state['research_confirmed']=dict(list(state['research_confirmed'].items())[-200:])
            state.setdefault('research_last_by_asset',{})[asset_id]=dict(
                at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),low=str(d['provider_low_usd']))
            state['research_last_by_asset']=dict(list(state['research_last_by_asset'].items())[-200:])
            delivery.update(delivered=1,status='BOT_API_CONFIRMED',message_id=receipt['result']['message_id'])
            decision.update(status='BOT_API_CONFIRMED',message_id=receipt['result']['message_id'])
            return delivery
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,AttributeError):
            delivery.update(failed=1,status='DELIVERY_FAILED');decision['status']=delivery['status'];return delivery
    return delivery
