"""Hourly-scan keep-alive: start the scanner on a reliable clock. Research only.

GitHub drops most scheduled cron events for this repo (16 full scans in 72h were
observed against a 20-minute cron). A single long-running job is not subject to
that: it dispatches the scanner with trigger=external every INTERVAL seconds, and
the scanner's cadence guard throttles those exactly like scheduled runs, so this
can never cause more than the intended hourly scans. Before the job's time limit
it dispatches a fresh copy of itself; a sparse cron restarts the loop if that
chain ever breaks. Uses only the workflow's own GITHUB_TOKEN (actions: write);
it reads and prints no secret and touches no trading code.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

SCANNER = "main.yml"
SELF = "keepalive.yml"
INTERVAL = 20 * 60
RUN_FOR = 340 * 60  # job timeout is 350 minutes; renew before it


def dispatch(repo, workflow, token, inputs=None, *, opener=urllib.request.urlopen):
    """POST a workflow_dispatch on main. Returns True on HTTP 204, False otherwise."""
    body = {"ref": "main"}
    if inputs:
        body["inputs"] = inputs
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "crypto-oracle-keepalive"})
    try:
        with opener(request, timeout=30) as response:
            return response.status == 204
    except (urllib.error.URLError, OSError, ValueError):
        return False


def loop(repo, token, *, clock=time.monotonic, sleep=time.sleep, send=dispatch, log=print,
         interval=INTERVAL, run_for=RUN_FOR):
    """Dispatch the scanner every interval until run_for elapses, then renew this loop."""
    start = clock()
    report = {"scanner_dispatches": 0, "scanner_failures": 0, "renewed": False}
    while True:
        if send(repo, SCANNER, token, {"trigger": "external"}):
            report["scanner_dispatches"] += 1
            log("Keep-alive: scanner dispatched (trigger=external); cadence guard decides whether it scans.")
        else:
            report["scanner_failures"] += 1
            log("Keep-alive: scanner dispatch failed; will retry next interval.")
        if clock() - start + interval >= run_for:
            break
        sleep(interval)
    report["renewed"] = send(repo, SELF, token)
    log(f"Keep-alive: loop renewed={report['renewed']}; report={report}")
    return report


def main():
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        print("Keep-alive: GITHUB_REPOSITORY and GITHUB_TOKEN are required.")
        return 1
    report = loop(repo, token)
    return 0 if report["scanner_dispatches"] and report["renewed"] else 1


if __name__ == "__main__":
    sys.exit(main())
