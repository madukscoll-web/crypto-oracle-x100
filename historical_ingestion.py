"""Reproducible offline ingestion of explicitly supplied point-in-time evidence.

Archive hashes prove reproducibility, not authenticity. This command never fetches
modern prices to reconstruct missing historical observations or approves trading.
It refuses incomplete cohorts rather than silently discarding failed assets.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

from research_validation import score, stamp, validate_record


def _https(value):
    parsed = urlparse(value) if isinstance(value, str) else None
    return bool(parsed and parsed.scheme == 'https' and parsed.hostname
                and not parsed.username and not parsed.password)


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', delete=False) as output:
            name = output.name
            json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def ingest(manifest_path, *, now=None):
    """Validate complete archived records against a pre-outcome cohort inventory.

    A manifest records a cohort ID, selection_basis, selected_at, a universe with
    asset_keys/failed_asset_keys and dated source provenance, and sources containing
    relative path, SHA256, source_url, origin and captured_at. Source JSON objects
    contain records. Their measurements retain their own provenance. No claimed
    source URL or hash is treated as independent authentication.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware ingestion clock required')
    manifest_path = Path(manifest_path).resolve()
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported ingestion manifest schema')
    cohort_id = manifest.get('cohort_id')
    if not isinstance(cohort_id, str) or not cohort_id.strip():
        raise ValueError('Cohort identity missing')
    if manifest.get('selection_basis') != 'LAUNCH_COHORT_BEFORE_OUTCOMES':
        raise ValueError('Retrospective cohort selection is prohibited')
    selected = stamp(manifest['selected_at'])
    if selected > now:
        raise ValueError('Future cohort selection timestamp')
    universe = manifest['universe']
    if not _https(universe.get('source_url')) or not universe.get('origin'):
        raise ValueError('Cohort universe provenance missing')
    observed, available = stamp(universe['observed_at']), stamp(universe['available_at'])
    if observed > available or available > selected:
        raise ValueError('Cohort universe was not available at selection')
    identities, failed = universe['asset_keys'], universe['failed_asset_keys']
    if (not isinstance(identities, list) or not identities
            or any(not isinstance(x, str) or not x for x in identities)
            or len(set(identities)) != len(identities)):
        raise ValueError('Unique complete pre-outcome universe required')
    if (not isinstance(failed, list) or not failed
            or any(not isinstance(x, str) for x in failed)
            or len(set(failed)) != len(failed) or not set(failed) <= set(identities)):
        raise ValueError('Explicit failed-token inclusion inventory required')
    sources = manifest['sources']
    if not isinstance(sources, list) or not sources:
        raise ValueError('No historical source archives supplied')
    records, archives, seen_paths = [], [], set()
    for source in sources:
        relative = source['path']
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError('Source archive path must be relative to manifest')
        path = (manifest_path.parent / relative).resolve()
        if not path.is_relative_to(manifest_path.parent) or path in seen_paths:
            raise ValueError('Source archive outside manifest directory or duplicated')
        seen_paths.add(path)
        if not _https(source.get('source_url')) or not source.get('origin'):
            raise ValueError('Archive provenance missing')
        captured = stamp(source['captured_at'])
        if captured > now:
            raise ValueError('Future archive capture timestamp')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != source.get('sha256'):
            raise ValueError('Source archive SHA256 mismatch: ' + relative)
        payload = json.loads(raw)
        rows = payload.get('records') if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise ValueError('Archive must contain nonempty records array')
        for row in rows:
            if row.get('cohort_id') != cohort_id:
                raise ValueError('Record cohort identity mismatch')
            if selected > stamp(row['feature_at']):
                raise ValueError('Cohort selected after entry features')
            if stamp(row['label_available_at']) > captured:
                raise ValueError('Outcome label unavailable at archive capture')
            # Existing protocol validates identity, paired executable depth/costs,
            # and all required feature availability before producing any output.
            validate_record(row)
            model = 'meme-v1' if row['asset_type'] == 'meme' else 'utility-v1'
            score(row, model)
            for observation in row['features'].values():
                if stamp(observation['observed_at']) > stamp(observation['available_at']):
                    raise ValueError('Feature observation after claimed availability')
            records.append(row)
        archives.append({k: source[k] for k in
                         ('path', 'sha256', 'source_url', 'origin', 'captured_at')})
    keys = [row['asset_key'] for row in records]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate asset across historical archives')
    missing, extra = set(identities) - set(keys), set(keys) - set(identities)
    if missing or extra:
        raise ValueError('Incomplete cohort inventory: missing=' + ','.join(sorted(missing))
                         + '; unexpected=' + ','.join(sorted(extra)))
    # Explicit failure membership must agree with observed cost-adjusted outcomes.
    by_key = {row['asset_key']: row for row in records}
    if any(validate_record(by_key[key]) >= 1 for key in failed):
        raise ValueError('Failed-token inventory conflicts with executable outcome')
    return {
        'schema_version': 1, 'status': 'INGESTED_NOT_EXTERNALLY_VERIFIED',
        'scope': 'OFFLINE_SOURCE_CONSISTENCY_ONLY', 'records': records,
        'buy_authorized': False, 'orders_allowed': False,
        'ingestion': {'manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(),
                      'cohort_id': cohort_id, 'selected_at': manifest['selected_at'],
                      'universe': universe, 'sources': archives,
                      'record_count': len(records), 'failed_asset_count': len(failed)},
        'blockers': ['Archive hashes and asserted provenance do not authenticate independent sources',
                     'Representative coverage and genuine source authority require independent review'],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    manifest_path = Path(args.manifest).resolve()
    output_path, report_path = Path(args.output).resolve(), Path(args.report).resolve()
    # Never overwrite input evidence even while reporting a rejected invocation.
    if manifest_path in (output_path, report_path) or output_path == report_path:
        print('BLOCKED: output, report and manifest must be distinct paths')
        return 2
    report_safe = True
    try:
        raw_manifest = json.loads(manifest_path.read_bytes())
        archive_paths = {(manifest_path.parent / x['path']).resolve()
                         for x in raw_manifest.get('sources', [])}
        if report_path in archive_paths:
            report_safe = False
            raise ValueError('Report must not overwrite source archives')
        if output_path in archive_paths:
            raise ValueError('Output must not overwrite source archives')
        dataset = ingest(args.manifest)
        source_paths = {(Path(args.manifest).resolve().parent / x['path']).resolve()
                        for x in dataset['ingestion']['sources']}
        if Path(args.output).resolve() in source_paths or Path(args.report).resolve() in source_paths:
            raise ValueError('Outputs must not overwrite source archives')
        _atomic_json(args.output, dataset)
        report = {k: v for k, v in dataset.items() if k != 'records'}
        report['records'] = len(dataset['records'])
        _atomic_json(args.report, report)
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        if report_safe:
            _atomic_json(args.report, {'status': 'BLOCKED', 'error': str(exc),
                                      'buy_authorized': False, 'orders_allowed': False})
        else:
            print('BLOCKED: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
