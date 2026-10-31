"""Read-only StonkFun launch ledger. Origin is provider-attributed, not independently on-chain verified."""
import datetime as dt
import json
from urllib.request import Request, urlopen
from asset_identity import canonical, key

URL = "https://www.stonkfun.xyz/api/v2/launches/recent?limit=25&order=desc"

def parse_launches(payload):
    if not isinstance(payload, dict) or payload.get("degraded") is not False:
        raise ValueError("Launch ledger degraded or missing integrity marker")
    pools = payload.get("pools")
    if not isinstance(pools, list):
        raise ValueError("Launch ledger missing pools")
    rows = []
    invalid = 0
    for pool in pools:
        try:
            if not isinstance(pool, dict):
                raise ValueError("Invalid pool")
            mint = pool.get("mint") or pool.get("baseMint")
            mint = canonical("solana", mint)
            rows.append({"network": "solana", "token_address": mint,
                         "asset_key": key("solana", mint),
                         "source": "StonkFun official launch ledger",
                         "source_url": URL,
                         "launchpad": "stonk",
                         "launchpad_origin_status": "PROVIDER_ATTESTED — ONCHAIN VERIFICATION PENDING",
                         "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                         "buy_authorized": False})
        except (ValueError, TypeError, KeyError):
            invalid += 1
    return rows, invalid

def run(fetch=None):
    if fetch is None:
        def fetch(url):
            with urlopen(Request(url, headers={"User-Agent": "crypto-oracle-research/1.0"}), timeout=12) as response:
                if response.status != 200:
                    raise OSError("StonkFun non-200 response")
                return json.load(response)
    payload = fetch(URL)
    rows, invalid = parse_launches(payload)
    return {"mode": "READ_ONLY_RESEARCH", "provider": "StonkFun",
            "source_url": URL, "tokens": rows, "count": len(rows),
            "invalid_rows": invalid, "orders_allowed": False,
            "buy_authorized": False, "telegram_transmission": False}

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
