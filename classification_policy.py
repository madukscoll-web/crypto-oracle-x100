"""Fail-closed Telegram message heading normalization.

This module formats existing classifications; it does not infer token age,
historical lows, verified safety, or BUY admission from market activity.
"""
HEADINGS = (
    "NEW COIN", "BULLISH REVERSAL", "ALL TIME LOW", "NEAR ALL TIME LOW",
    "RESEARCH WATCH", "BUY CANDIDATE — MANUAL REVIEW", "SYSTEM HEALTH REPORT",
)

def classify_existing_message(message):
    """Return a heading only when the message already carries its evidence context."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Nonempty Telegram message required")
    first = message.lstrip().splitlines()[0].strip()
    if first in HEADINGS:
        return first
    upper = first.upper()
    if "WORKFLOW FAILED" in upper or "DAILY PIPELINE HEALTH" in upper:
        return "SYSTEM HEALTH REPORT"
    if "BUY CANDIDATE — MANUAL REVIEW" in upper:
        # A heading alone cannot establish authorization; callers must have
        # authenticated admission before invoking this notification path.
        return "BUY CANDIDATE — MANUAL REVIEW"
    if "TECHNICAL WATCH" in upper:
        # This is a documented research hypothesis, NOT a confirmed reversal.
        return "RESEARCH WATCH"
    if "RESEARCH WATCH" in upper or "UNVERIFIED RESEARCH LEAD" in upper:
        return "RESEARCH WATCH"
    # Unknown paths are deliberately not promoted to NEW COIN / ATL / BUY.
    return "RESEARCH WATCH"

def format_message(message):
    """Add a supported first-line heading without discarding original context."""
    heading = classify_existing_message(message)
    if message.startswith(heading + "\n"):
        return message
    return heading + "\n" + message
