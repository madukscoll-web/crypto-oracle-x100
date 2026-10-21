"""Shared public evidence enrichment and explicit mandatory-gate diagnostics."""
import contract_sources
import custody_verification
import escrow_discovery
import kyber_quotes
import supply_evidence
import unlock_provider
import kyber_execution
import quote_calldata
import nft_custody
import json
import pathlib


def augment(item,report,fetch,env,native_price=None,reference_order=None):
    raw=report.get('contract_security',{}).get('raw') or {}
    info=(raw.get('result') or {}).get(item.get('token_address','').lower(),{})
    registry=json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())
    report['unlock_provider']=unlock_provider.collect(item,registry,env)
    report['supply_comparison']=supply_evidence.collect(item,fetch)
    report['contract_source']=contract_sources.collect(item,fetch)
    report['escrow_discovery']=escrow_discovery.collect(item,info.get('lp_holders') or [],fetch)
    report['nft_custody']=nft_custody.collect(item,info.get('lp_holders') or [])
    report['custody']=custody_verification.collect(item,info.get('holders') or [],fetch)
    report['kyber']=kyber_quotes.collect(item,env,reference_order=reference_order,native_price=native_price)
    report['calldata_policy']=quote_calldata.collect(item,report['kyber'],fetch)
    report['kyber_execution']=kyber_execution.collect(item,report['kyber'],env.get('ORACLE_TAKER_ADDRESS',''),native_price=native_price)
    return report


def blockers(item):
    report=item.get('verification') or {}
    reasons=[]
    if item.get('risk_category')=='AVOID / HIGH CONCERN':
        reasons.append('Critical provider security concern: '+'; '.join(item.get('risk_reasons') or []))
    source=report.get('contract_source',{})
    if not source.get('metrics',{}).get('runtime_source_match'):
        diagnostic=source.get('diagnostic') or {}
        suffix=' (HTTP '+str(diagnostic['http_status'])+')' if diagnostic.get('http_status') is not None else ''
        reasons.append('Exact source/bytecode verification unavailable: '+source.get('reason','Not checked')+suffix)
    reasons.append('Independent contract mint/upgrade/transfer authority audit is incomplete')
    lp=((report.get('onchain',{}).get('raw') or {}).get('results') or {}).get('lp',{})
    metrics=(report.get('pool_identity_followup',{}).get('metrics') if report.get('pool_identity_followup',{}).get('status')=='LIMITED' else None) or lp.get('metrics') or {}
    fraction=metrics.get('burned_lp_fraction')
    if fraction is None:
        if metrics.get('position_type')=='concentrated_nft':
            reasons.append('Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified')
        else:
            reasons.append('LP coverage unknown: '+lp.get('reason','No canonical supported-pool proof'))
    else:
        reasons.append(f'LP permanent-burn coverage observed {fraction:.6%}; complete corroborated escrow coverage/review unavailable')
    if report.get('nft_custody',{}).get('status')=='CONFLICTING':
        reasons.append('Position NFT provider/RPC owner evidence conflicts; complete custody remains unverified')
    reasons.append('Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons')
    if report.get('supply_comparison',{}).get('status')=='CONFLICTING':
        reasons.append('Supply evidence conflict: '+report['supply_comparison']['reason'])
    reasons.append('Complete circulating supply, vesting/unlocks and mint authority are unverified: '+report.get('unlocks',{}).get('reason','No disclosure'))
    sim=report.get('sellability') or report.get('honeypot') or {}
    if sim.get('status')!='LIMITED':reasons.append('Exact-pool independent sellability: '+sim.get('reason','Unavailable'))
    execution=report.get('execution_checks',{})
    sequential=((execution.get('raw') or {}).get('sequential') or {}).get('sequential_simulation_succeeded')
    kyber_sequential=(((report.get('kyber_execution',{}).get('raw') or {}).get('sequential')) or {}).get('sequential_simulation_succeeded')
    if sequential is not True and kyber_sequential is not True:reasons.append('Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable')
    reasons.append('Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified')
    if report.get('entry',{}).get('status')!='LIMITED':
        reasons.append('Entry evidence: '+report.get('entry',{}).get('reason','No verified historical setup'))
    if item.get('market_corroboration',{}).get('status')!='CORROBORATED':
        reasons.append('Exact-pool market corroboration: '+item.get('market_corroboration',{}).get('reason','Unavailable'))
    return reasons
