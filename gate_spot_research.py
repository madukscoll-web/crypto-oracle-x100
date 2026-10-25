"""Gate public Spot metadata/books/candles only. No account or order methods.

Docs: https://www.gate.com/docs/developers/apiv4/en/spot/
https://www.gate.com/docs/developers/apiv4/en/wallet/
"""
import datetime as dt
import re
from decimal import Decimal,InvalidOperation,localcontext,ROUND_FLOOR
from urllib.parse import urlencode,quote
from asset_identity import key,GATE_CHAINS

BASE='https://api.gateio.ws/api/v4'


def decimal(value,zero=False):
    if value is None or isinstance(value,bool):raise ValueError('Missing decimal')
    try:result=Decimal(str(value))
    except InvalidOperation as exc:raise ValueError('Invalid decimal') from exc
    if not result.is_finite() or result<0 or (result==0 and not zero):raise ValueError('Invalid measurement')
    return result


def integer(value):
    if type(value) is not int or value<0:raise ValueError('Explicit nonnegative integer required')
    return value


class PublicGate:
    def __init__(self,fetch):self.fetch=fetch;self.evidence=[]
    def get(self,path,query=None):
        # No arbitrary URLs, private account methods, order requests or mutation.
        if not (path in ('/spot/currencies','/spot/currency_pairs','/spot/order_book','/spot/candlesticks','/wallet/currency_chains') or re.fullmatch(r'/spot/currency_pairs/[A-Z0-9_.-]+_[A-Z0-9_.-]+',path)):
            raise ValueError('Outside public read-only research endpoints')
        url=BASE+path+('?' +urlencode(query) if query else '')
        raw=self.fetch(url);self.evidence.append(dict(url=url,retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),provider_timestamp='UNKNOWN unless supplied in raw response',raw=raw));return raw
    def catalog(self):
        # Publish identity metadata atomically: a malformed/partial reload must
        # never leave a usable half-built uniqueness index.
        for name in ('index','catalog_at'):
            if hasattr(self,name):delattr(self,name)
        self.currencies=self.get('/spot/currencies');self.pairs=self.get('/spot/currency_pairs')
        if not isinstance(self.currencies,list) or not isinstance(self.pairs,list):raise ValueError('Invalid catalog')
        index={}
        for currency in self.currencies:
            if not isinstance(currency,dict) or not isinstance(currency.get('currency'),str):raise ValueError('Malformed currency metadata')
            for chain in currency.get('chains') or []:
                if not isinstance(chain,dict) or not isinstance(chain.get('name'),str):raise ValueError('Malformed chain metadata')
                network=GATE_CHAINS.get(chain.get('name'))
                if not network or not chain.get('addr'):continue
                try:identity=key(network,chain['addr'])
                except ValueError:continue
                index.setdefault(identity,[]).append(currency)
        if any(not isinstance(p,dict) or not isinstance(p.get('id'),str) for p in self.pairs):raise ValueError('Malformed pair catalog')
        self.index=index;self.catalog_at=dt.datetime.now(dt.timezone.utc).timestamp()
        return dict(currency_records=len(self.currencies),spot_pair_records=len(self.pairs),
            normal_tradable_pairs=sum(p.get('type')=='normal' and p.get('trade_status')=='tradable' for p in self.pairs),
            exact_contract_keys=len(self.index),retrieved_at=self.catalog_at,listing_time_semantics='First observation is not a new listing; buy_start/sell_start are exchange-provided activation times')
    def eligibility(self,asset,now=None):
        now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
        result=dict(status='UNKNOWN',market='GATE SPOT ONLY',reason='Exact contract-to-Spot eligibility not established',raw=None)
        try:
            if not 0<=now-self.catalog_at<=300:raise ValueError('Catalog stale/future')
            matches=self.index.get(key(asset['network'],asset['token_address']),[])
            currencies={c['currency']:c for c in matches}
            if len(currencies)!=1:
                result['reason']='No exact contract match in the bounded Spot catalog' if not currencies else 'Ambiguous exchange currency identities for this exact contract'
                return result
            currency=next(iter(currencies.values()));symbol=currency['currency']
            if not re.fullmatch('[A-Z0-9_.-]{1,64}',symbol):raise ValueError('Unsupported exchange currency code')
            if currency.get('delisted') is not False or currency.get('trade_disabled') is not False:raise ValueError('Currency delisted, trading disabled or status UNKNOWN')
            chains=self.get('/wallet/currency_chains',{'currency':symbol})
            bound=[]
            for chain in chains:
                network=GATE_CHAINS.get(chain.get('chain'))
                if network!=asset['network'] or not chain.get('contract_address'):continue
                try:
                    if key(network,chain['contract_address'])==asset['asset_key']:bound.append(chain)
                except ValueError:continue
            if len(bound)!=1:
                result.update(status='CONFLICTING',reason='Spot catalog contract and wallet-chain contract evidence do not uniquely agree',raw=dict(currency=currency,chains=chains));return result
            if type(bound[0].get('is_disabled')) is not int or bound[0]['is_disabled']!=0:raise ValueError('Exact transfer network disabled or UNKNOWN')
            # Symbol is used only after exact chain/contract binding, never as a join.
            pair_id=symbol+'_USDT'
            rows=[p for p in self.pairs if p.get('id')==pair_id and p.get('base')==symbol and p.get('quote')=='USDT']
            if len(rows)!=1:raise ValueError('Exact USDT Spot pair absent/ambiguous')
            pair=self.get('/spot/currency_pairs/'+quote(pair_id,safe=''))
            if pair.get('id')!=pair_id or pair.get('base')!=symbol or pair.get('quote')!='USDT':raise ValueError('Pair identity conflict')
            if pair.get('type')!='normal' or pair.get('trade_status')!='tradable':raise ValueError('Not a normal, two-way tradable Spot pair (premarket/futures/Web3/Trenches not eligible)')
            if any(integer(pair.get(k))>now for k in ('buy_start','sell_start')):raise ValueError('Spot trading not yet active')
            if pair.get('delisting_time') is not None and integer(pair['delisting_time'])>0:raise ValueError('Delisting scheduled; research eligibility blocked')
            if pair.get('st_tag') is not False:raise ValueError('ST risk tag active or UNKNOWN')
            result.update(status='CONFIRMED_SPOT',reason='Exchange Spot metadata and wallet-chain exact contract agree; normal two-way pair active',
                pair_id=pair_id,raw=dict(currency=currency,chain=bound[0],pair=pair),
                account_eligibility='UNKNOWN',transfer_status={k:bound[0].get(k,'UNKNOWN') for k in ('is_deposit_disabled','is_withdraw_disabled')})
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
            result['reason']=str(exc) if isinstance(exc,ValueError) else 'Public exchange evidence unavailable: '+type(exc).__name__
            result['diagnostic']=dict(error_type=type(exc).__name__,http_status=getattr(exc,'code',None))
        return result
    def research(self,eligibility,quote_notional='100',excluded=False,now=None):
        supplied_now=now
        now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
        result=dict(status='BLOCKED',orders_allowed=False,automated_trading_enabled=False,
            reason='Exact Spot eligibility required',fees='UNKNOWN (account-specific rates require authenticated read access; no credentials requested)')
        if eligibility.get('status')!='CONFIRMED_SPOT':return result
        try:
            pair=eligibility['raw']['pair'];identifier=eligibility['pair_id']
            candles=self.get('/spot/candlesticks',dict(currency_pair=identifier,interval='5m',limit=30))
            book=self.get('/spot/order_book',dict(currency_pair=identifier,limit=20,with_id='true'))
            observed=dt.datetime.now(dt.timezone.utc).timestamp() if supplied_now is None else supplied_now
            metrics=analyze_book(book,quote_notional,observed);history=analyze_candles(candles,observed)
            result.update(status='LIMITED',reason='Public snapshots only; no funded execution/account eligibility or future fill proof',
                pair_id=identifier,book=metrics,history=history,public_pair_fee_percent=str(decimal(pair['fee'],zero=True)),fee_scope='Indicative pair fee; personal maker/taker, VIP/rebates and net proceeds UNKNOWN',
                conditional_plan=dict(status='BLOCKED' if excluded else 'CONDITIONAL_RESEARCH_ONLY',candidate_limit_price=None,
                    conditions=['Recheck all token security and existing mandatory evidence gates','Confirm personal fees, jurisdiction/account eligibility and available balances',
                        'Refresh depth/spread, minimum/maximum amounts and price/amount precision before manual review','Observe a fresh closed-candle retest/hold of historical support; invalidate if support fails'],
                    targets='UNKNOWN — no price prediction',position_sizing='UNKNOWN — no user risk/equity inputs',
                    risks=['Snapshot depth can be cancelled or spoofed','Displayed volume is not independent proof of genuine adoption','Limit orders may never fill; stop orders can slip']))
            if not metrics['buy_depth_sufficient'] or not metrics['sell_depth_sufficient'] or decimal(metrics['spread_bps'],zero=True)>100 or history['status']!='LIMITED':
                result['conditional_plan']['status']='BLOCKED'
            if history['status']=='LIMITED' and result['conditional_plan']['status']!='BLOCKED':
                precision=integer(pair.get('precision'))
                if precision>18:raise ValueError('Unsupported price precision')
                tick=Decimal(1).scaleb(-precision)
                limit=decimal(history['support']).quantize(tick,rounding=ROUND_FLOOR)
                if limit<=0:raise ValueError('Support rounds to zero')
                if limit>=decimal(metrics['best_ask']) or decimal(metrics['best_bid'])<=decimal(history['support']):
                    result['conditional_plan']['status']='BLOCKED'
                    result['conditional_plan']['conditions'].append('Historical support has failed or would produce a marketable limit; no entry reference admitted')
                    return result
                result['conditional_plan'].update(candidate_limit_price=str(limit),reference='Historical observed support rounded down to exchange price precision; NOT an order or current entry signal')
        except (OSError,ValueError,KeyError,TypeError,AttributeError,InvalidOperation) as exc:
            result.update(status='UNKNOWN',reason='Book, candle, units or fee evidence unavailable/invalid: '+type(exc).__name__)
        return result


