"""Read-only Gate review backlog summary. Never approves tokens or sends alerts."""
import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(registry, report):
    tokens = registry.get("tokens", {})
    if not isinstance(tokens, dict):
        raise ValueError("Review registry tokens must be an object")
    summary = {"reviewed_registry_entries": len(tokens), "review_registry_empty": not bool(tokens),
               "review_required": not bool(tokens), "buy_authorized": False,
               "orders_allowed": False, "telegram_eligible": False,
               "candidate_blocker_counts": {}, "report_available": report is not None}
    if report is not None:
        if not isinstance(report, dict):
            raise ValueError("Gate candidate report must be an object")
        counts = Counter()
        def walk(value, depth=0):
            if depth > 5:
                return
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in ("blockers", "reasons") and isinstance(v, list):
                        for item in v:
                            if isinstance(item, str):
                                counts[item[:160]] += 1
                    elif isinstance(v, (dict, list)):
                        walk(v, depth+1)
            elif isinstance(value, list):
                for item in value[:1000]:
                    walk(item, depth+1)
        walk(report)
        summary["candidate_blocker_counts"] = dict(sorted(counts.items()))
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry", default="gate_token_reviews.json")
    p.add_argument("--report", default="gate_candidate_report.json")
    p.add_argument("--output", default="gate_review_backlog.json")
    a = p.parse_args()
    registry = json.loads(Path(a.registry).read_text(encoding="utf-8"))
    report_path = Path(a.report)
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    result = summarize(registry, report)
    Path(a.output).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
