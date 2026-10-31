"""Five canonical research outcomes. Authorization stays with existing BUY gates."""
import opportunity_alerts
import evidence_audit
import adverse_evidence

OUTCOMES = ('VERIFIED BUY', 'ENTRY WATCH', 'RESEARCH WATCH', 'REJECT', 'INSUFFICIENT EVIDENCE')
VERSION = 'canonical-outcomes-v1'


def assess(item, now=None):
    # Recompute; never consume a caller-provided decision or buy_eligible boolean.
    adverse=[name+': '+reason for name, reason in adverse_evidence.findings(item).items()]
    if adverse:
        legacy={'classification':'REJECT','eligible_for_buy':False,'reasons':adverse,'missing_checks':[]}
    else:
        try:
            legacy = opportunity_alerts.classify(item, now=now)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
            legacy={'classification':'INELIGIBLE','eligible_for_buy':False,
                'reasons':['Evidence structure unavailable: '+type(exc).__name__],
                'missing_checks':['Classification withheld until evidence schema is supported']}
    label = legacy['classification']
    if label == 'REJECT':
        outcome = 'REJECT'
    elif label == 'VERIFIED BUY' and legacy.get('eligible_for_buy') is True and evidence_audit.audit(item)['trade_ready'] is True:
        outcome = 'VERIFIED BUY'
    elif label in ('HIGH-PRIORITY WATCH', 'ENTRY WATCH'):
        # Existing ENTRY WATCH only establishes a candle setup. Material gaps
        # make it RESEARCH WATCH under the stricter canonical policy.
        outcome = 'ENTRY WATCH' if evidence_audit.audit(item)['trade_ready'] is True and not legacy['missing_checks'] else 'RESEARCH WATCH'
    else:
        outcome = 'INSUFFICIENT EVIDENCE'
    return {'outcome': outcome, 'policy_version': VERSION,
            'legacy_classification': label, 'reasons': legacy['reasons'],
            'critical_gaps': legacy['missing_checks'],
            'buy_authorized': outcome == 'VERIFIED BUY',
            'orders_allowed': False,
            'entry_watch_policy': 'Reserved for fully verified research with only noncritical entry conditions unmet; no current adapter establishes this'}
