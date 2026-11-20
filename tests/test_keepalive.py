import json
import pathlib
import unittest
import urllib.error

import keepalive

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class LoopTests(unittest.TestCase):
    def run_loop(self, send, run_for=keepalive.RUN_FOR):
        clock, calls = FakeClock(), []

        def recording(repo, workflow, token, inputs=None):
            calls.append((workflow, inputs))
            return send(workflow)
        report = keepalive.loop("o/r", "t", clock=clock, sleep=clock.sleep, send=recording,
                                log=lambda *_: None, run_for=run_for)
        return report, calls, clock.now

    def test_dispatches_scanner_every_20_minutes_then_renews_once(self):
        report, calls, elapsed = self.run_loop(lambda wf: True)
        scanner = [c for c in calls if c[0] == "main.yml"]
        self.assertEqual(len(scanner), 17)  # 0, 20, ... 320 minutes within 340
        self.assertTrue(all(c[1] == {"trigger": "external"} for c in scanner))
        self.assertEqual(calls[-1], ("keepalive.yml", None))
        self.assertEqual([c[0] for c in calls].count("keepalive.yml"), 1)
        self.assertLess(elapsed, keepalive.RUN_FOR)
        self.assertTrue(report["renewed"])

    def test_scanner_failures_are_counted_and_loop_still_renews(self):
        report, calls, _ = self.run_loop(lambda wf: wf == "keepalive.yml")
        self.assertEqual(report["scanner_dispatches"], 0)
        self.assertEqual(report["scanner_failures"], 17)
        self.assertTrue(report["renewed"])

    def test_never_dispatches_scanner_without_external_trigger(self):
        _, calls, _ = self.run_loop(lambda wf: True, run_for=3 * keepalive.INTERVAL)
        for workflow, inputs in calls:
            if workflow == "main.yml":
                self.assertEqual(inputs, {"trigger": "external"})

    def test_renewal_happens_before_job_timeout(self):
        workflow = (ROOT / ".github/workflows/keepalive.yml").read_text()
        self.assertIn("timeout-minutes: 350", workflow)
        self.assertLess(keepalive.RUN_FOR, 350 * 60)


class DispatchTests(unittest.TestCase):
    def test_posts_dispatch_on_main_with_inputs(self):
        seen = {}

        class Response:
            status = 204
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def opener(request, timeout):
            seen["url"], seen["body"], seen["method"] = request.full_url, json.loads(request.data), request.method
            return Response()
        self.assertTrue(keepalive.dispatch("o/r", "main.yml", "tok", {"trigger": "external"}, opener=opener))
        self.assertEqual(seen["url"], "https://api.github.com/repos/o/r/actions/workflows/main.yml/dispatches")
        self.assertEqual(seen["body"], {"ref": "main", "inputs": {"trigger": "external"}})
        self.assertEqual(seen["method"], "POST")

    def test_http_errors_return_false_not_raise(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)
        self.assertFalse(keepalive.dispatch("o/r", "main.yml", "tok", opener=opener))


class WorkflowTests(unittest.TestCase):
    def test_workflow_has_minimal_permissions_and_single_loop(self):
        text = (ROOT / ".github/workflows/keepalive.yml").read_text()
        self.assertIn("actions: write", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("group: scanner-keepalive", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("secrets.", text)

    def test_scanner_still_accepts_external_trigger(self):
        text = (ROOT / ".github/workflows/main.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("trigger:", text)


if __name__ == "__main__":
    unittest.main()