def analyze_book(raw,notional,now):
    notional=decimal(notional)
    for field in ('current','update'):
        timestamp=integer(raw.get(field))/1000
        if not -1<=now-timestamp<=30:raise ValueError('Stale/future order book')
    if raw['update']>raw['current']:raise ValueError('Book timestamp ordering invalid')
    asks=[(decimal(p),decimal(q)) for p,q in raw['asks']];bids=[(decimal(p),decimal(q)) for p,q in raw['bids']]
    if not asks or not bids or len(asks)>20 or len(bids)>20:raise ValueError('Empty or out-of-scope depth')
    if any(a[0]>=b[0] for a,b in zip(asks,asks[1:])) or any(a[0]<=b[0] for a,b in zip(bids,bids[1:])) or bids[0][0]>=asks[0][0]:raise ValueError('Crossed/unsorted book')
    with localcontext() as ctx:
        ctx.prec=80
        remaining=notional;quantity=Decimal(0)
        for price,amount in asks:
            spend=min(remaining,price*amount);quantity+=spend/price;remaining-=spend
            if remaining==0:break
        buy_complete=remaining==0;spent=notional-remaining;buy_vwap=spent/quantity if quantity else None
        left=quantity;proceeds=Decimal(0)
        for price,amount in bids:
            fill=min(left,amount);proceeds+=fill*price;left-=fill
            if left==0:break
        sell_complete=left==0;sell_vwap=proceeds/quantity if sell_complete and quantity else None
        mid=(asks[0][0]+bids[0][0])/2
        return dict(provider_current_ms=raw['current'],provider_update_ms=raw['update'],snapshot_expires_at=raw['current']/1000+30,
            quote_currency='USDT (not assumed USD)',diagnostic_quote_notional=str(notional),best_ask=str(asks[0][0]),best_bid=str(bids[0][0]),
            spread_bps=str((asks[0][0]-bids[0][0])/mid*10000),ask_levels=len(asks),bid_levels=len(bids),
            ask_depth_quote_within_1pct=str(sum((p*q for p,q in asks if p<=asks[0][0]*Decimal('1.01')),Decimal(0))),
            bid_depth_quote_within_1pct=str(sum((p*q for p,q in bids if p>=bids[0][0]*Decimal('.99')),Decimal(0))),
            buy_depth_sufficient=buy_complete,sell_depth_sufficient=sell_complete,
            buy_vwap=str(buy_vwap) if buy_complete else None,sell_vwap=str(sell_vwap) if sell_vwap is not None else None,
            buy_slippage_bps=str((buy_vwap/asks[0][0]-1)*10000) if buy_complete else None,
            sell_slippage_bps=str((1-sell_vwap/bids[0][0])*10000) if sell_vwap is not None else None,
            complete_fees_included=False,executable_quote_verified=False,sequential_funded_execution_verified=False)


