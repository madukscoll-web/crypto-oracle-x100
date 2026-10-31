"""Five canonical outcomes; signed admission is the positive evidence authority."""
import opportunity_alerts
import adverse_evidence
import authenticated_admission

BUY = 'BUY CANDIDATE — MANUAL REVIEW'
OUTCOMES = (BUY, 'WATCHLIST', 'WAIT/VERIFY', 'REJECT', 'DISCARD')
VERSION = 'canonical-outcomes-v2'


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
    admission = authenticated_admission.evaluate(item, now=now)
    if label == 'REJECT':
        outcome = 'REJECT'
    elif admission.get('safety_verified') and not admission['admitted']:
        outcome = 'WATCHLIST'
    elif admission['admitted']:
        outcome = BUY
    elif label in ('HIGH-PRIORITY WATCH', 'ENTRY WATCH'):
        # A legacy candle/activity setup cannot substitute for signed safety.
        outcome = 'WAIT/VERIFY'
    elif item.get('discovery_eligible') is False and item.get('scan_mode') != 'verification_only':
        outcome = 'DISCARD'
    else:
        outcome = 'WAIT/VERIFY'
    return {'outcome': outcome, 'policy_version': VERSION,
            'legacy_classification': label, 'reasons': legacy['reasons'],
            'critical_gaps': legacy['missing_checks'],
            'buy_authorized': outcome == BUY,
            'orders_allowed': False,
            'admission_bundle_sha256': admission.get('bundle_sha256'),
            'entry_watch_policy': 'WATCHLIST requires authenticated safety with signed MONITOR entry status'}
