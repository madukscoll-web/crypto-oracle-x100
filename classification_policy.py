"""Conservative Telegram heading normalization.

Text and caller-provided dictionaries are never admission credentials.
Authenticated BUY notification requires a separately trusted admission path.
"""
HEADINGS = (
    "NEW TOKEN DISCOVERY", "EXISTING POOL DISCOVERY", "BULLISH REVERSAL WATCH", "ALL-TIME LOW WATCH",
    "NEW COIN", "BULLISH REVERSAL", "ALL TIME LOW", "NEAR ALL TIME LOW",
    "ATL RECOVERY WATCH", "UNVERIFIED ATL RESEARCH WATCH",
    "EARLY REVERSAL WATCH", "CONFIRMED TECHNICAL REVERSAL", "INVALIDATED SETUP",
    "EARLY BULLISH REVERSAL WATCH", "CONFIRMED BULLISH REVERSAL",
    "WAIT / VERIFY", "RESEARCH WATCH", "BUY CANDIDATE — MANUAL REVIEW", "SYSTEM HEALTH REPORT",
    "CRITICAL SYSTEM FAILURE",
)
_UNTRUSTED = frozenset(HEADINGS) - {"RESEARCH WATCH", "SYSTEM HEALTH REPORT", "CRITICAL SYSTEM FAILURE"}


def classify_opportunity(candidate_data: dict, admission_result: dict = None) -> str:
    """Research-only classification; supplied dictionaries cannot authorize BUY."""
    if not isinstance(candidate_data, dict):
        raise TypeError("candidate_data must be a dictionary")
    # admission_result is intentionally not trusted: a caller can forge its keys.
    return "RESEARCH WATCH"


def classify_existing_message(message):
    """No promotional heading may be inferred from untrusted message text."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Nonempty Telegram message required")
    first = message.lstrip().splitlines()[0].strip()
    upper = first.upper()
    # Operational notices claim no market evidence, so they may be preserved.
    if first == "CRITICAL SYSTEM FAILURE":
        return first
    if (first == "SYSTEM HEALTH REPORT" or upper.startswith("BOT HEALTH")
            or "WORKFLOW FAILED" in upper or "DAILY PIPELINE HEALTH" in upper):
        return "SYSTEM HEALTH REPORT"
    return "RESEARCH WATCH"


def format_message(message):
    """Normalize first-line heading without preserving an unsafe first-line claim."""
    heading = classify_existing_message(message)
    lines = message.lstrip().splitlines()
    first = lines[0].strip()
    if first == heading:
        return message
    if first in _UNTRUSTED:
        # Preserve evidence context but never repeat an unauthenticated BUY heading.
        lines[0] = "UNVERIFIED SOURCE LABEL (not an authenticated admission)"
        message = "\n".join(lines)
    return heading + "\n" + message

