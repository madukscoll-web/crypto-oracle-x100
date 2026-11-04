"""Fail-closed, bounded Telegram research summary. No buy orders or secrets in reports."""
import json
import pathlib

def summarize(report):
    if not isinstance(report, dict):
        raise ValueError("Invalid research report")
    if report.get("run_state") != "COMPLETED":
        raise ValueError("Research run incomplete")
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Candidate list unavailable")
    allowed = {"DISCARD", "WAIT AND VERIFY"}
    lines = ["CRYPTO-ORACLE independent research (not trading advice)",
             "Scope: bounded first-page research; not the entire market.",
             f"Discovery-filter candidates: {report.get('qualified_discovery_count', 'unknown')}",
             f"Independently assessed: {len(candidates)}"]
    counts = {"DISCARD": 0, "WAIT AND VERIFY": 0}
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("Invalid candidate")
        decision = item.get("decision")
        if decision not in allowed:
            raise ValueError("Unreviewed decision; refusing to notify")
        network = str(item.get("network", "unknown"))[:12]
        address = str(item.get("token_address", "UNVERIFIED"))[:45]
        blockers = item.get("mandatory_blockers")
        if not isinstance(blockers, list) or not blockers:
            raise ValueError("Missing mandatory evidence blockers")
        counts[decision] += 1
    if report.get("verified_buy_signals") not in ([], 0):
        raise ValueError("Unreviewed buy-signal schema; refusing to notify")
    lines.append("Suppressed internal outcomes: " + ", ".join(f"{label}={count}" for label, count in counts.items()))
    lines.append("VERIFIED BUY SIGNALS: 0. No automated trades.")
    lines.append("Unknown evidence is not a pass. Check full GitHub artifact.")
    return "\n".join(lines)

def main():
    import telegram_notify
    path = pathlib.Path("live_candidate_scan.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    telegram_notify.send_message(summarize(report))

if __name__ == "__main__":
    main()