def analyze_candles(raw,now):
    try:
        bars=[]
        for row in raw:
            if len(row)!=8:raise ValueError('Ambiguous candle schema')
            t=int(row[0])
            if str(t)!=str(row[0]) or t%300:raise ValueError('Invalid five-minute timestamp')
            if type(row[7]) not in (str,bool) or row[7] not in ('true','false',True,False):raise ValueError('Missing closed-candle flag')
            if row[7] in ('false',False) or t+300>now:continue
            volume,close,high,low,opening,base=[decimal(x,zero=True) for x in row[1:7]]
            if not 0<low<=min(opening,close)<=max(opening,close)<=high:raise ValueError('Invalid OHLC geometry')
            bars.append((t,volume,close,high,low,opening,base))
        bars.sort()
        if len(bars)<21 or now-bars[-1][0]>900:raise ValueError('Insufficient fresh closed candles')
        bars=bars[-21:]
        if any(b[0]-a[0]!=300 for a,b in zip(bars,bars[1:])):raise ValueError('Candle gaps/duplicates')
        return dict(status='LIMITED',source='Gate Spot closed five-minute candles',last_closed_candle_at=bars[-1][0],
            support=str(min(x[4] for x in bars)),resistance=str(max(x[3] for x in bars)),
            mean_quote_volume=str(sum(x[1] for x in bars)/len(bars)),basis='Observed 21-candle range; not predicted support/targets or a confirmed retest')
    except (ValueError,KeyError,TypeError,InvalidOperation,IndexError):return dict(status='UNKNOWN',reason='Closed candle history insufficient, stale, ambiguous or malformed')
