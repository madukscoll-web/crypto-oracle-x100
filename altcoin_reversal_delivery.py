"""Bounded Telegram delivery for independently verified reversal WATCH reports.

State is stored as a JSON artifact; never sends BUY orders or credentials.
"""
import argparse
import json
import pathlib
import sys
from altcoin_reversal_alerts import select_watches, format_watch
from telegram_notify import send_message, NotificationError

def deliver(report, state, sender=send_message, max_alerts=3, persist=None):
    if type(max_alerts) is not int or not 1 <= max_alerts <= 10:
        raise ValueError('Invalid alert budget')
    if not isinstance(state, dict):
        raise ValueError("Invalid dedup state")
    previous = state.get("delivered", {})
    if not isinstance(previous, dict):
        raise ValueError("Invalid delivered state")
    updated = dict(previous)
    delivered = []
    watches = select_watches(report)
    for row in watches:
        if len(delivered) >= max_alerts:
            break
        research = row["research"]
        key = row["pair"] + "|" + research["interval"] + "|" + research["classification"]
        candle = str(row.get("latest_closed_candle", ""))
        if not candle or updated.get(key) == candle:
            continue
        if sender(format_watch(row)) is not True:
            raise NotificationError('Telegram receipt not confirmed')
        updated[key] = candle
        if persist is not None:
            persist({'version': 1, 'delivered': updated})
        delivered.append(key)
    return {"version": 1, "delivered": updated}, {
        "pairs_assessed": len(report["results"]),
        "research_watches": len(watches),
        "alerts_delivered": len(delivered),
        "unavailable": sum(r.get("status") != "RESEARCH_ONLY" for r in report["results"]),
        "buy_authorized": False
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    report = json.loads(pathlib.Path(args.report).read_text())
    state_path = pathlib.Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {"version": 1, "delivered": {}}
    def persist(snapshot):
        temporary = state_path.with_suffix(state_path.suffix + '.tmp')
        temporary.write_text(json.dumps(snapshot, indent=2))
        temporary.replace(state_path)
    new_state, summary = deliver(report, state, persist=persist)
    # Persist each confirmed receipt, including when a later send fails.
    persist(new_state)
    pathlib.Path(args.summary).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, NotificationError, json.JSONDecodeError) as exc:
        print("Reversal notification stage failed: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
