"""Telegram delivery with bounded retries and credential-safe diagnostics."""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from oracle_http import retry_delay


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
    payload = urllib.parse.urlencode({"chat_id": chat, "text": bounded_text(message)}).encode()
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
    return (f"CRYPTO-ORACLE X100 hourly scan completed at {report['completed_at']}. "
            f"Pool observations: {report['observations']}; research candidates: {report['candidates']}; "
            f"separate candidate alerts delivered: {report['alerts_delivered']}; "
            f"coverage warnings: {len(report['warnings'])}. "
            + details
            + ("No qualifying tokens found. " if report['candidates'] == 0 else "")
            + "Research only; not a buy signal. Run: " + run_url)


if __name__ == "__main__":
    try:
        mode = sys.argv[1]
        if mode != "failure":
            report = json.loads(pathlib.Path("scan_summary.json").read_text(encoding="utf-8"))
            if os.environ.get("GITHUB_RUN_ID") and report.get("github_run_id") != os.environ["GITHUB_RUN_ID"]:
                raise NotificationError("Summary belongs to another workflow run")
        send_message(workflow_message(mode))
        if mode != "failure":
            pathlib.Path("operational_notification.json").write_text(json.dumps({
                "status": "BOT_API_CONFIRMED", "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
                "candidate_details_included": False}) + "\n", encoding="utf-8")
    except (NotificationError, OSError, ValueError, KeyError, IndexError) as exc:
        print(f"ERROR: Telegram workflow notification failed ({type(exc).__name__}). Inspect configuration and run logs.", flush=True)
        sys.exit(1)
