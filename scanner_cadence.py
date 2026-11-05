"""Actual core-scan heartbeat and bounded, trusted companion-run recovery.

A successful scan is computation, not security verification or Telegram receipt.
"""
import argparse
import datetime as dt
import json
import os
import pathlib

STATE = pathlib.Path('scanner_runtime_state.json')


def age(value, now):
    try:
        stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return None
        seconds = (now - stamp).total_seconds()
        return seconds if seconds >= 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def decide(event, state, now, trusted=False):
    if event != 'workflow_run':
        return True, 'scheduled or explicitly requested scan'
    if not trusted:
        return False, 'untrusted companion event'
    attempt = age(state.get('last_attempt_at'), now)
    success = age(state.get('last_core_success_at'), now)
    if attempt is not None and attempt < 1200:
        return False, 'recent scan attempt; recovery throttled'
    if success is not None and success < 3900:
        return False, 'core scan completed within 65 minutes'
    return True, 'core scan overdue or heartbeat unavailable'


def finish(state, summary, run_id, outcome, now):
    result = dict(state)
    result['last_attempt_outcome'] = outcome
    if (outcome == 'success' and run_id and
            str(summary.get('github_run_id')) == run_id and
            summary.get('status') == 'completed'):
        result['last_core_success_at'] = now.isoformat()
        result['last_core_success_run_id'] = run_id
    result['scope'] = 'CORE_SCAN_COMPUTATION_ONLY_NOT_BUY_OR_DELIVERY_VERIFICATION'
    return result


def read(path):
    try:
        data = json.loads(pathlib.Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('guard', 'start', 'finish'))
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    state = read(STATE)
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if args.mode == 'guard':
        event = read(os.environ.get('GITHUB_EVENT_PATH', ''))
        source = event.get('workflow_run') or {}
        trusted = (source.get('head_branch') == 'main' and
                   (source.get('head_repository') or {}).get('full_name') == os.environ.get('GITHUB_REPOSITORY') and
                   source.get('event') in ('schedule', 'workflow_dispatch', 'push'))
        run, reason = decide(os.environ.get('GITHUB_EVENT_NAME'), state, now, trusted)
        report = {'run': run, 'reason': reason, 'checked_at': now.isoformat(),
                  'last_core_success_at': state.get('last_core_success_at'),
                  'hourly_guarantee': False}
        pathlib.Path('scanner_cadence_report.json').write_text(json.dumps(report, indent=2) + '\n')
        output = os.environ.get('GITHUB_OUTPUT')
        if output:
            with open(output, 'a') as target:
                target.write('run=' + str(run).lower() + '\n')
        print(json.dumps(report))
        return
    if args.mode == 'start':
        state.update(last_attempt_at=now.isoformat(), last_attempt_run_id=run_id,
                     last_attempt_outcome='in_progress')
    else:
        state = finish(state, read('scan_summary.json'), run_id,
                       os.environ.get('SCAN_OUTCOME', 'unknown'), now)
    STATE.write_text(json.dumps(state, indent=2) + '\n')


if __name__ == '__main__':
    main()
