"""Read-only multichain rollout policy. Discovery support is not verification approval.

This module does not enable unsupported chains in asset_identity or any BUY gate.
Adapters must prove identity and chain-specific safety before activation.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ChainPlan:
    network: str
    priority: int
    stage: str
    required_checks: tuple

COMMON = ("canonical_token_identity", "pool_identity", "liquidity_and_sellability",
          "holder_concentration", "circulating_supply_and_unlocks",
          "execution_depth", "evidence_freshness")
EVM = ("verified_contract_bytecode", "owner_and_upgrade_permissions",
       "blacklist_mint_pause_tax_honeypot")
SOLANA = ("mint_account_owner_and_program", "mint_and_freeze_authorities",
          "token_2022_extensions", "transfer_restrictions",
          "pool_and_token_account_validation")

PLANS = (
    ChainPlan("solana", 1, "existing_partial", COMMON + SOLANA),
    ChainPlan("eth", 2, "existing", COMMON + EVM),
    ChainPlan("base", 3, "existing", COMMON + EVM),
    ChainPlan("bsc", 4, "existing", COMMON + EVM),
    ChainPlan("arbitrum", 5, "planned", COMMON + EVM),
    ChainPlan("sui", 6, "planned", COMMON + ("move_package_and_upgrade_authority", "coin_metadata_and_treasury_cap")),
    ChainPlan("avalanche", 7, "planned", COMMON + EVM),
    ChainPlan("ton", 8, "planned", COMMON + ("jetton_master_wallet_validation", "admin_and_mint_controls")),
)

def plan(network):
    return next((item for item in PLANS if item.network == network), None)

def eligible_for_buy(network, observations):
    """Never grant authorization; report missing chain-specific prerequisites only.

    This is a prerequisite diagnostic, not a replacement for the production
    investment, security or execution gates.
    """
    item = plan(network)
    if item is None:
        return {"status": "UNSUPPORTED", "missing": ["supported_chain_adapter"], "buy_authorized": False}
    missing = [check for check in item.required_checks
               if not isinstance(observations.get(check), dict)
               or observations[check].get("status") != "VERIFIED"]
    if item.stage == "planned":
        missing.insert(0, "production_chain_adapter")
    return {"status": "PREREQUISITES_PRESENT" if not missing else "INCOMPLETE",
            "missing": missing, "buy_authorized": False}
