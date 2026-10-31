"""Persistent discovery rotation and selection history; no token approval state."""
import json
import pathlib
from asset_identity import key

VERSION = 1
MAX_IDENTITIES = 20000


def load(path):
    path = pathlib.Path(path)
    if not path.exists():
        return {'version': VERSION, 'cursor': 0, 'seen': {}}
    data = json.loads(path.read_text())
    if (data.get('version') != VERSION or type(data.get('cursor')) is not int
            or data['cursor'] < 0 or not isinstance(data.get('seen'), dict)):
        raise ValueError('Invalid persistent discovery state; refusing reset')
    for identity, row in data['seen'].items():
        if key(row['network'], row['token_address']) != identity or type(row['selections']) is not int or row['selections'] < 1:
            raise ValueError('Invalid retained discovery identity')
    return data


def prioritize(assets, state):
    seen = state['seen']
    return sorted(assets, key=lambda row: (
        seen.get(row['asset_key'], {}).get('last_selected_at', ''), row['asset_key']))


def update(state, assets, at, cursor):
    for asset in assets:
        identity = asset['asset_key']
        old = state['seen'].get(identity)
        if old is None and len(state['seen']) >= MAX_IDENTITIES:
            raise ValueError('Discovery history capacity reached; archive explicitly before admission')
        state['seen'][identity] = dict(network=asset['network'], token_address=asset['token_address'],
            first_selected_at=old['first_selected_at'] if old else at,
            last_selected_at=at, selections=(old['selections'] if old else 0) + 1)
    state['cursor'] = cursor


def save(state, path):
    path = pathlib.Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    temp.replace(path)
