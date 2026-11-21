"""Telegram delivery with bounded retries and credential-safe diagnostics."""
import datetime as dt
import json
import re
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from oracle_http import retry_delay
from classification_policy import format_message
from telegram_receipts import confirmed


HEALTH_FORMAT_VERSION = 2


class NotificationError(RuntimeError):
    """Safe to log: never includes a URL, token, chat ID or response body."""


def bounded_text(message, limit=4096):
    """Telegram counts UTF-16 units; preserve a complete Unicode prefix."""
    return message.encode("utf-16-le")[:limit * 2].decode("utf-16-le", errors="ignore")


def send_message(message):
    return _send_message(format_message(message))


def send_research_message(notice):
    from research_notice import verified_text
    message = verified_text(notice)
    # Never silently discard trailing risk disclosures or evidence limitations.
    # Telegram's text ceiling is 4096 UTF-16 code units, not Python characters.
    if len(message.encode('utf-16-le')) // 2 > 4096:
        raise NotificationError('Research alert exceeds Telegram limit; delivery withheld to preserve risk disclosures')
    return _send_message(message, max_attempts=1, request_timeout=8)


def send_admission_message(item):
    """Recompute authenticated admission at transport, never trust supplied text.

    Generic send_message intentionally downgrades caller-provided BUY labels.
    Passing a freshly formatted admission through that path also downgraded
    genuine signed candidates. Keep the privileged path bound to the asset and
    its current evidence rather than adding a bypass flag to generic transport.
    """
    from opportunity_alerts import format_admission_alert
    return _send_message(format_admission_alert(item), max_attempts=1, request_timeout=8)


def _send_message(message, *, max_attempts=3, request_timeout=20):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise NotificationError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    payload = urllib.parse.urlencode({"chat_id": chat, "text": bounded_text(message)}).encode()
    request = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage", data=payload, method="POST")
    failure = "Telegram delivery unconfirmed"
    for attempt in range(max_attempts):
        delay = retry_delay({}, attempt)
        try:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise ValueError("Invalid response")
            if confirmed(result, chat):
                print("Telegram delivery confirmed by Bot API (message_id present).", flush=True)
                return True
            code = result.get("error_code")
            if code not in (429, 500, 502, 503, 504):
                raise NotificationError("Telegram API rejected delivery or omitted confirmation")
            parameters = result.get("parameters") or {}
            delay = retry_delay({"Retry-After": parameters.get("retry_after")}, attempt)
            failure = f"Telegram API rejected delivery (HTTP {code})"
        except urllib.error.HTTPError as exc:
            failure = f"Telegram HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                raise NotificationError(failure) from None
            delay = retry_delay(exc.headers, attempt)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError):
            # Never propagate urllib's credential-bearing URL or remote body.
            failure = "Telegram transport failure or malformed response"
        if attempt < max_attempts-1:
            print(f"{failure}; retry {attempt + 1}/2 (delivery may duplicate after ambiguous response)", flush=True)
            time.sleep(delay)
    raise NotificationError(failure) from None


def _plain_time(value):
    import datetime as _dt
    try:
        parsed=_dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed.astimezone(_dt.timezone.utc).strftime('%d %b %Y %H:%M UTC')
    except (ValueError,TypeError):
        return 'not recorded'


