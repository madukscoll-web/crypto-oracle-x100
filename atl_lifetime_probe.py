"""Read-only production configuration evidence, never a positive ATL fixture."""
import datetime as dt
import json
import pathlib

import authenticated_admission as auth
import atl_lifetime


def inspect(now=None):
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    registry = atl_lifetime.load_registry()
    if (registry.get('schema') != atl_lifetime.SCHEMA
            or not isinstance(registry.get('sources'), dict)
            or not isinstance(registry.get('manifests'), dict)):
        raise ValueError('Invalid lifetime registry')
    trust = auth.load_trust()
    if trust.get('schema') != auth.VERSION or not isinstance(trust.get('reviewers'), dict):
        raise ValueError('Invalid independent trust registry')
    active = []
    for name, reviewer in trust['reviewers'].items():
        scopes = reviewer.get('scopes')
        if (isinstance(scopes, list) and 'atl_lifetime' in scopes
                and reviewer.get('revoked') is False
                and auth.stamp(reviewer['valid_from']) <= now < auth.stamp(reviewer['valid_until'])):
            active.append(name)
    summary, notice = atl_lifetime.collect([], now=now)
    if notice is not None:
        raise ValueError('No candidate may be fabricated for readiness checks')
    blockers = []
    if len(active) < 2: blockers.append('Two genuine independent lifetime-history reviewers required')
    if len(registry['sources']) < 2: blockers.append('Two genuinely independent complete history archives required')
    if not registry['manifests']: blockers.append('No authentic signed exact-asset lifetime manifests installed')
    return dict(status='BLOCKED_BY_EVIDENCE' if blockers else 'CONFIGURED_NOT_CANDIDATE_VERIFIED',
                observed_at=dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                enrolled_archive_sources=len(registry['sources']),
                enrolled_manifests=len(registry['manifests']), active_lifetime_reviewers=active,
                candidate_check=summary, blockers=blockers,
                notices_sent=0, buy_authorized=False, orders_allowed=False)


if __name__ == '__main__':
    result = inspect()
    pathlib.Path('work').mkdir(exist_ok=True)
    pathlib.Path('work/atl_lifetime_readiness.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
