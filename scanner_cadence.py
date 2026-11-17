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


EXTERNAL = 'external'


def decide(event, state, now, trusted=False, trigger=None):
    """Run/skip decision. A dispatch carrying trigger='external' (an outside timer used
    because GitHub skips cron slots) is throttled exactly like a scheduled run; any
    other dispatch, including a missing or unknown trigger value, is a manual request
    and always runs. The input can only reduce runs, never add them."""
    if event == 'workflow_dispatch' and trigger != EXTERNAL:
        return True, 'explicitly requested scan'
    if event in ('schedule', 'workflow_dispatch'):
        attempt = age(state.get('last_attempt_at'), now)
        success = age(state.get('last_core_success_at'), now)
        if attempt is not None and attempt < 1200:
            return False, 'recent scan attempt; scheduled retry throttled'
        if success is not None and success < 3300:
            return False, 'core scan completed within 55 minutes'
        return True, 'scheduled scan due or heartbeat unavailable'
    if event != 'workflow_run':
        return True, 'push-triggered scan'
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


def audit_slots(runs, start, end):
    """Report observed starts per expected cron slot, not inferred scheduler causes.

    Input must be the scanner workflow's main-branch run history. A missing API
    record cannot distinguish a scheduler delay from incomplete history.
    """
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError('Ordered timezone-aware audit bounds required')
    slots=[]
    slot=start.replace(minute=7,second=0,microsecond=0)
    if slot < start:slot+=dt.timedelta(hours=1)
    while slot < end:
        stop=min(slot+dt.timedelta(hours=1),end)
        observed=[]
        for run in runs:
            if not isinstance(run,dict) or run.get('head_branch')!='main':continue
            try:
                at=dt.datetime.fromisoformat(str(run.get('run_started_at') or run.get('created_at')).replace('Z','+00:00'))
                if at.tzinfo is None:continue
            except ValueError:continue
            if slot<=at<stop:
                observed.append(dict(id=run.get('id'),event=run.get('event'),started_at=at.isoformat(),
                    status=run.get('status'),conclusion=run.get('conclusion'),url=run.get('html_url')))
        slots.append(dict(expected_at=slot.isoformat(),window_end=stop.isoformat(),runs=observed,
            status='START_OBSERVED_NOT_CORE_COMPLETION' if observed else 'NO_START_IN_SUPPLIED_HISTORY_CAUSE_UNKNOWN'))
        slot+=dt.timedelta(hours=1)
    return dict(start=start.isoformat(),end=end.isoformat(),slots=slots,
        missing_start_slots=sum(not x['runs'] for x in slots),hourly_guarantee=False,
        limitation='Start-window audit only; delayed cron attribution and missing-run causes are not established. History pagination and core-scan completion must be checked separately.')


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
        trusted = (source.get('conclusion') == 'success' and
                   source.get('head_branch') == 'main' and
                   (source.get('head_repository') or {}).get('full_name') == os.environ.get('GITHUB_REPOSITORY') and
                   source.get('event') in ('schedule', 'workflow_dispatch', 'push'))
        inputs = event.get('inputs')
        trigger = inputs.get('trigger') if isinstance(inputs, dict) else None
        run, reason = decide(os.environ.get('GITHUB_EVENT_NAME'), state, now, trusted, trigger)
        report = {'run': run, 'reason': reason, 'checked_at': now.isoformat(),
                  'github_run_id':run_id,
                  'last_core_success_at': state.get('last_core_success_at'),
                  'hourly_guarantee': False,
                  'core_success_age_seconds': age(state.get('last_core_success_at'),now),
                  'stale_or_missing_core_heartbeat': age(state.get('last_core_success_at'),now) is None or age(state.get('last_core_success_at'),now)>3900}
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
