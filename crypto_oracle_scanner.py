"""CRYPTO-ORACLE Z: multichain, evidence-labelled crypto research alerts.

No contract audit, token inception date, price forecast, or calibrated return
probability is inferred from pool-level GeckoTerminal market data.
"""

import datetime as dt
import json
import hashlib
import math
import os
import pathlib
import time
import urllib.error
import urllib.parse

import signal_tracker
import canonical_outcomes
import forward_ledger
import traceback
import evidence_audit
import investment_gates
import fundamental_evidence
import evidence_checks
import research_records
import market_corroboration
import evidence_coverage
import hourly_evidence
import gate_spot_candidates
from oracle_http import get_json
from telegram_notify import send_message

API = "https://api.geckoterminal.com/api/v2"
# Override with comma-separated GeckoTerminal network IDs using ORACLE_NETWORKS.
# Network IDs and API availability must be checked against GeckoTerminal.
DEFAULT_NETWORKS = ("solana", "base", "eth", "bsc", "arbitrum", "polygon_pos", "avax", "optimism")
NETWORKS = tuple(x.strip() for x in os.environ.get(
    "ORACLE_NETWORKS", ",".join(DEFAULT_NETWORKS)).split(",") if x.strip())
SCAN_MODES = ("new_pools", "trending_pools")
DATA_SOURCE = "GeckoTerminal public API"
HEADERS = {
    "Accept": "application/json;version=20230302",
    "User-Agent": "CRYPTO-ORACLE-Z/0.3",
}
MIN_LIQUIDITY_USD = 50_000
MIN_24H_VOLUME_USD = 100_000
MIN_1H_TRANSACTIONS = 40
MAX_NEW_POOL_AGE_HOURS = 72
# Older pools can appear via trending_pools. These are NOT necessarily old tokens.
MIN_TRENDING_POOL_AGE_HOURS = 72
PAGES_PER_NETWORK = max(1, min(3, int(os.environ.get("ORACLE_PAGES", "1"))))
REQUEST_DELAY_SECONDS = 8
MAX_ALERTS_PER_RUN = max(1, min(10, int(os.environ.get("ORACLE_MAX_ALERTS", "4"))))
NEW_POOL_TARGET_SHARE = 0.70  # Minimum priority allocation when enough new candidates qualify.
STATE_FILE = pathlib.Path("reported_pools.json")
WATCH_STATE_FILE = pathlib.Path("watchlist_state.json")
# Enrichment is limited to selected, not all discovered pools, to control API use.
SECURITY_CHAIN_IDS = {"eth": "1", "bsc": "56", "polygon_pos": "137",
                      "arbitrum": "42161", "base": "8453", "optimism": "10",
                      "avax": "43114"}
ENRICHMENT_DELAY_SECONDS = 4



def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def fetch_json(url):
    return get_json(url, headers=HEADERS)


def missing_market_fields(item):
    """Require actual finite observations; unknown values never become zero."""
    missing = []
    for field in ("liquidity", "volume", "trades", "buy_share", "change_h1", "change_h24"):
        value = item.get(field)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or fundamental_evidence.finite(value, minimum=-math.inf) is None):
            missing.append(field)
        elif (field == "liquidity" and value <= 0
              or field in ("volume", "trades") and value < 0
              or field == "trades" and value != int(value)
              or field == "buy_share" and not 0 <= value <= 1):
            missing.append(field)
    return missing


def display_measurement(value, spec):
    value = fundamental_evidence.finite(value)
    return "UNKNOWN" if value is None else format(value, spec)


