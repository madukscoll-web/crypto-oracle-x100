"""Reproducible live read-only reference validation, separate from discovery.

This is not a deployment or BUY approval. Telegram transmission is opt-in and
always marked NO BUY SIGNAL. Outputs contain public market/RPC evidence and
sanitized Telegram state, never credentials or private chat metadata.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import execution_quotes
import execution_checks
import candidate_evidence
import gas_valuation
import onchain
import telegram_validation
import token_unlocks
import verification
from crypto_oracle_scanner import fetch_json

REFERENCE = dict(network='eth',token_address='0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                 address='0x811beed0119b4afce20d2583eb608c6f7af1954f')


def validate(send_test=False):
    registry=json.loads(pathlib.Path(__file__).with_name('evidence_registry.json').read_text())
    report=verification.collect(REFERENCE,fetch_json)
    info=((report.get('contract_security',{}).get('raw') or {}).get('result') or {}).get(REFERENCE['token_address'],{})
    report['onchain']=onchain.collect(REFERENCE,info.get('holders') or [],lock_descriptors=registry['lp_locks'].get('eth:'+REFERENCE['address'],[]))
    report['unlocks']=token_unlocks.collect(REFERENCE,registry)
    report['gas_valuation']=gas_valuation.collect('eth',fetch_json)
    price=report['gas_valuation'].get('metrics',{}).get('native_usd')
    report['execution']=execution_quotes.collect(REFERENCE,os.environ,native_price=price)
    report['execution_checks']=execution_checks.collect(REFERENCE,report['execution'],os.environ.get('ORACLE_TAKER_ADDRESS',''))
    candidate_evidence.augment(REFERENCE,report,fetch_json,os.environ,native_price=price,reference_order=dict(funding_token='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',amount_base_units='100000000'))
    report['telegram']=telegram_validation.validate(os.environ,send_test)
    return dict(observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),reference=REFERENCE,
                automated_trading_enabled=False,verified_buy_issued=False,
                production_ready=False,evidence=report)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='validation_runtime.json')
    parser.add_argument('--send-telegram-test',action='store_true')
    args=parser.parse_args()
    report=validate(args.send_telegram_test)
    pathlib.Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    for key,value in report['evidence'].items():
        print(key,value['status'],value.get('reason',''))
    if args.send_telegram_test and not report['evidence']['telegram']['delivery_confirmed']:
        return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())
