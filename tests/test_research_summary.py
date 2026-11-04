import unittest
from research_summary import summarize

def report(candidates=None):
    return dict(run_state="COMPLETED", qualified_discovery_count=26,
                verified_buy_signals=[], candidates=candidates if candidates is not None else [
                    dict(network="eth",token_address="0x"+"a"*40,
                         decision="WAIT AND VERIFY",mandatory_blockers=["No independent audit"])])

class ResearchSummaryTests(unittest.TestCase):
    def test_no_buy_and_blockers_visible(self):
        text=summarize(report())
        self.assertIn("VERIFIED BUY SIGNALS: 0",text)
        self.assertIn("WAIT AND VERIFY=1",text)
        self.assertNotIn("0x"+"a"*40,text)
    def test_discard_is_reported(self):
        item=report()["candidates"][0]
        item["decision"]="DISCARD"
        self.assertIn("DISCARD",summarize(report([item])))
    def test_refuse_unreviewed_buy_claim(self):
        for decision in ("BUY", "BUY CANDIDATE — REVIEW ENTRY", None):
            item=report()["candidates"][0]
            item["decision"]=decision
            with self.assertRaises(ValueError):summarize(report([item]))
    def test_refuse_incomplete_or_unproven_evidence(self):
        for changed in (dict(run_state="IN_PROGRESS"),dict(verified_buy_signals=[dict(token="X")])):
            value=report()
            value.update(changed)
            with self.assertRaises(ValueError):summarize(value)
        item=report()["candidates"][0]
        item["mandatory_blockers"]=[]
        with self.assertRaises(ValueError):summarize(report([item]))