def workflow_message(mode):
    run_url = ("https://github.com/" + os.environ.get("GITHUB_REPOSITORY", "")
               + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", ""))
    if mode == "failure":
        outcomes = {}
        for entry in os.environ.get('FAILED_STAGES', '').split(','):
            name, separator, outcome = entry.strip().partition('=')
            if separator:
                outcomes[name] = outcome
        failed = [name + '=' + value for name, value in outcomes.items()
                  if value in ('failure', 'cancelled', 'timed_out')]
        core = outcomes.get('scan', 'unknown')
        # Only a failed core scan is critical; a failed follow-up stage leaves
        # discovery intact and is reported as an ordinary health notice.
        heading = "SYSTEM HEALTH REPORT" if core == "success" else "CRITICAL SYSTEM FAILURE"
        failed_text = ', '.join(failed) or 'see run logs'
        if core == "success":
            plain = ("The main market scan worked, but a later step failed. "
                     "Alerts from this run may be missing or late.")
        else:
            plain = ("The main market scan did not finish. "
                     "The bot has not checked the market in this run, so no alerts came from it.")
        return (heading + "\n\U0001F9ED IN PLAIN ENGLISH\n" + plain + "\n"
                "What to do: nothing urgent. The next scan will try again by itself. "
                "If this message keeps repeating, open the link below.\n"
                "The bot has NOT bought or sold anything and cannot trade.\n\n"
                "\U0001FA7A DETAILS\n"
                "Main scan result: " + core + ".\n"
                "Steps that failed: " + failed_text + ".\n\n"
                "\U0001F517 Run log: " + run_url)
    report = json.loads(pathlib.Path("scan_summary.json").read_text(encoding="utf-8"))
    if report.get("status") != "completed":
        raise NotificationError("Refusing completion summary for an unsuccessful scan")
    def optional(name):
        try:
            value=json.loads(pathlib.Path(name).read_text())
            return value if isinstance(value,dict) else {}
        except (OSError,ValueError):
            return {}
    return health_summary(report, optional('altcoin_reversal_report.json'),
        optional('pipeline_health_report.json'), optional('atl_coverage_report.json'),
        optional('strategy_lab_state.json'), optional('technical_followup_state.json'),run_url,
        optional('scanner_cadence_report.json'))


# Fixed plain-language categories for audit blockers. Only these phrases (never raw
# provider text, addresses or diagnostics) can enter Telegram.
BLOCKER_CATEGORIES=(
    ('Critical provider security flag','flagged high-risk by the security provider'),
    ('Provider security assessment unavailable','no security data yet (token too new for the provider)'),
    ('Exact base-token identity unverified','token contract not identified'),
    ('Positive pool liquidity and volume unavailable','market data refresh failed'),
    ('Token-2022','Solana Token-2022 mint not yet supported'),
    ('Circulating/maximum supply unverified','supply not verified'),
    ('Complete LP withdrawal authority','LP lock and ownership not verified'),
    ('Top-holder concentration','holder concentration not verified'),
    ('executable quote','no live sell quote'),
)


# The first five categories explain WHY a particular token failed; the rest are checks
# that are unverified for nearly every candidate, so they are listed after the specific ones.
SPECIFIC_BLOCKERS=5


def blocker_summary(counts,limit=5):
    """Top blockers as 'N reason' phrases, specific causes first. Overlapping strings use the max count."""
    if not isinstance(counts,dict):return []
    totals={}
    for raw,count in counts.items():
        if not isinstance(raw,str) or type(count) is not int or count<=0:continue
        for position,(needle,phrase) in enumerate(BLOCKER_CATEGORIES):
            if needle in raw:
                totals[phrase]=(position,max(totals.get(phrase,(position,0))[1],count))
                break
    ranked=sorted(((phrase,value[1],value[0]) for phrase,value in totals.items()),
                  key=lambda item:(item[2]>=SPECIFIC_BLOCKERS,-item[1],item[0]))
    ranked=[(phrase,count) for phrase,count,_ in ranked]
    return [str(count)+' '+phrase for phrase,count in ranked[:limit]]


def pattern_lines(study):
    """One honest line on the winner-pattern study; never a score or a recommendation."""
    if not isinstance(study, dict) or not isinstance(study.get('labeled'), int):
        return []
    text = str(study.get('conclusion', ''))[:150]
    return ['Pattern study (24h outcomes): '+str(study['labeled'])+'/'+str(study.get('minimum_total', 200))
            +' measured. '+text+'.']


def scan_gap_line(cadence):
    """Hours between the previous completed core scan and this scan's start. Only a finite
    non-negative number from the cadence guard is shown; anything else is 'unknown'."""
    seconds=cadence.get('core_success_age_seconds') if isinstance(cadence,dict) else None
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not 0<=seconds<=10**8 or seconds!=seconds:
        return 'Scan gap: unknown (no previous completed scan recorded).'
    hours=seconds/3600
    note=' Scans are running less often than planned.' if hours>2 else ''
    return 'Scan gap: previous completed scan was '+format(hours,'.1f')+' h before this one.'+note


def health_summary(report,reversal,health,atl,paper,followup,run_url,cadence=None):
    """Counts only. Raw arrays, addresses and diagnostics never enter Telegram."""
    def number(value):
        return str(value) if type(value) is int and 0<=value<=10**12 else 'unknown'
    def metric(source,key):
        return number(source.get(key)) if isinstance(source,dict) else 'unknown'
    def obj(source,key):
        value=source.get(key) if isinstance(source,dict) else None
        return value if isinstance(value,dict) else {}
    audit=obj(report,'filter_audit');counts=obj(audit,'notification_outcomes')
    coverage=obj(reversal,'coverage');technical=obj(reversal,'technical_delivery')
    suppressed=obj(technical,'suppressed');evidence=obj(report,'suppression_reasons')
    try:
        at=dt.datetime.fromisoformat(report['completed_at'].replace('Z','+00:00'))
        if at.tzinfo is None:raise ValueError('Timezone missing')
        at=at.astimezone(dt.timezone(dt.timedelta(hours=1))).strftime('%d %b %H:%M WAT')
    except (KeyError,ValueError,TypeError,AttributeError):at='time unavailable'
    axes=[]
    for key in ('execution_status','coverage_status','admission_status'):
        value=health.get(key)
        axes.append(value if value in {'COMPLETED','FAILED_OR_INCOMPLETE','DEGRADED','NO_REPORTED_PROVIDER_ERRORS','BLOCKED','UNKNOWN','NOT_READY','READY'} else 'UNKNOWN')
    accounts=paper.get('accounts');hypotheses=followup.get('hypotheses')
    closed=opened=None;triggered=None;watches=None
    if isinstance(accounts,dict) and all(isinstance(x,dict) and isinstance(x.get('account'),dict) and isinstance(x['account'].get('trades'),list) for x in accounts.values()):
        closed=sum(len(x['account']['trades']) for x in accounts.values())
        opened=sum(x['account'].get('position') is not None for x in accounts.values())
    if isinstance(hypotheses,dict) and all(isinstance(x,dict) and isinstance(x.get('samples'),list) for x in hypotheses.values()):
        watches=len(hypotheses)
        triggered=sum(any(isinstance(sample,dict) and sample.get('at_or_above_trigger_observed') is True for sample in x['samples']) for x in hypotheses.values())
    def alerted_assets(source):
        # Provider slugs only (never addresses or raw diagnostics), capped.
        decisions=obj(source,'research_delivery').get('decisions') or []
        names=[]
        for entry in decisions if isinstance(decisions,list) else []:
            slug=entry.get('provider_id') if isinstance(entry,dict) else None
            if (isinstance(entry,dict) and entry.get('status')=='BOT_API_CONFIRMED' and isinstance(slug,str)
                    and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}',slug) and slug not in names):
                names.append(slug)
        return names[:5]
    atl_names=alerted_assets(atl)
    blockers=blocker_summary(audit.get('assessed_blocker_counts')) if number(report.get('candidates') if isinstance(report,dict) else None)!='unknown' else []
    lines=[
        'SYSTEM HEALTH REPORT',
        'CRYPTO-ORACLE X100 daily pipeline health | '+at,
        '',
        '🩺 STATUS',
        'Execution: '+axes[0]+' | Coverage: '+axes[1]+' | Admission: '+axes[2],
        scan_gap_line(cadence),
        '',
        '🔎 DISCOVERY',
        'Discovery: '+metric(report,'candidates')+' candidates; '+metric(audit,'assessed_candidates')+' assessed; '+metric(audit,'discovery_pools_not_selected')+' deferred.',
        'Assessed: '+metric(audit,'assessed_candidates')+'; ineligible: '+metric(counts,'ineligible')+'. Evidence: '+metric(evidence,'REJECT')+' rejected; '+metric(evidence,'INSUFFICIENT EVIDENCE')+' incomplete.',
        *(['','🔍 WHY NO ALERTS','Top blockers among assessed candidates: '+'; '.join(blockers)+'.'] if blockers else []),
        '',
        '🔔 ALERTS',
        'BUY candidates for manual review: '+metric(report,'buy_candidates_delivered')+'; safety-reviewed entry WATCH alerts: '+metric(report,'signed_entry_watches_delivered')+'; research WATCH alerts: '+metric(report,'research_watch_delivered')+'.',
        'Reversals: '+metric(technical,'delivered')+' alerts; '+metric(coverage,'selected_pairs')+'/'+metric(coverage,'liquid_eligible_pairs')+' policy pairs assessed; '+metric(coverage,'all_liquid_eligible_pairs')+' liquid pairs overall.',
        'Reversal suppression: '+number(sum(v for v in suppressed.values() if type(v) is int and v>=0))+' cases. Exact reasons remain in diagnostics.',
        'ATL: '+metric(atl,'alerts_delivered')+' alerts; '+metric(atl,'provider_atl_candidates')+' provider leads; '+metric(atl,'enrichment_deferred')+' enrichment-deferred; '+metric(atl,'historical_baselines_validated')+' validated lifetime baselines.',
        *(['ATL alerted: '+', '.join(atl_names)+'.'] if atl_names else []),
        '',
        '📈 PERFORMANCE',
        'Performance: '+number(closed)+' closed paper trades; '+number(opened)+' open paper positions. Sampled trigger reached: '+number(triggered)+'/'+number(watches)+' tracked watches.',
        'Profitability: NOT ESTABLISHED. Paper accounts are simulations; sampled prices are not fills.',
        *pattern_lines(report.get('pattern_study')),
        '',
        '🧾 SUMMARY',
        'No qualifying tokens found.' if report.get('candidates')==0 else 'Research observations are not purchase approval.',
        '',
        '🔗 LINKS',
        'Full diagnostics: '+run_url]
    return '\n'.join(lines)


def notify_workflow(mode, *, now=None, state_path="operational_digest_state.json", sender=None):
    """At most one confirmed health digest per Lagos calendar day.

    State is published with scanner state by the serialized hourly workflow.
    Failed or ambiguous sends never advance the confirmed-day marker.
    """
    sender = sender or send_message
    if mode == "failure":
        if sender(workflow_message(mode)) is not True:
            raise NotificationError("Telegram failure receipt not confirmed")
        return {"status": "BOT_API_CONFIRMED", "mode": "failure"}
    if mode != "success":
        raise ValueError("Unknown workflow notification mode")
    report = json.loads(pathlib.Path("scan_summary.json").read_text(encoding="utf-8"))
    if report.get("status") != "completed":
        raise NotificationError("Refusing digest for unsuccessful scan")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if run_id and report.get("github_run_id") != run_id:
        raise NotificationError("Summary belongs to another workflow run")
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone required")
    day = now.astimezone(dt.timezone(dt.timedelta(hours=1))).date().isoformat()
    target = pathlib.Path(state_path)
    state = json.loads(target.read_text()) if target.exists() else {"version": 1}
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("Invalid digest state")
    # Report a cadence gap at most once per Lagos calendar day, not once per heartbeat.
    # Each new prior heartbeat is different and previously caused repeated Telegram spam.
    cadence_path=pathlib.Path('scanner_cadence_report.json')
    if cadence_path.exists():
        cadence=json.loads(cadence_path.read_text())
        from scanner_cadence import age
        checked_age=age(cadence.get('checked_at'),now)
        marker=cadence.get('last_core_success_at') or 'MISSING_HEARTBEAT'
        if (cadence.get('stale_or_missing_core_heartbeat') is True
                and run_id and cadence.get('github_run_id')==run_id
                and checked_age is not None and checked_age<=3600
                and state.get('cadence_gap_confirmed_day')!=day):
            message=('BOT HEALTH | OPERATIONAL\n'
                     '\U0001F9ED IN PLAIN ENGLISH\n'
                     'The bot was not running for a while, and has now started again. '
                     'The scan that just finished worked normally. '
                     'Nothing is wrong right now, but you cannot assume it checked the market every hour.\n'
                     'What to do: nothing.\n\n'
                     '\U0001F4CC DETAILS\n'
                     'Last scan before this one: '+_plain_time(cadence.get('last_core_success_at'))+'\n'
                     'Why this happens: GitHub sometimes skips scheduled runs.\n'
                     'Technical record: scanner_cadence_report.json in run '+run_id+'.\n\n'
                     '\u26A0\uFE0F LIMITS\n'
                     'This is a status note, not a trading signal. The bot cannot buy or sell.')
            if sender(message) is not True:
                raise NotificationError('Cadence gap receipt not confirmed')
            state['cadence_gap_confirmed_for']=marker
            state['cadence_gap_confirmed_day']=day
            temporary=target.with_suffix(target.suffix+'.tmp')
            temporary.write_text(json.dumps(state,indent=2)+'\n')
            temporary.replace(target)
    # Replace an older unreadable format once; normal daily dedup then resumes.
    if state.get("confirmed_day") == day and state.get("confirmed_format_version",1) == HEALTH_FORMAT_VERSION:
        return {"status": "SKIPPED_DAILY_DEDUP", "github_run_id": run_id}
    if sender(workflow_message(mode)) is not True:
        raise NotificationError("Telegram digest receipt not confirmed")
    state.update(confirmed_day=day, confirmed_at=now.isoformat(), github_run_id=run_id,
                 confirmed_format_version=HEALTH_FORMAT_VERSION)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return {"status": "BOT_API_CONFIRMED", "github_run_id": run_id,
            "candidate_details_included": False, "confirmed_day": day}


if __name__ == "__main__":
    try:
        result = notify_workflow(sys.argv[1])
        pathlib.Path("operational_notification.json").write_text(json.dumps(result) + "\n", encoding="utf-8")
    except (NotificationError, OSError, ValueError, KeyError, IndexError) as exc:
        print(f"ERROR: Telegram workflow notification failed ({type(exc).__name__}). Inspect configuration and run logs.", flush=True)
        sys.exit(1)


