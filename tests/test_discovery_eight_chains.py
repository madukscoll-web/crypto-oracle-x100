"""Eight-chain discovery identity and read-only admission regression tests."""
import unittest
from asset_identity import CHAINS, key
from discovery_adapters import RESEARCH_ADAPTERS, gecko_rows
from multichain_live_research import run
from multichain_rollout_policy import eligible_for_buy
from test_global_discovery import pool_payload, TOKEN, POOL, SOL

class EightChainTests(unittest.TestCase):
    def test_chain_ids_and_equal_tickers_remain_distinct(self):
        expected = {"eth":1, "bsc":56, "base":8453, "arbitrum":42161,
                    "polygon_pos":137, "avax":43114, "optimism":10}
        for network, number in expected.items():
            self.assertEqual(CHAINS[network], f"eip155:{number}")
        self.assertEqual(len({key(n, TOKEN) for n in expected}), 7)

    def test_eight_chains_discovered_with_raw_evidence_and_no_buy(self):
        def fetch(url):
            network = url.split("/networks/")[1].split("/")[0]
            token = SOL if network == "solana" else TOKEN
            pool = SOL if network == "solana" else POOL
            return pool_payload(network, token, pool)
        report = run(limit=8, fetch=fetch)
        self.assertEqual(len(report["requested_networks"]), 8)
        self.assertEqual(set(report["observed_by_chain"]), set(report["requested_networks"]))
        self.assertEqual(len(report["selected"]), 8)
        self.assertEqual(len(report["provider_observations"]), 16)
        self.assertFalse(report["buy_authorized"])
        self.assertFalse(report["telegram_transmission"])
        for network in ("arbitrum", "polygon_pos", "avax", "optimism"):
            result = eligible_for_buy(network, {})
            self.assertIn("production_chain_adapter", result["missing"])
            self.assertFalse(result["buy_authorized"])

    def test_wrong_network_pool_rejected_on_every_evm_chain(self):
        for adapter in RESEARCH_ADAPTERS:
            if adapter.network == "solana": continue
            payload = pool_payload(adapter.network)
            payload["data"][0]["id"] = "solana_" + SOL
            rows, failures = gecko_rows(adapter.network, payload, "fixture", "test")
            self.assertEqual(rows, [])
            self.assertEqual(len(failures), 1)
