"""Fail-closed, persistent deduplication for Gate research alerts.

Uses local JSON state. A workflow must persist this file between runs; otherwise
deduplication does not survive fresh GitHub Actions runners.
"""
import datetime as dt
import json
import os
import pathlib
import tempfile

DEFAULT_COOLDOWN_HOURS = 24
MAX_RECORDS = 5000


def parse_utc(value):
    try:
        x = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return x.astimezone(dt.timezone.utc) if x.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def read_state(path):
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items()
            if isinstance(k, str) and isinstance(v, str) and parse_utc(v)}


def eligible_alerts(proposals, state, now=None, cooldown_hours=DEFAULT_COOLDOWN_HOURS,
                    max_alerts=3):
    """One research alert per pair per cooldown, no duplicate within a batch."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or cooldown_hours <= 0 or max_alerts < 0:
        raise ValueError("Invalid scheduling arguments")
    now = now.astimezone(dt.timezone.utc)
    chosen = []
    encountered = set()
    for p in proposals:
        pair = p.get("pair")
        if (not isinstance(pair, str) or not pair.endswith("_USDT")
                or p.get("status") != "WATCHLIST_ONLY" or pair in encountered):
            continue
        encountered.add(pair)
        prior = parse_utc(state.get(pair))
        if prior is not None:
            delta = (now - prior).total_seconds()
            if delta < 0 or delta < cooldown_hours * 3600:
                continue
        chosen.append(p)
        if len(chosen) >= max_alerts:
            break
    return chosen[:max_alerts]


def mark_delivered(state, pair, now=None):
    """Call ONLY after Telegram API confirms delivery."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    state[pair] = now.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
    if len(state) > MAX_RECORDS:
        sorted_keys = sorted(state, key=lambda key: parse_utc(state[key]) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
        for key in sorted_keys[:-MAX_RECORDS]:
            del state[key]


def save_state(path, state):
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic local replacement prevents partially written state files.
    fd, temp_path = tempfile.mkstemp(prefix=".gate_alerts_", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, sort_keys=True, indent=2)
            f.write("\n")
        os.replace(temp_path, target)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
