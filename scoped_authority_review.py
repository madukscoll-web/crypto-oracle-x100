"""Exact-code technical review notes, not an audit or trade authorization."""
import datetime as dt

LINK='0x514910771af9ca656af840dff83e8264ecf986ca'
REVIEW=dict(network='eth',contract=LINK,reviewer='Codex AI technical source review',
            reviewed_at='2026-10-28T21:50:13.898629+00:00',expires_at='2026-11-04T21:50:13.898629+00:00',
            source_hashes={'LinkToken.sol':'18d961958d71cf5c7f70d2892d80bf6011f5920a498bf269a3707cf4acde2b0e'},
            runtime_hash='9792a60e149086e16264936114044e08b07981f87f64293339df5cd659e92a29',
            compiler_version='0.4.16+commit.d7661dd9',
            findings=['The named LinkToken constructor assigns the fixed initial balance at deployment',
                      'Reviewed balance writes are constructor allocation and ordinary caller/allowance-controlled transfers',
                      'No mint, freeze, blacklist, owner/admin or upgrade path was identified in this exact reviewed source',
                      'ERC677 transferAndCall deliberately invokes the recipient after updating transfer balances'],
            residuals=['AI technical review is not an independent security audit or local compiler reproduction',
                       'ERC20 approval replacement has transaction-ordering considerations; ERC677 recipients can execute callbacks',
                       'Treasury wallet controllers can release existing tokens; immutable supply does not establish a release calendar',
                       'Holder identities, economic ownership, exchange custody and trade execution are outside this code review'])


def assess(asset,source,now=None):
    result=dict(status='UNKNOWN',buy_authorized=False,independent_audit_completed=False)
    try:
        now=dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
        if asset.get('network')!=REVIEW['network'] or str(asset.get('token_address','')).lower()!=REVIEW['contract']:
            raise ValueError('No exact-code review registered for this asset')
        start=dt.datetime.fromisoformat(REVIEW['reviewed_at']).timestamp();end=dt.datetime.fromisoformat(REVIEW['expires_at']).timestamp()
        if not start<=now<end:raise ValueError('Exact-code technical review stale or future-dated')
        metrics=source.get('metrics')or{}
        if source.get('status')!='LIMITED' or metrics.get('runtime_source_match')is not True:
            raise ValueError('Fresh source/runtime collector evidence unavailable')
        observed=dt.datetime.fromisoformat(source['observed_at'].replace('Z','+00:00'))
        if observed.tzinfo is None or not 0<=now-observed.timestamp()<=3600:raise ValueError('Source observation stale/future')
        if metrics.get('source_sha256')!=REVIEW['source_hashes'] or metrics.get('runtime_sha256')!=REVIEW['runtime_hash']:
            raise ValueError('Source/runtime differs from reviewed code')
        if (metrics.get('proxy_resolution')or{}).get('isProxy')is not False:
            raise ValueError('Proxy scope unknown or mutable')
        if (metrics.get('compiler')or{}).get('compilerVersion')!=REVIEW['compiler_version']:
            raise ValueError('Compiler scope differs from review')
        result.update(status='SCOPED_TECHNICAL_REVIEW_MATCH',review=REVIEW,
                      meaning='Review findings apply only to the matched code; no token approval or complete security conclusion')
    except (ValueError,TypeError,KeyError,AttributeError):
        result['reason']='Exact reviewed identity, code, proxy/compiler scope or freshness not established'
    return result