def inspect(pool, network, mode="new_pools"):
    """Score observed pool activity; never infer contract or token safety."""
    attrs = pool.get("attributes") or {}
    created = attrs.get("pool_created_at")
    if not created:
        return None
    try:
        timestamp = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        age_hours = (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds() / 3600
    except (TypeError, ValueError, OverflowError):
        return None
    if age_hours < 0:
        return None
    if mode == "new_pools" and age_hours > MAX_NEW_POOL_AGE_HOURS:
        return None
    if mode == "trending_pools" and age_hours < MIN_TRENDING_POOL_AGE_HOURS:
        return None

    liquidity = number(attrs.get("reserve_in_usd"))
    volume = number((attrs.get("volume_usd") or {}).get("h24"))
    h1 = (attrs.get("transactions") or {}).get("h1") or {}
    buys = int(max(0, number(h1.get("buys"))))
    sells = int(max(0, number(h1.get("sells"))))
    trades = buys + sells
    if (liquidity < MIN_LIQUIDITY_USD or volume < MIN_24H_VOLUME_USD
            or trades < MIN_1H_TRANSACTIONS):
        return None

    address = attrs.get("address") or (pool.get("id") or "").removeprefix(network + "_")
    if not address:
        return None
    name = attrs.get("name") or "Unnamed pool"
    buy_share = buys / trades if trades else 0
    volume_liquidity = volume / liquidity if liquidity else 0
    changes = attrs.get("price_change_percentage") or {}
    change_h1 = number(changes["h1"]) if changes.get("h1") is not None else None
    change_h24 = number(changes["h24"]) if changes.get("h24") is not None else None

    # Activity score (0-100). Deliberately excludes contract security.
    score = 0
    score += 25 if liquidity >= 250_000 else 15 if liquidity >= 100_000 else 8
    score += 25 if volume >= 1_000_000 else 15 if volume >= 300_000 else 8
    score += 20 if trades >= 200 else 12 if trades >= 100 else 6
    score += 15 if 0.45 <= buy_share <= 0.70 else 8 if 0.35 <= buy_share <= 0.80 else 0
    score += 15 if 0.5 <= volume_liquidity <= 10 else 7 if volume_liquidity <= 20 else 0
    flags = []
    if buy_share < 0.35:
        flags.append("Sell-heavy trading in last hour")
    if buy_share > 0.80:
        flags.append("Buy-heavy trading; authenticity unverified")
    if volume_liquidity > 20:
        flags.append("Very high 24h volume relative to liquidity")
    if volume_liquidity > 10:
        flags.append("Elevated volume/liquidity ratio: investigate wash trading")
    if buys + sells > 0 and min(buys, sells) / (buys + sells) < 0.10:
        flags.append("Strongly one-sided transaction flow: investigate manipulation")
    if age_hours < 1:
        flags.append("Pool younger than one hour")

    safe_address = urllib.parse.quote(address, safe="")
    return {
        "key": f"{network}:{address}",
        "discovery_token_hint": (((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", ""),
        "network": network,
        "address": address,
        "name": name,
        "age_hours": age_hours,
        "pool_class": "NEW POOL" if age_hours <= 72 else "EXISTING POOL",
        "token_age": "UNKNOWN — pool creation does not establish token launch date",
        "discovery_mode": mode,
        "source": DATA_SOURCE,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "contract_security": "NOT VERIFIED",
        "holder_concentration": "NOT VERIFIED",
        "liquidity_lock": "NOT VERIFIED",
        "return_probabilities": "UNAVAILABLE — no validated historical probability model",
        "liquidity": liquidity,
        "base_token_price_usd": number(attrs.get("base_token_price_usd")),
        "price_source": "GeckoTerminal pool base_token_price_usd at discovery (not executable)",
        "volume": volume,
        "buys": buys,
        "sells": sells,
        "trades": trades,
        "buy_share": buy_share,
        "change_h1": change_h1,
        "change_h24": change_h24,
        "score": score,
        "flags": flags,
        "url": f"https://www.geckoterminal.com/{network}/pools/{safe_address}",
    }


def _relationship_token(payload, relation):
    """Extract an address only when GeckoTerminal includes a matching token object."""
    relationships = (payload.get("data") or {}).get("relationships") or {}
    identifier = ((relationships.get(relation) or {}).get("data") or {}).get("id")
    for entry in payload.get("included") or []:
        if entry.get("type") == "token" and entry.get("id") == identifier:
            attrs = entry.get("attributes") or {}
            return attrs.get("address"), attrs.get("symbol") or "UNKNOWN"
    return None, None


def _risk_indicator(label, value, positive_is_risk=True):
    """GoPlus flags: 1/0 are observations, not a full audit."""
    if str(value) not in ("0", "1"):
        return None
    risky = str(value) == ("1" if positive_is_risk else "0")
    return f"{label}: {'FLAGGED' if risky else 'not flagged by provider'}"


def risk_gate(info, holder_total=None, holder_count=0):
    """Conservative, explainable triage; never a contract audit or buy signal.

    Only explicit 0/1 provider values are interpreted. Missing values are unknown.
    Top-holder percentages are descriptive only because LP/contract exclusions
    and the completeness of the holder list are not established.
    """
    critical = {"is_honeypot": "Provider reports honeypot",
                "owner_change_balance": "Owner can change balances",
                "hidden_owner": "Hidden owner",
                "is_blacklisted": "Blacklist functionality reported",
                "cannot_sell_all": "Provider reports token cannot be fully sold"}
    concerning = {"is_open_source": ("0", "Source not reported open by provider"),
                  "is_mintable": ("1", "Minting capability reported"),
                  "trading_cooldown": ("1", "Trading cooldown reported")}
    findings = []
    severe = False
    for field, description in critical.items():
        if str(info.get(field)) == "1":
            findings.append(f"{field}=1: {description}")
            severe = True
    for field, (bad, description) in concerning.items():
        if str(info.get(field)) == bad:
            findings.append(f"{field}={bad}: {description}")
    # Descriptive holder percentages are not themselves evidence of a contract
    # vulnerability. Keep them in holder_details, not the security-failure list.
    if severe:
        return "AVOID / HIGH CONCERN", findings
    if findings:
        return "WAIT / VERIFY", findings
    # Never promote a token based on only one negative provider flag.
    # All core checks must be explicitly present; unknown means WAIT.
    required = ("is_honeypot", "owner_change_balance", "hidden_owner",
                "is_blacklisted", "cannot_sell_all", "is_open_source",
                "is_mintable", "trading_cooldown")
    missing = [field for field in required
               if str(info.get(field)) not in ("0", "1")]
    if missing:
        return "WAIT / VERIFY", (["Holder concentration is descriptive only; LP/exclusions unknown."] if holder_total is not None else []) + [
            "Missing or uninterpretable provider security fields: "
            + ", ".join(missing)]
    # No flagged issues in the core provider fields is NOT proof of safety.
    return "RESEARCH CANDIDATE — LIMITED CHECKS", ([
        "Holder concentration is descriptive only; LP/exclusions unknown."] if holder_total is not None else []) + [
        "No specified risk flags detected in returned fields; not proof of safety"]


def risk_gate_unavailable(reason):
    return "WAIT / VERIFY", [reason]


def enrich(item, fetch=None, delay=None):
    """Best-effort token identification; never suppress an alert on API failure."""
    item.update(token_address="UNVERIFIED", token_symbol="UNVERIFIED",
                previous_pools="UNKNOWN", security_source="NOT CHECKED",
                security_details="UNVERIFIED", holder_details="UNVERIFIED",
                token_identity_status="UNVERIFIED", risk_category="WAIT / VERIFY",
                risk_reasons=["Token identity or security checks incomplete"],
                security_fields="NOT AVAILABLE",
                sellability_verified=False, liquidity_lock_verified=False,
                holder_distribution_verified=False, tokenomics_verified=False,
                entry_risk_reviewed=False, executable_quote_verified=False,
                slippage_verified=False)
    # A failed or partial refresh must not reuse discovery measurements as fresh.
    for field in ("liquidity", "volume", "buys", "sells", "trades", "buy_share", "change_h1", "change_h24"):
        item[field] = None
    item.update(base_token_price_usd=0, price_source="Pool price refresh unavailable")
    item.pop("market_raw", None)
    network = item["network"]
    fetch = fetch or fetch_json
    delay = ENRICHMENT_DELAY_SECONDS if delay is None else delay
    try:
        pool_url = f"{API}/networks/{urllib.parse.quote(network, safe='')}/pools/{urllib.parse.quote(item['address'], safe='')}?include=base_token,quote_token"
        payload = fetch(pool_url)
        returned_pool = ((payload.get("data") or {}).get("attributes") or {}).get("address")
        if not fundamental_evidence.same_address(network, returned_pool, item["address"]):
            item["token_identity_status"] = "UNVERIFIED (returned pool identity mismatch)"
            return item
        # Never carry stale discovery liquidity, volume or trade counts into a refreshed assessment.
        attrs = (payload.get("data") or {}).get("attributes") or {}
        fresh_liquidity = fundamental_evidence.finite(attrs.get("reserve_in_usd"))
        fresh_volume = fundamental_evidence.finite((attrs.get("volume_usd") or {}).get("h24"))
        tx = (attrs.get("transactions") or {}).get("h1") or {}
        counts = [fundamental_evidence.finite(tx.get(field)) for field in ("buys", "sells")]
        item["buys"], item["sells"] = [int(x) if x is not None and x.is_integer() else None for x in counts]
        item["liquidity"] = fresh_liquidity if fresh_liquidity is not None and fresh_liquidity > 0 else None
        item["volume"] = fresh_volume
        item["trades"] = item["buys"] + item["sells"] if all(x is not None for x in (item["buys"], item["sells"])) else None
        item["buy_share"] = item["buys"] / item["trades"] if item["trades"] else None
        changes = attrs.get("price_change_percentage") or {}
        for field in ("h1", "h24"):
            item["change_" + field] = fundamental_evidence.finite(changes.get(field), minimum=-math.inf)
        item["market_raw"] = payload
        # Refresh the indicative pool price at enrichment time. An absent or
        # malformed price must never inherit a potentially stale discovery quote.
        refreshed_price = number(((payload.get("data") or {}).get("attributes") or {}).get("base_token_price_usd"))
        item["base_token_price_usd"] = (
            refreshed_price if math.isfinite(refreshed_price) and refreshed_price > 0 else 0
        )
        item["observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        item["price_source"] = (
            "GeckoTerminal pool base_token_price_usd refreshed during enrichment; indicative only"
            if item["base_token_price_usd"] else "GeckoTerminal refresh did not return a valid price"
        )
        address, symbol = _relationship_token(payload, "base_token")
        if not address:
            item["token_identity_status"] = "UNVERIFIED (base-token relationship unavailable)"
            return item
        item["token_address"] = address
        item["quote_token_address"] = _relationship_token(payload, "quote_token")[0]
        item["token_symbol"] = symbol
        item["token_identity_status"] = "Base token from GeckoTerminal pool relationship"
    except (urllib.error.URLError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, OSError) as exc:
        print(f"Enrichment identity unavailable for {item['key']}: {type(exc).__name__}", flush=True)
        return item
    finally:
        time.sleep(delay)

    # A first-page check can prove older pools exist, but cannot prove none exist.
    try:
        url = (f"{API}/networks/{urllib.parse.quote(network, safe='')}/tokens/"
               f"{urllib.parse.quote(address, safe='')}/pools?page=1")
        response = fetch(url)
        older = 0
        for pool in response.get("data") or []:
            created = (pool.get("attributes") or {}).get("pool_created_at")
            if not created:
                continue
            try:
                when = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=dt.timezone.utc)
                if (dt.datetime.now(dt.timezone.utc) - when).total_seconds() > 72 * 3600:
                    older += 1
            except (ValueError, TypeError, OverflowError):
                continue
        item["previous_pools"] = (f"YES: {older} older pools on first API page" if older
                                  else "NOT FOUND on first API page (not proof of absence)")
    except (urllib.error.URLError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, OSError) as exc:
        print(f"Previous-pool check unavailable for {item['key']}: {type(exc).__name__}", flush=True)
    finally:
        time.sleep(delay)

    chain_id = SECURITY_CHAIN_IDS.get(network)
    if not chain_id or not address.lower().startswith("0x"):
        item["security_source"] = "GoPlus not queried for this network/address"
        return item
    try:
        params = urllib.parse.urlencode({"contract_addresses": address})
        url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?{params}"
        payload = fetch(url)
        if payload.get("code") != 1:
            item["security_source"] = "GoPlus did not report successful response; UNVERIFIED"
            return item
        result = payload.get("result") or {}
        info = result.get(address.lower()) or result.get(address) or {}
        if not isinstance(info, dict) or not info:
            item["security_source"] = "GoPlus: no matching token report returned"
            return item
        item["security_source"] = "GoPlus token_security API (provider data; not an audit)"
        # Preserve provider provenance; never promote this to independent verification.
        item["security_provider_evidence"] = {
            "provider": "GoPlus", "chain_id": str(chain_id),
            "contract_address": address, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "fields_present": sorted(str(k) for k in info.keys()),
            "response_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "source_url": url, "network": network,
            "values": {"total_supply": info.get("total_supply")},
            "status": "PROVIDER OBSERVATION — NOT INDEPENDENT AUDIT",
            "findings": {k: info.get(k) for k in (
                "is_honeypot", "owner_change_balance", "hidden_owner",
                "is_blacklisted", "cannot_sell_all", "is_open_source",
                "is_mintable", "trading_cooldown")},
        }
        # Supply, FDV, holders and vesting are intentionally not inferred from
        # incomplete security API fields or from pool activity.
        item["security_fields"] = "; ".join(
            f"{field}={info.get(field)}" for field in
            ("is_honeypot", "owner_change_balance", "hidden_owner",
             "is_blacklisted", "cannot_sell_all", "is_open_source",
             "is_mintable", "trading_cooldown")
            if str(info.get(field)) in ("0", "1")) or "No interpretable 0/1 fields"
        checks = [
            _risk_indicator("Honeypot", info.get("is_honeypot")),
            _risk_indicator("Trading cooldown", info.get("trading_cooldown")),
            _risk_indicator("Owner can change balance", info.get("owner_change_balance")),
            _risk_indicator("Hidden owner", info.get("hidden_owner")),
            _risk_indicator("Mintable", info.get("is_mintable")),
            _risk_indicator("Blacklist", info.get("is_blacklisted")),
            _risk_indicator("Cannot sell all", info.get("cannot_sell_all")),
            _risk_indicator("Open source", info.get("is_open_source"), positive_is_risk=False),
        ]
        checks = [check for check in checks if check]
        item["security_details"] = "; ".join(checks) if checks else "No interpretable provider flags"
        holder_total = None
        holder_count = 0
        holders = info.get("holders")
        if isinstance(holders, list) and holders:
            percentages = []
            for holder in holders[:10]:
                try:
                    pct = float(holder.get("percent"))
                    if 0 <= pct <= 1:
                        percentages.append(pct)
                except (TypeError, ValueError):
                    pass
            if percentages:
                holder_total = sum(percentages)
                holder_count = len(percentages)
                item["holder_details"] = (f"Provider's first {len(percentages)} listed holders: "
                                          f"{holder_total:.1%} combined; exclusions/LP unknown")
        item["risk_category"], item["risk_reasons"] = risk_gate(info, holder_total, holder_count)
    except (urllib.error.URLError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, OSError) as exc:
        print(f"GoPlus security unavailable for {item['key']}: {type(exc).__name__}", flush=True)
        item["security_source"] = "GoPlus unavailable; NOT VERIFIED"
    finally:
        time.sleep(delay)
    return item


def load_state():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(item) for item in data}
        if isinstance(data, dict):
            # Backward compatible with earlier state file: {"base:address": ...}
            return {str(key) for key in data}
        raise ValueError("State file must contain a JSON object or array")
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot safely load existing alert history: {exc}") from exc


def save_state(seen):
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(sorted(seen), indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE_FILE)


def strategy(item):
    """Non-personalized research process, not a trading recommendation."""
    if item["pool_class"] == "NEW POOL":
        return ("WAIT / RESEARCH: verify token contract, ownership, sellability, "
                "liquidity withdrawal risk and holder distribution before considering exposure")
    return ("RESEARCH / WATCH: verify token inception date, fundamentals, "
            "supply unlocks and longer price history before considering any entry")


def horizon_notes():
    return (
        "3 months: monitor liquidity persistence, activity and severe downside risk; "
        "probability unavailable.\n"
        "12 months: investigate adoption, supply dilution and token survival; "
        "probability unavailable.\n"
        "3 years: investigate team execution, security history and long-term tokenomics; "
        "probability unavailable."
    )


def decision_summary(item):
    """Evidence-based action; never turn activity scores into buy advice."""
    risk = item.get("risk_category", "WAIT / VERIFY")
    if any(((item.get("evidence_review") or {}).get(key) or {}).get("status") == "HIGH CONCERN"
           for key in ("security", "provider_security")):
        return "DISCARD", "Source-bound security observations report critical concerns; independently investigate."
    # Reject independently observed sellability failures for the exact chain, token and pool.
    sell = ((item.get("verification") or {}).get("sellability") or {})
    raw = sell.get("raw") or {}
    if (sell.get("status") in ("FAIL", "HIGH CONCERN")
            and sell.get("source") == "honeypot"
            and isinstance(raw, dict)
            and str((raw.get("token") or {}).get("address", "")).lower() == str(item.get("token_address", "")).lower()
            and str(raw.get("pairAddress", "")).lower() == str(item.get("address", "")).lower()
            and str((raw.get("chain") or {}).get("id", "")) == {"eth": "1", "bsc": "56", "base": "8453"}.get(item.get("network"))
            and (raw.get("honeypotResult") or {}).get("isHoneypot") is True):
        return "DISCARD", "Exact-pool independent honeypot evidence failed sellability verification."
    reasons = item.get("risk_reasons") or []
    if risk == "AVOID / HIGH CONCERN":
        detail = reasons[0] if reasons else "Critical provider risk flag reported."
        return "DISCARD", (
            f"Critical security concern: {detail}. Do not treat high volume "
            "or activity as a reason to override this warning."
        )
    if item.get("token_identity_status", "").startswith("UNVERIFIED"):
        return "WAIT AND VERIFY", (
            "Token identity could not be verified. Confirm the exact contract "
            "and independently check sellability, holders, and liquidity lock."
        )
    if item.get("market_corroboration", {}).get("status") == "CONFLICTING":
        return "WAIT AND VERIFY", "Independent market-data conflict: verify exact pool, token and current price."
    if item.get("discovery_eligible") is False:
        return "WAIT AND VERIFY", "This is verification-only research; discovery eligibility is not established."
    if sell.get("status") in ("FAIL", "CONFLICTING", "HIGH CONCERN"):
        return "WAIT AND VERIFY", "Independent sellability evidence failed or conflicts; exact binding requires investigation."
    if item.get("scan_mode") == "verification_only":
        return "WAIT AND VERIFY", "This is verification-only research; no entry qualification is permitted."
    missing = missing_market_fields(item)
    if missing:
        detail = reasons[0] if reasons else "Independent evidence is incomplete."
        return "WAIT AND VERIFY", detail + " Missing or invalid market observations: " + ", ".join(missing) + "; provider checks are not a contract audit."
    # An independent, source-bound audit is mandatory; never accept caller-set
    # booleans or a synthetic quote as sufficient evidence.
    if evidence_audit.audit(item)["trade_ready"] is not True:
        detail = reasons[0] if reasons else "Provider checks are not a contract audit."
        return "WAIT AND VERIFY", (
            f"{detail} Independent security, sellability, tokenomics and execution "
            "evidence is incomplete; provider checks are not a contract audit."
        )
    # A BUY CANDIDATE is permitted only after independent verification.
    # These fields are not inferred from activity scores or missing API data.
    if (risk == "RESEARCH CANDIDATE — LIMITED CHECKS"
            and item.get("token_identity_status") ==
                "Base token from GeckoTerminal pool relationship"
            and item.get("sellability_verified") is True
            and item.get("liquidity_lock_verified") is True
            and item.get("holder_distribution_verified") is True
            and item.get("tokenomics_verified") is True
            and item.get("entry_risk_reviewed") is True
            and item.get("executable_quote_verified") is True
            and item.get("slippage_verified") is True
            and validate_execution_evidence(item) is True
            and item.get("market_corroboration", {}).get("status") == "CORROBORATED"
            and price_evidence(item)[0] is True
            and not any("wash trading" in f or "manipulation" in f for f in item.get("flags", []))
            and item.get("score", 0) >= 70
            and item.get("liquidity", 0) >= 250_000
            and item.get("volume", 0) >= 300_000
            and 0.45 <= item.get("buy_share", 0) <= 0.70):
        return "BUY CANDIDATE — REVIEW ENTRY", (
            "Market activity meets screening thresholds and independent "
            "verification fields are explicitly confirmed. Review live price, "
            "slippage, position sizing and exit plan before any order. "
            "Not a guaranteed profit or automatic buy instruction."
        )
    if risk == "RESEARCH CANDIDATE — LIMITED CHECKS":
        missing = [
            label for field, label in (
                ("sellability_verified", "independent sellability test"),
                ("liquidity_lock_verified", "liquidity-lock evidence"),
                ("holder_distribution_verified", "holder distribution review"),
                ("tokenomics_verified", "tokenomics and unlock review"),
                ("entry_risk_reviewed", "entry price and downside plan"),
                ("executable_quote_verified", "executable order quote"),
                ("slippage_verified", "slippage verification"),
            ) if item.get(field) is not True
        ]
        if item.get("market_corroboration", {}).get("status") != "CORROBORATED":
            missing.append("independent exact-pool market-price corroboration")
        if not validate_execution_evidence(item):
            missing.append("fresh quote bound to exact network, token and pool")
        if not price_evidence(item)[0]:
            missing.append("fresh, valid pool price")
        if any("wash trading" in f or "manipulation" in f for f in item.get("flags", [])):
            missing.append("unresolved abnormal trading activity")
        if item.get("score", 0) < 70:
            missing.append("activity score below 70")
        if item.get("liquidity", 0) < 250_000:
            missing.append("liquidity below $250,000")
        if item.get("volume", 0) < 300_000:
            missing.append("24h volume below $300,000")
        if not 0.45 <= item.get("buy_share", 0) <= 0.70:
            missing.append("buy share outside 45–70% screening range")
        return "WAIT AND VERIFY", (
            "Provider's core security flags have no detected concerns; this is not a contract audit, "
            "but BUY CANDIDATE requirements remain unmet: "
            + ", ".join(missing[:5])
            + (f" (plus {len(missing)-5} more)" if len(missing) > 5 else "")
            + ". These checks are not inferred from trading activity."
        )
    detail = reasons[0] if reasons else "Security evidence is incomplete."
    return "WAIT AND VERIFY", (
        f"{detail}. Do not buy until independent contract, liquidity, "
        "holder and sellability checks are satisfactory."
    )


def validate_execution_evidence(item):
    """No authenticated execution adapter exists; caller claims cannot authorize.

    evidence_checks.quotes reports source-bound metrics separately. Even valid
    metrics do not prove authenticity, successful simulation, or sellability.
    """
    return False



def price_evidence(item):
    """Require recent observation and a positive finite pool price."""
    import math
    price = number(item.get("base_token_price_usd"))
    if not math.isfinite(price) or price <= 0:
        return False, "Missing, invalid or nonpositive pool price"
    observed = item.get("observed_at")
    if not observed:
        return False, "Missing price observation timestamp"
    try:
        stamp = dt.datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False, "Price timestamp has no timezone"
        age = (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return False, "Invalid price observation timestamp"
    if age < -60 or age > 300:
        return False, "Pool price observation is stale or future-dated"
    return True, "Recent GeckoTerminal pool observation (indicative, not executable)"


def investment_plan(item, decision):
    """Naira-denominated conservative plan; no assumed exchange rate."""
    if decision != "BUY CANDIDATE — REVIEW ENTRY":
        return ""
    budget_ngn = max(0, number(os.environ.get("ORACLE_BUDGET_NGN", "200000")))
    risk_fraction = min(0.02, max(0, number(os.environ.get("ORACLE_RISK_FRACTION", "0.01"))))
    max_allocation_fraction = min(0.25, max(0, number(os.environ.get("ORACLE_MAX_ALLOCATION_FRACTION", "0.10"))))
    position_ngn = budget_ngn * max_allocation_fraction
    max_planned_loss_ngn = budget_ngn * risk_fraction
    price = number(item.get("base_token_price_usd"))
    price_source = item.get("price_source", "UNVERIFIED")
    price_ok, price_status = price_evidence(item)
    lines = [
        "",
        "INVESTMENT PLAN (ILLUSTRATIVE; NOT A TRADE ORDER)",
        f"Total speculative budget: NGN {budget_ngn:,.0f}",
        f"Illustrative maximum allocation: NGN {position_ngn:,.0f} ({max_allocation_fraction:.0%} of budget; not a trade order)",
        f"Illustrative risk budget: NGN {max_planned_loss_ngn:,.0f} ({risk_fraction:.1%} of budget; not guaranteed)",
        "USD order amount: UNAVAILABLE until a verified NGN/USD rate is supplied.",
        "CONCENTRATION WARNING: a single token can lose its entire allocation; stops can slip or fail.",
    ]
    if not price_ok:
        lines.append(f"Entry/exit prices: UNAVAILABLE — {price_status}. Refresh before trading.")
    else:
        lines.extend([
            f"Price evidence: {price_source}; {price_status}",
            f"Observed pool token price: USD {price:.10g} (indicative only)",
            "Entry/stop/targets: UNAVAILABLE — historical structure and executable quote required.",
        ])
    lines.append("Executable quote/slippage: NOT VERIFIED. A pool quote is not a tradeable offer.")
    lines.append("Do not execute without verifying live price, fees, slippage and token risks. "
                 "Stops may slip; actual loss can exceed the planned amount.")
    return chr(10).join(lines)


def load_watchlist():
    if not WATCH_STATE_FILE.exists():
        return {}
    data = json.loads(WATCH_STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Watchlist must be a JSON object")
    return data


def save_watchlist(data):
    temp = WATCH_STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(WATCH_STATE_FILE)


def watchlist_transition(item, watchlist):
    key = item["key"]
    setup, _ = setup_assessment(item)
    previous = watchlist.get(key, {}).get("setup")
    checked_at = watchlist.get(key, {}).get("evidence_checked_at", "")
    if (item.get("hourly_evidence") or {}).get("status") == "COLLECTED":
        checked_at = item["observed_at"]
    watchlist[key] = {"evidence_checked_at": checked_at, "setup": setup, "observed_at": item["observed_at"],
                      "score": item["score"], "network": item["network"],
                      "pool_address": item["address"]}
    if setup == "PRIORITY VERIFY" and previous != "PRIORITY VERIFY":
        return "UPGRADED TO PRIORITY" if previous else "NEW PRIORITY SETUP"
    return None


def entry_setup(item):
    """Classify observed market structure, not independently verified buy eligibility."""
    ok, reason = price_evidence(item)
    if not ok:
        return "NO SETUP", reason
    if item.get("risk_category") == "AVOID / HIGH CONCERN":
        return "NO SETUP", "Critical security concern"
    missing = missing_market_fields(item)
    if missing:
        return "INSUFFICIENT DATA", "Missing or invalid market observations: " + ", ".join(missing)
    h1 = item.get("change_h1")
    h24 = item.get("change_h24")
    if h1 is None or h24 is None:
        return "INSUFFICIENT DATA", "Price-change fields missing"
    if h1 > 35 or h24 > 120:
        return "OVEREXTENDED", "Sharp acceleration: do not chase"
    liquidity = item.get("liquidity", 0)
    volume = item.get("volume", 0)
    share = item.get("buy_share", 0)
    trades = item.get("trades", 0)
    if liquidity < 250000 or volume < 300000 or trades < 100:
        return "WAIT", "Insufficient liquidity, volume or trades"
    if 2 <= h1 <= 12 and 5 <= h24 <= 35 and 0.52 <= share <= 0.70:
        return "MOMENTUM WATCH", "Constructive momentum; breakout and retest unverified"
    if -5 <= h1 <= 3 and 0 <= h24 <= 25 and 0.48 <= share <= 0.65:
        return "PULLBACK WATCH", "Potential consolidation; support and reversal unverified"
    return "WAIT", "No qualifying preliminary momentum or pullback pattern"


def setup_assessment(item):
    """Market-only setup classification, never an authorization to trade."""
    score = item.get("score", 0)
    liq = item.get("liquidity", 0)
    vol = item.get("volume", 0)
    share = item.get("buy_share", 0)
    flags = item.get("flags", [])
    if item.get("risk_category") == "AVOID / HIGH CONCERN":
        return "REJECT", "Critical provider risk flag"
    missing = missing_market_fields(item)
    if missing:
        return "WAIT", "Missing or invalid market observations: " + ", ".join(missing)
    if item.get("change_h1") is None or item.get("change_h24") is None:
        return "WAIT", "Missing price-change observations"
    if ((item.get("change_h1") is not None and item["change_h1"] > 35)
            or (item.get("change_h24") is not None and item["change_h24"] > 120)):
        return "WAIT", "Extreme short-term price acceleration; avoid chasing"
    if any("wash trading" in f or "manipulation" in f for f in flags):
        return "WAIT", "Abnormal flow needs investigation"
    if (score >= 75 and liq >= 250_000 and vol >= 300_000
            and 0.45 <= share <= 0.70 and price_evidence(item)[0]):
        return "PRIORITY VERIFY", "Strong observed activity; execution and security checks still required"
    if score >= 60 and liq >= 100_000 and price_evidence(item)[0]:
        return "WATCH SETUP", "Activity merits tracking; not a verified buy"
    return "WAIT", "Market setup not strong enough"


def token_alert_key(item):
    """Chain-bound token deduplication also covers alternate pools."""
    network, token = item.get('network'), item.get('token_address')
    if not network or not token:
        return None
    return 'token:' + network + ':' + (token if network == 'solana' else token.lower())


def already_alerted(item, seen):
    return item['key'] in seen or token_alert_key(item) in seen


def telegram_eligible(item):
    """Fail closed: DEX research leads are silent unless independently trade-ready.

    This predicate does not change discovery, classification or audit evidence.
    Gate Spot paper candidates have a separate reviewed notification path.
    """
    try:
        import evidence_audit
        decision, _ = decision_summary(item)
        return (decision == "BUY CANDIDATE — REVIEW ENTRY"
                and evidence_audit.audit(item).get("trade_ready") is True
                and validate_execution_evidence(item) is True)
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        return False



def research_telegram_eligible(item):
    """Opt-in research notification, never BUY authorization."""
    if os.environ.get("ORACLE_RESEARCH_ALERTS", "").strip().lower() not in ("1", "true", "yes"):
        return False
    try:
        decision, _ = decision_summary(item)
        if decision != "WAIT AND VERIFY" or item.get("risk_category") == "AVOID / HIGH CONCERN":
            return False
        if item.get("discovery_eligible") is False or item.get("refresh_failed"):
            return False
        if item.get("token_identity_status") != "VERIFIED":
            return False
        if not all(item.get(k) for k in ("network", "token_address", "address")):
            return False
        if missing_market_fields(item) or item.get("liquidity", 0) <= 0 or item.get("volume", 0) <= 0:
            return False
        if hourly_evidence.adverse(item):
            return False
        if any(((item.get("evidence_review") or {}).get(key) or {}).get("status") == "HIGH CONCERN"
               for key in ("security", "provider_security")):
            return False
        return True
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        return False


def send_telegram(item):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    flags = "; ".join(item["flags"]) if item["flags"] else "No additional activity flags triggered"
    decision, summary = decision_summary(item)
    setup, setup_reason = setup_assessment(item)
    message = (
        "🔎 CRYPTO-ORACLE Z — UNVERIFIED RESEARCH LEAD\n"
        f"FINAL DECISION: {decision}\n"
        f"Token: {item.get('token_symbol', 'UNKNOWN')} | Network: {item['network']}\n"
        f"Contract: {item.get('token_address', 'UNKNOWN')}\n"
        f"{investment_gates.telegram_summary(item)}\n"
        f"Network: {item['network']}\n"
        f"Pool: {item['name']}\n"
        f"Pool classification: {item['pool_class']}\n"
        f"TOKEN AGE: {item['token_age']}\n"
        f"Base token: {item['token_symbol']}\n"
        f"Base-token contract: {item['token_address']}\n"
        f"Identity evidence: {item['token_identity_status']}\n"
        f"Older trading pools: {item['previous_pools']}\n"
        f"Discovery activity score: {item['score']}/100 (NOT safety or success probability)\n"
        f"Pool age: {item['age_hours']:.1f} hours\n"
        f"Liquidity: ${display_measurement(item.get('liquidity'), ',.0f')}\n"
        f"24h volume: ${display_measurement(item.get('volume'), ',.0f')}\n"
        f"1h trades: {display_measurement(item.get('trades'), '.0f')} ({display_measurement(item.get('buys'), '.0f')} buys / {display_measurement(item.get('sells'), '.0f')} sells)\n"
        f"1h buy share: {display_measurement(item.get('buy_share'), '.0%')}\n"
        f"Price change: 1h {item.get('change_h1')}% / 24h {item.get('change_h24')}% (provider-reported; None means unavailable)\n"
        f"Activity flags: {flags}\n"
        f"Security: {item['contract_security']}; holders: {item['holder_concentration']}; "
        f"liquidity lock: {item['liquidity_lock']}\n"
        f"Provider security findings: {item['security_details']}\n"
        f"RISK TRIAGE: {item['risk_category']}\n"
        f"Independent market corroboration: {item.get('market_corroboration', {}).get('status', 'UNKNOWN')} — {item.get('market_corroboration', {}).get('reason', 'Not checked')}\n"
        f"Risk evidence: {'; '.join(item['risk_reasons'])}\n"
        f"Exact provider fields: {item['security_fields']}\n"
        f"Holder evidence: {item['holder_details']}\n"
        f"Security data source: {item['security_source']}\n"
        f"Research strategy: {strategy(item)}\n"
        f"{horizon_notes()}\n"
        f"Success / 10x / 100x probabilities: {item['return_probabilities']}\n"
        f"Source: {item['source']}\n"
        f"Retrieved UTC: {item['observed_at']}\n"
        f"Pool link: {item['url']}\n\n"
        "AUTOMATED SCREEN ONLY. Provider data are not an audit; "
        "no price forecast or guaranteed return is provided.\n\n"
        f"MARKET SETUP: {setup} — {setup_reason}\n"
        f"ENTRY PATTERN: {entry_setup(item)[0]} — {entry_setup(item)[1]}\n"
        f"SETUP CHANGE: {item.get('setup_transition', 'INITIAL DISCOVERY')}\n"
        f"{evidence_audit.summary(evidence_audit.audit(item))}\n"
        f"FINAL DECISION: {decision}\n"
        f"WHY: {summary}"
        f"{investment_plan(item, decision)}"
    )
    if len(message) > 4096:
        message = message[:3900] + "\n[Additional diagnostics truncated; see workflow logs.]"
    return send_message(message)


def main():
    seen = load_state()
    watchlist = load_watchlist()
    history = signal_tracker.load()
    candidates = []
    keys_in_run = set()
    warnings = []
    errors = []
    total_checked = 0
    successful_feeds = 0
    for network in NETWORKS:
        network_checked = 0
        for mode in SCAN_MODES:
            for page in range(1, PAGES_PER_NETWORK + 1):
                try:
                    url = f"{API}/networks/{network}/{mode}?page={page}"
                    payload = fetch_json(url)
                    pools = payload.get("data")
                    if not isinstance(pools, list):
                        raise ValueError("Discovery response data must be an array")
                    successful_feeds += 1
                    network_checked += len(pools)
                    total_checked += len(pools)
                    for pool in pools:
                        item = inspect(pool, network, mode)
                        if item and item["key"] not in keys_in_run:
                            candidates.append(item)
                            keys_in_run.add(item["key"])
                    if not pools:
                        break
                except (urllib.error.URLError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, OSError) as exc:
                    detail = f"{network} {mode} page {page}: {type(exc).__name__}"
                    if (isinstance(exc, urllib.error.HTTPError) and exc.code == 429
                            and total_checked > 0):
                        warnings.append(f"Incomplete scan after rate limiting: {detail}")
                    else:
                        errors.append(detail)
                    break
                finally:
                    time.sleep(REQUEST_DELAY_SECONDS)
        print(f"{network}: checked {network_checked} pool observations", flush=True)

    # Rank independently: older, high-liquidity pools cannot crowd out new pools.
    # These are POOL classifications, not independently verified token ages.
    new_candidates = sorted(
        (item for item in candidates if item["pool_class"] == "NEW POOL"),
        key=lambda item: (item["score"], item["liquidity"]), reverse=True,
    )
    existing_candidates = sorted(
        (item for item in candidates if item["pool_class"] == "EXISTING POOL"),
        key=lambda item: (item["score"], item["liquidity"]), reverse=True,
    )
    new_unseen = [item for item in new_candidates if item["key"] not in seen]
    existing_unseen = [item for item in existing_candidates if item["key"] not in seen]
    # Verification capacity is separate from the Telegram delivery limit.
    # Prefer new pools, and use spare research slots when that feed is empty.
    evidence_slots = 6
    new_reserved = (evidence_slots * 7 + 9) // 10
    new_unseen = hourly_evidence.rotate(new_unseen, watchlist)
    existing_unseen = hourly_evidence.rotate(existing_unseen, watchlist)
    selected_new = new_unseen[:new_reserved]
    selected_existing = existing_unseen[:evidence_slots - len(selected_new)]
    remaining = evidence_slots - len(selected_new) - len(selected_existing)
    selected_new.extend(new_unseen[len(selected_new):len(selected_new) + remaining])
    selected = selected_new + selected_existing
    # Fetch tracked pools directly, including those absent from discovery feeds.
    # Bound requests to avoid exceeding the public API rate limit.
    revisits = []
    # Rotate tracked pools by oldest observation, instead of always refreshing the same eight.
    ordered_watchlist = sorted(watchlist.items(), key=lambda pair: pair[1].get("observed_at", ""))
    revisit_limit = max(1, min(12, int(os.environ.get("ORACLE_REVISITS", "3"))))
    for key, record in ordered_watchlist[:revisit_limit]:
        network = record.get("network")
        address = record.get("pool_address")
        if not network or not address or key in {x["key"] for x in selected}:
            continue
        try:
            url = (f"{API}/networks/{urllib.parse.quote(network, safe='')}/pools/"
                   f"{urllib.parse.quote(address, safe='')}")
            payload = fetch_json(url)
            pool = payload.get("data")
            if not isinstance(pool, dict):
                continue
            item = inspect(pool, network, "tracked")
            if item:
                revisits.append(item)
        except (urllib.error.URLError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, OSError) as exc:
            warnings.append(f"Watchlist refresh failed for {key}: {type(exc).__name__}")
        finally:
            time.sleep(REQUEST_DELAY_SECONDS)
    selected.extend(revisits)
    selected = hourly_evidence.rotate(selected, watchlist)[:evidence_slots]
    print(
        f"Qualified candidates: NEW POOL={len(new_candidates)}, "
        f"EXISTING POOL={len(existing_candidates)}; "
        f"unreported: new={len(new_unseen)}, existing={len(existing_unseen)}; "
        f"selected: new={len(selected_new)}, existing={len(selected_existing)}",
        flush=True,
    )
    delivered = 0
    delivered_new = 0
    delivered_existing = 0
    risk_counts = {}
    setup_counts = {}
    evidence_reports = []
    entry_counts = {}
    hourly_collector = hourly_evidence.HourlyEvidence()
    for item in selected:
        enrich(item)
        item["fundamental_evidence"] = fundamental_evidence.collect(item, lambda url: get_json(url, headers=HEADERS, retries=0, timeout=5))
        item["research_records"], item["research_record_status"] = research_records.load_for(item)
        item["research_records"] = research_records.combine(item, item["research_records"])
        item["evidence_review"] = evidence_checks.review(item)
        item["market_corroboration"] = market_corroboration.check(item, fetch_json)
        hourly_evidence.collect_safely(hourly_collector, item)
        if hourly_evidence.adverse(item):
            item["risk_category"] = "AVOID / HIGH CONCERN"
            item["risk_reasons"].append("Adverse independent evidence; inspect detailed findings")
        coverage = evidence_coverage.summary(item)
        canonical = canonical_outcomes.assess(item)
        item["canonical_outcome"] = canonical["outcome"]
        print("Evidence coverage " + item["key"] + ": " +
              json.dumps({name: row["status"] for name, row in coverage.items()}, sort_keys=True), flush=True)
        evidence_reports.append({"network": item["network"], "pool": item["address"],
                                 "contract": item.get("token_address"),
                                 "security": item.get("security_provider_evidence"),
                                 "source_records": item["research_records"],
                                 "market_corroboration": item["market_corroboration"],
                                 "activity": {"provider": item.get("source"), "network": item["network"],
                                              "contract": item.get("token_address"), "pool": item["address"],
                                              "observed_at": item.get("observed_at"),
                                              "status": "PROVIDER OBSERVATION — NOT SAFETY",
                                              "values": {key: item.get(key) for key in (
                                                  "liquidity", "volume", "buy_share", "score", "age_hours",
                                                  "change_h1", "change_h24", "base_token_price_usd")}},
                                 "source_review": item["evidence_review"],
                                 "verification": item.get("verification"),
                                 "hourly_evidence": item.get("hourly_evidence"),
                                 "verification_coverage": coverage,
                                 "gate_spot": item.get("gate_spot"),
                                 "gate_provider_evidence": item.get("gate_provider_evidence"),
                                 "gate_execution_research": item.get("gate_execution_research"),
                                 "canonical_assessment": canonical,
                                 "assessment": investment_gates.assess(item)})
        risk_counts[item["risk_category"]] = risk_counts.get(item["risk_category"], 0) + 1
        setup = setup_assessment(item)[0]
        setup_counts[setup] = setup_counts.get(setup, 0) + 1
        entry = entry_setup(item)[0]
        entry_counts[entry] = entry_counts.get(entry, 0) + 1
        item["entry_pattern"] = entry
        item["market_setup"] = setup
        if price_evidence(item)[0]:
            signal_tracker.record(history, item)
        previous_watch = watchlist.get(item["key"])
        transition = watchlist_transition(item, watchlist)
        if already_alerted(item, seen):
            # Already delivered: never repeat the same token just because a
            # market setup transition occurred on a later hourly scan.
            save_watchlist(watchlist)
            continue
        item["setup_transition"] = transition or "INITIAL DISCOVERY"
        buy_eligible = telegram_eligible(item)
        research_eligible = not buy_eligible and research_telegram_eligible(item)
        if delivered >= MAX_ALERTS_PER_RUN or not (buy_eligible or research_eligible):
            # Keep discarded or insufficiently evidenced tokens silent.
            save_watchlist(watchlist)
            continue
        try:
            send_telegram(item)
        except (urllib.error.URLError, ValueError, RuntimeError, TimeoutError, OSError) as exc:
            errors.append(f"Telegram delivery failed for {item['key']}: {type(exc).__name__}")
            # Retry a failed priority-transition alert on the next scan.
            if previous_watch is None:
                watchlist.pop(item["key"], None)
            else:
                watchlist[item["key"]] = previous_watch
            continue
        seen.add(item["key"])
        if token_alert_key(item):
            seen.add(token_alert_key(item))
        save_state(seen)
        save_watchlist(watchlist)
        delivered += 1
        if item["pool_class"] == "NEW POOL":
            delivered_new += 1
        else:
            delivered_existing += 1
        time.sleep(1)
    # Gate-only strategy has its own evidence, report, paper history and label.
    # Optional failure never changes the DEX decision or interrupts its delivery.
    gate_report = {}
    try:
        gate_report = gate_spot_candidates.hourly(send_message)
        warnings.extend("Gate paper strategy: " + error for error in gate_report.get("errors", []))
        warnings.extend("Gate paper notification failed" for event in gate_report.get("delivery_events", [])
                        if event.get("status") == "DELIVERY_FAILED")
    except Exception as exc:
        warnings.append("Gate paper stage unavailable: " + type(exc).__name__)
    save_watchlist(watchlist)
    signal_tracker.save(history)
    ledger_status = forward_ledger.capture(history, selected)
    print(f"Tracked pool histories: {len(history)}", flush=True)
    for hours in signal_tracker.HORIZONS_HOURS:
        values = [result["change_percent"]
                  for observations in history.values()
                  for result in signal_tracker.outcomes(observations)
                  if result["horizon_hours"] == hours and result["status"] == "OBSERVED"]
        if values:
            values.sort()
            median = (values[(len(values)-1)//2] + values[len(values)//2]) / 2
            print(f"Paper {hours}h: n={len(values)}, median={median:+.2f}%, positive={sum(v > 0 for v in values)}/{len(values)}; indicative prices, selection bias", flush=True)
        else:
            print(f"Paper {hours}h: no measured outcomes yet", flush=True)
    print(f"Risk triage among selected: {risk_counts}", flush=True)
    print(f"Market setups among selected: {setup_counts}", flush=True)
    print(f"Entry patterns among selected: {entry_counts}", flush=True)
    print(f"Alerts delivered by category: NEW POOL={delivered_new}, "
          f"EXISTING POOL={delivered_existing}", flush=True)

    print(f"Total pool observations checked: {total_checked}", flush=True)
    print(f"Candidates found: {len(candidates)}; alerts delivered: {delivered}", flush=True)
    for warning in warnings:
        print(f"WARNING: {warning}", flush=True)
    for error in errors:
        print(f"ERROR: {error}", flush=True)
    if not successful_feeds:
        errors.append("No discovery feeds completed successfully")
    pathlib.Path("evidence_report.json").write_text(json.dumps(evidence_reports, indent=2) + "\n", encoding="utf-8")
    report = {"status": "failed" if errors else "completed",
              "observations": total_checked, "candidates": len(candidates),
              "alerts_delivered": delivered, "successful_feeds": successful_feeds,
              "hourly_evidence": hourly_collector.summary(),
              "gate_paper_candidates": sum(c.get("classification") == gate_spot_candidates.LABEL for c in gate_report.get("candidates", [])),
              "forward_ledger": ledger_status,
              "signal_performance": {key: {"horizons": signal_tracker.outcomes(rows),
                                           "sampled_risk": signal_tracker.sampled_risk(rows)}
                                     for key, rows in history.items()},
              "classification_counts": {outcome: sum(row["canonical_assessment"]["outcome"] == outcome for row in evidence_reports)
                                        for outcome in canonical_outcomes.OUTCOMES},
              "signal_tracking_limits": {"maximum_signals": signal_tracker.MAX_TOKENS,
                                         "maximum_samples_per_signal": signal_tracker.MAX_OBSERVATIONS,
                                         "at_signal_capacity": len(history) >= signal_tracker.MAX_TOKENS,
                                         "signals_at_sample_capacity": [key for key, rows in history.items()
                                              if len(rows) >= signal_tracker.MAX_OBSERVATIONS]},
              "warnings": warnings, "errors": errors,
              "completed_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    pathlib.Path("scan_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(1)
    return report


def cli():
    """Unexpected errors fail the workflow with credential-safe diagnostics.

    The hourly workflow's failure step sends the Telegram error notification.
    Never leave an earlier successful summary behind after an unexpected crash.
    """
    try:
        main()
    except Exception as exc:
        error = "Unexpected scanner failure: " + type(exc).__name__
        print("::error::" + error + "; see workflow failure notification", flush=True)
        # Frame names and line numbers only: no exception values, arguments,
        # locals, remote bodies, URLs or credentials enter diagnostic output.
        locations=[pathlib.Path(frame.filename).name+':'+str(frame.lineno)+' in '+frame.name
                   for frame in traceback.extract_tb(exc.__traceback__)[-5:]]
        print('Safe failure locations: '+'; '.join(locations), flush=True)
        try:
            pathlib.Path("scan_summary.json").write_text(json.dumps(dict(
                status="failed", errors=[error], error_locations=locations,
                completed_at=dt.datetime.now(dt.timezone.utc).isoformat())) + "\n", encoding="utf-8")
        except OSError:
            print("::error::Could not write failed scan summary", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

