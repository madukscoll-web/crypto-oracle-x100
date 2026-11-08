"""Telegram delivery with bounded retries and credential-safe diagnostics."""
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from oracle_http import retry_delay
from classification_policy import format_message


class NotificationError(RuntimeError):
    """Safe to log: never includes a URL, token, chat ID or response body."""


def bounded_text(message, limit=4096):
    """Telegram counts UTF-16 units; preserve a complete Unicode prefix."""
    return message.encode("utf-16-le")[:limit * 2].decode("utf-16-le", errors="ignore")


def send_message(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise NotificationError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    payload = urllib.parse.urlencode({"chat_id": chat, "text": bounded_text(format_message(message))}).encode()
    request = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage", data=payload, method="POST")
    failure = "Telegram delivery unconfirmed"
    for attempt in range(3):
        delay = retry_delay({}, attempt)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise ValueError("Invalid response")
            receipt = (result.get("result") or {})
            message_id = receipt.get("message_id") if isinstance(receipt, dict) else None
            if result.get("ok") is True and type(message_id) is int and message_id > 0:
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
        if attempt < 2:
            print(f"{failure}; retry {attempt + 1}/2 (delivery may duplicate after ambiguous response)", flush=True)
            time.sleep(delay)
    raise NotificationError(failure) from None


def workflow_message(mode):
    run_url = ("https://github.com/" + os.environ.get("GITHUB_REPOSITORY", "")
               + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", ""))
    if mode == "failure":
        return ("CRYPTO-ORACLE X100: workflow FAILED. No successful scan should be assumed. "
                "Failed stage(s): " + os.environ.get("FAILED_STAGES", "see run logs") + ". Inspect: " + run_url)
    report = json.loads(pathlib.Path("scan_summary.json").read_text(encoding="utf-8"))
    if report.get("status") != "completed":
        raise NotificationError("Refusing completion summary for an unsuccessful scan")
    audit = report.get("filter_audit") or {}
    counts = audit.get("notification_outcomes") or {}
    details = (f"Assessed: {audit.get('assessed_candidates', 'unknown')}; "
               f"ineligible: {counts.get('ineligible', 0)}; already delivered: {counts.get('already_delivered', 0)}; "
               f"delivery capped: {counts.get('delivery_cap', 0)}; failed sends: {counts.get('delivery_failed', 0)}. "
               f"Security concerns among assessed: {audit.get('security_rejections', 0)}; "
               f"discovered pools deferred: {audit.get('discovery_pools_not_selected', 'unknown')}. ")
    suppression = report.get('suppression_reasons') or {}
    details += 'Suppressed by evidence outcome: ' + json.dumps(suppression, sort_keys=True) + '. '
    reversal_path = pathlib.Path('altcoin_reversal_report.json')
    if reversal_path.exists():
        reversal = json.loads(reversal_path.read_text(encoding='utf-8'))
        technical = reversal.get('technical_delivery') or {}
        details += f"Technical channel: {technical.get('delivered', 0)} delivered, {technical.get('failed', 0)} failed; separate from verified BUY. "
        details += 'Reversal coverage: ' + json.dumps(reversal.get('coverage', reversal.get('status_counts', {})), sort_keys=True) + '. '
    health_path = pathlib.Path('pipeline_health_report.json')
    if health_path.exists():
        health = json.loads(health_path.read_text())
        details += f"Research data health: {health.get('status','UNKNOWN')}; provider gaps: {json.dumps(health.get('data_degradation',{}),sort_keys=True)}. "
    atl_path = pathlib.Path('atl_coverage_report.json')
    if atl_path.exists():
        atl = json.loads(atl_path.read_text())
        details += (f"ATL collector: {atl.get('status', 'UNKNOWN')}; "
                    f"{atl.get('provider_atl_candidates', 0)} provider-reported near-low candidates; "
                    f"{atl.get('historical_baselines_validated', 0)} validated lifetime baselines; "
                    f"{atl.get('alerts_delivered', 0)} ATL alerts. ")
    return (f"CRYPTO-ORACLE X100 daily pipeline health, latest scan at {report['completed_at']}. "
            f"Pool observations: {report['observations']}; research candidates: {report['candidates']}; "
            f"BUY candidates for manual review: {report.get('buy_candidates_delivered', 'unknown')}; "
            f"safety-reviewed entry WATCH alerts: {report.get('signed_entry_watches_delivered', 'unknown')}; "
            f"research WATCH alerts: {report.get('research_watch_delivered', 'unknown')}; "
            f"coverage warnings: {len(report['warnings'])}. "
            + details
            + ("No qualifying tokens found. " if report['candidates'] == 0 else "")
            + "Research only; not a buy signal. Run: " + run_url)


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
    if state.get("confirmed_day") == day:
        return {"status": "SKIPPED_DAILY_DEDUP", "github_run_id": run_id}
    if sender(workflow_message(mode)) is not True:
        raise NotificationError("Telegram digest receipt not confirmed")
    state.update(confirmed_day=day, confirmed_at=now.isoformat(), github_run_id=run_id)
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

