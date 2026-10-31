"""Bounded market discovery independent of all exchange listing decisions.

GeckoTerminal new/trending pools, with explicitly labelled latest-profile fallback.
DEX profiles are promotional discovery leads, not evidence of organic adoption.
Docs: https://docs.dexscreener.com/api/reference
https://apiguide.geckoterminal.com/ (CoinGecko on-chain API documentation)
"""
import datetime as dt
import math
from urllib.parse import quote
from asset_identity import canonical,key,DEX_CHAINS,pool_address

GECKO='https://api.geckoterminal.com/api/v2'
DEX='https://api.dexscreener.com'


def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()


def measurement(value):
    if value is None or isinstance(value,bool):return None
    try:
        value=float(value)
        return value if math.isfinite(value) else None
    except (ValueError,TypeError,OverflowError):return None


def gecko_rows(network,raw,url,mode,at=None):
    at=at or stamp();included={x['id']:x for x in raw.get('included',[]) if x.get('type')=='token'}
    rows=[];invalid=[]
    for pool in raw['data']:
        try:
            attrs=pool['attributes'];relation=pool['relationships']['base_token']['data']['id'];token=included[relation]['attributes']
            contract=canonical(network,token['address'])
            if not relation.startswith(network+'_') or canonical(network,relation[len(network)+1:])!=contract:raise ValueError('Included token relationship identity mismatch')
            address=pool_address(network,attrs['address'])
            if not pool['id'].startswith(network+'_') or pool_address(network,pool['id'][len(network)+1:])!=address:raise ValueError('Pool/network identity mismatch')
            h1=(attrs.get('transactions') or {}).get('h1') or {};buys=measurement(h1.get('buys'));sells=measurement(h1.get('sells'))
            trades=buys+sells if buys is not None and sells is not None and min(buys,sells)>=0 else None
            created=attrs.get('pool_created_at');age=None
            if created:
                born=dt.datetime.fromisoformat(created.replace('Z','+00:00'));observed=dt.datetime.fromisoformat(at)
                if born.tzinfo is not None and 0<=(observed-born).total_seconds():age=(observed-born).total_seconds()/3600
            rows.append(dict(asset_key=key(network,contract),network=network,token_address=contract,token_symbol=token.get('symbol','UNKNOWN'),
                address=address,key=network+':'+address,name=attrs.get('name','UNKNOWN'),source='GeckoTerminal public pool feed',source_url=url,
                observed_at=at,provider_market_timestamp='UNKNOWN (retrieval time only)',discovery_mode=mode,
                token_identity_status='Base token from GeckoTerminal pool relationship',
                base_token_price_usd=measurement(attrs.get('base_token_price_usd')),liquidity=measurement(attrs.get('reserve_in_usd')),
                volume=measurement((attrs.get('volume_usd') or {}).get('h24')),buys=buys,sells=sells,trades=trades,
                buy_share=buys/trades if trades else None,change_h1=measurement((attrs.get('price_change_percentage') or {}).get('h1')),
                change_h24=measurement((attrs.get('price_change_percentage') or {}).get('h24')),age_hours=age,
                market_cap_estimate_usd=measurement(attrs.get('market_cap_usd')),fdv_estimate_usd=measurement(attrs.get('fdv_usd')),
                token_age='UNKNOWN — pool age is not token launch age',flags=[],score=0,
                url=f'https://www.geckoterminal.com/{network}/pools/{quote(address,safe="")}',raw=pool))
        except (ValueError,KeyError,TypeError,AttributeError) as exc:invalid.append(dict(pool_id=pool.get('id'),error_type=type(exc).__name__))
    return rows,invalid


class GeckoDiscovery:
    network=None
    def __init__(self,fetch):self.fetch=fetch
    def discover(self, modes=('new_pools','trending_pools')):
        observations=[];rows=[];failures=[]
        for mode in modes:
            url=f'{GECKO}/networks/{self.network}/{mode}?include=base_token,quote_token&page=1'
            try:
                raw=self.fetch(url);at=stamp()
                if not isinstance(raw.get('data'),list):raise ValueError('Invalid pool feed')
                parsed,invalid=gecko_rows(self.network,raw,url,mode,at);rows+=parsed
                observations.append(dict(source='geckoterminal',url=url,observed_at=at,raw=raw,invalid_rows=invalid))
            except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:failures.append(dict(url=url,error_type=type(exc).__name__,http_status=getattr(exc,'code',None)))
        return dict(rows=rows,observations=observations,failures=failures)


