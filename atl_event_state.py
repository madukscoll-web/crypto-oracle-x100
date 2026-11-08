"""Persistent ATL watch-event admission; independent of BUY admission.

Caller must supply an evidence-qualified classification. This module never
approves a trade or claims Telegram delivery before an affirmative receipt.
"""
import hashlib
import json
import os
from pathlib import Path
from telegram_receipts import confirmed

WATCH_LABELS = frozenset({
    "ALL-TIME LOW | WATCH", "NEAR ALL-TIME LOW | WATCH",
    "LOWEST OBSERVED PRICE | WATCH", "NEAR OBSERVED LOW | WATCH",
    "ATL RECOVERY | TECHNICAL WATCH",
    "OBSERVED-LOW RECOVERY | TECHNICAL WATCH",
})
SCHEMA_VERSION = 1

def event_key(identity, label, baseline_id, evidence_revision):
    fields = (identity, label, baseline_id, evidence_revision)
    if any(not isinstance(x, str) or not x.strip() for x in fields):
        raise ValueError("Event identity, type, baseline and evidence revision required")
    if label not in WATCH_LABELS:
        raise ValueError("Not an ATL research event")
    return hashlib.sha256(json.dumps(fields, separators=(",", ":")).encode()).hexdigest()

def load_state(path):
    p = Path(path)
    if not p.exists():
        return {"schema_version": SCHEMA_VERSION, "confirmed": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported ATL state schema")
    if not isinstance(data.get("confirmed"), dict):
        raise ValueError("Corrupt ATL delivery state")
    return data

def eligible_event(state, key, *, identity_verified, observation_fresh,
                   history_validated, evidence_qualified, security_passed):
    if not all(type(x) is bool for x in (identity_verified, observation_fresh,
                                          history_validated, evidence_qualified,
                                          security_passed)):
        return False
    return (identity_verified and observation_fresh and history_validated
            and evidence_qualified and security_passed
            and key not in state["confirmed"])

def confirm_delivery(path, key, receipt, observed_at, *, expected_chat_id):
    """Record only a positive Telegram Bot API receipt; caller serializes writes.

    Ambiguous sends are NOT marked delivered. Caller must coordinate a
    single writer to prevent concurrent updates.
    """
    if not confirmed(receipt, expected_chat_id):
        return False
    result = receipt['result']
    if not isinstance(observed_at, str) or not observed_at:
        raise ValueError("Missing observation timestamp")
    state = load_state(path)
    state["confirmed"][key] = {"telegram_message_id": result["message_id"],
                                "observed_at": observed_at}
    target = Path(path)
    temp = target.with_name(target.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(state, f, sort_keys=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, target)
    return True

