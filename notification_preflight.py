"""Read-only diagnostics for the CRYPTO-ORACLE Telegram delivery path.

No message is sent, no secrets are printed, and BUY eligibility is untouched.
Run: python notification_preflight.py
"""
import json
import os
from pathlib import Path


def inspect(environ=None, summary_path="scan_summary.json"):
    env = os.environ if environ is None else environ
    issues = []
    token_present = bool(env.get("TELEGRAM_BOT_TOKEN", "").strip())
    chat_present = bool(env.get("TELEGRAM_CHAT_ID", "").strip())
    if not token_present:
        issues.append("TELEGRAM_BOT_TOKEN missing")
    if not chat_present:
        issues.append("TELEGRAM_CHAT_ID missing")
    path = Path(summary_path)
    report = None
    if path.exists():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("summary is not an object")
        except (OSError, ValueError):
            issues.append("scan_summary.json unreadable")
            report = None
    else:
        issues.append("scan_summary.json missing; scanner may not have run")
    if report is not None and report.get("status") != "completed":
        issues.append("scanner has not recorded a completed run")
    return {
        "credentials_configured": token_present and chat_present,
        "scan_status": report.get("status", "unknown") if report else "unknown",
        "alerts_delivered": report.get("alerts_delivered") if report else None,
        "issues": issues,
        "delivery_verified": False,
        "note": "Read-only checks cannot confirm Bot API delivery; inspect notification job logs for message_id receipt.",
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), indent=2))