class SolanaDiscovery(GeckoDiscovery):network='solana'
class EthereumDiscovery(GeckoDiscovery):network='eth'
class BaseDiscovery(GeckoDiscovery):network='base'
class BnbDiscovery(GeckoDiscovery):network='bsc'
ADAPTERS=(SolanaDiscovery,EthereumDiscovery,BaseDiscovery,BnbDiscovery)

# Expanded public discovery is separate from production security authorization.
class ArbitrumDiscovery(GeckoDiscovery):network='arbitrum'
class PolygonDiscovery(GeckoDiscovery):network='polygon_pos'
class AvalancheDiscovery(GeckoDiscovery):network='avax'
class OptimismDiscovery(GeckoDiscovery):network='optimism'
RESEARCH_ADAPTERS=ADAPTERS+(ArbitrumDiscovery,PolygonDiscovery,AvalancheDiscovery,OptimismDiscovery)


class ProfileFallback:
    def __init__(self,fetch):self.fetch=fetch;self.raw=None
    def discover(self,network,limit=2):
        rows=[];evidence=[];failures=[]
        try:
            if self.raw is None:self.raw=self.fetch(DEX+'/token-profiles/latest/v1')
            if not isinstance(self.raw,list):raise ValueError('Invalid profile response')
            evidence.append(dict(source='dexscreener_profiles',url=DEX+'/token-profiles/latest/v1',observed_at=stamp(),raw=self.raw))
            profiles=[x for x in self.raw if x.get('chainId')==DEX_CHAINS[network]][:limit]
            for profile in profiles:
                token=canonical(network,profile['tokenAddress']);url=DEX+'/token-pairs/v1/'+DEX_CHAINS[network]+'/'+quote(token,safe='')
                raw=self.fetch(url);at=stamp();evidence.append(dict(url=url,observed_at=at,raw=raw))
                for pair in raw:
                    if pair.get('chainId')!=DEX_CHAINS[network] or canonical(network,(pair.get('baseToken') or {}).get('address'))!=token:continue
                    h1=(pair.get('txns') or {}).get('h1') or {};buys=measurement(h1.get('buys'));sells=measurement(h1.get('sells'));trades=buys+sells if buys is not None and sells is not None else None
                    address=pool_address(network,pair['pairAddress']);created=measurement(pair.get('pairCreatedAt'))
                    age=(dt.datetime.fromisoformat(at).timestamp()-created/1000)/3600 if created is not None else None
                    rows.append(dict(asset_key=key(network,token),network=network,token_address=token,token_symbol=pair['baseToken'].get('symbol','UNKNOWN'),
                        address=address,key=network+':'+address,name=pair['baseToken'].get('name','UNKNOWN'),source='DEX Screener latest-profile fallback (promotional lead)',
                        source_url=url,observed_at=at,provider_market_timestamp='UNKNOWN (retrieval time only)',discovery_mode='profile_fallback',
                        token_identity_status='DEX Screener pool relationship; GeckoTerminal confirmation UNKNOWN',
                        base_token_price_usd=measurement(pair.get('priceUsd')),liquidity=measurement((pair.get('liquidity') or {}).get('usd')),
                        volume=measurement((pair.get('volume') or {}).get('h24')),buys=buys,sells=sells,trades=trades,buy_share=buys/trades if trades else None,
                        change_h1=measurement((pair.get('priceChange') or {}).get('h1')),change_h24=measurement((pair.get('priceChange') or {}).get('h24')),
                        age_hours=age,market_cap_estimate_usd=measurement(pair.get('marketCap')),fdv_estimate_usd=measurement(pair.get('fdv')),
                        token_age='UNKNOWN',flags=['Promotional profile is not organic adoption evidence'],score=0,
                        url=f'https://dexscreener.com/{DEX_CHAINS[network]}/{quote(address,safe="")}',raw=pair))
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:failures.append(dict(error_type=type(exc).__name__,http_status=getattr(exc,'code',None)))
        return dict(rows=rows,observations=evidence,failures=failures)


def deduplicate(rows):
    assets={}
    for row in rows:
        identity=key(row['network'],row['token_address'])
        if identity not in assets:assets[identity]=dict(asset_key=identity,network=row['network'],token_address=canonical(row['network'],row['token_address']),pools=[])
        # The same pool on two feeds remains two source observations, not two
        # additive liquidity/volume measurements. Never merge by symbol.
        assets[identity]['pools'].append(row)
    return list(assets.values())
