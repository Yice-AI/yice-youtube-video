import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("rec_bridge_test", SCRIPTS / "rec-bridge.py")
assert SPEC is not None and SPEC.loader is not None
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
REC = bridge.shot_module()
DEMO = bridge.demo_module()

# This substitute never accesses the screen, clipboard, mouse or macOS APIs.
FAKE_RUNNER = r'''
import json, os, signal, subprocess, sys, time
from pathlib import Path
home = Path(__file__).parent
shot = json.loads(Path(sys.argv[1]).read_text())
with (home / "requests.jsonl").open("a") as stream:
    stream.write(json.dumps({"argv": sys.argv[1:], "title": shot["target"]["title_contains"]}) + "\n")
print("substitute rec-shot started", flush=True)
if "TIMEOUT" in shot["target"]["title_contains"]:
    log = home / "lifecycle.log"
    def event(value):
        with log.open("a") as stream:
            stream.write(value + "\n")
    child = subprocess.Popen([sys.executable, "-c", """
import os, signal, sys, time
from pathlib import Path
root = Path(sys.argv[1])
def event(value):
    with (root / 'lifecycle.log').open('a') as stream:
        stream.write(value + '\\n')
def stop(*_):
    event('stop-recorder')
    raise SystemExit(0)
signal.signal(signal.SIGINT, stop)
event('start-recorder')
(root / 'child-ready').write_text(str(os.getpid()))
while True:
    time.sleep(1)
""", str(home)])
    (home / "pids.json").write_text(json.dumps([os.getpid(), child.pid]))
    event("start-parent")
    def stop(*_):
        child.send_signal(signal.SIGINT)
        child.wait(timeout=3)
        event("stop-parent")
        raise SystemExit(130)
    signal.signal(signal.SIGTERM, stop)
    while True:
        time.sleep(1)
if "--dry-run" not in sys.argv:
    for step in shot["steps"]:
        if step["type"] == "rec_start":
            output = Path(step["out"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"SUBSTITUTE ONLY: not a real video")
            folder = Path(str(output) + ".rec")
            folder.mkdir()
            (folder / "events.json").write_text(json.dumps({"state": "complete", "simulated": True}))
print("substitute rec-shot finished", flush=True)
'''


def shot(output=None, title="test"):
    steps = [{"type": "wait", "sec": 0}]
    if output is not None:
        steps = [{"type": "rec_start", "region": [0, 0, 100, 100], "out": str(output)},
                 {"type": "rec_stop"}]
    return {"version": 1, "target": {"process": "FakeApp", "title_contains": [title],
            "region": [0, 0, 100, 100], "input": {"region": [10, 60, 80, 20], "initial_text": ""}},
            "steps": steps}


class RecBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.fake = self.root / "fake"
        self.fake.mkdir()
        (self.fake / "rec-shot.py").write_text(FAKE_RUNNER)
        (self.fake / "rec-shot.sh").write_text(
            '#!/bin/bash\nset -eu\nexec python3 "$(dirname "$0")/rec-shot.py" "$@"\n')
        (self.fake / "rec-demo.py").write_text(
            'import json,sys\nfrom pathlib import Path\n'
            'params=json.loads(Path(sys.argv[1]).read_text())\n'
            '(Path(__file__).parent/"demo-request.json").write_text(json.dumps(params))\n'
            'print("synthetic rec-demo; no UI")\n')
        (self.fake / "rec-demo.sh").write_text(
            '#!/bin/bash\nset -eu\nexec python3 "$(dirname "$0")/rec-demo.py" "$@"\n')
        self.service = bridge.Bridge(self.root / "bridge", [self.evidence], timeout=0.8, grace=4)
        self.service.acquire()
        self.patch_scripts = mock.patch.object(bridge, "SCRIPTS", self.fake)
        self.patch_module = mock.patch.object(bridge, "shot_module", return_value=REC)
        self.patch_demo = mock.patch.object(bridge, "demo_module", return_value=DEMO)
        self.patch_scripts.start()
        self.patch_module.start()
        self.patch_demo.start()

    def tearDown(self):
        self.patch_demo.stop()
        self.patch_module.stop()
        self.patch_scripts.stop()
        self.service.close()
        destination = os.environ.get("REC_BRIDGE_TEST_EVIDENCE")
        if destination:
            archive = Path(destination) / self._testMethodName
            archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copytree(self.root, archive, symlinks=True)
        self.temporary.cleanup()

    def request(self, name, value):
        path = self.service.queue / (name + ".json")
        bridge.write_json(path, value)
        self.service.process(path)
        return json.loads((self.service.done / path.name).read_text())

    def plan(self, value, name="shot.json"):
        path = self.evidence / name
        bridge.write_json(path, value)
        return str(path)

    def count(self):
        path = self.fake / "requests.jsonl"
        return len(path.read_text().splitlines()) if path.exists() else 0

    def demo_params(self):
        return {"version": 1, "project": "示例", "output_dir": str(self.evidence / "demo"),
                "input": {"empty_text": "给示例发消息"},
                "messages": [{"text": "示例消息", "completion_text": "用时", "timeout": 5}]}

    def test_demo_accepts_only_a_parameter_path_and_freezes_it(self):
        params = self.demo_params()
        source = self.plan(params, "demo-params.json")
        result = self.request("demo", {"action": "rec-demo", "params": source})
        self.assertEqual(result["exit_code"], 0, result)
        params['output_dir'] = str(Path(params['output_dir']).resolve())
        observed = json.loads((self.fake / "demo-request.json").read_text())
        self.assertEqual(observed, params)
        Path(source).write_text('{}')
        snapshot = self.service.private / 'demo/params.json'
        self.assertEqual(json.loads(snapshot.read_text()), params)
        self.assertEqual(self.count(), 0)
        self.assertIn('synthetic rec-demo; no UI', result['stdout'])

    def test_demo_rejects_extra_arguments_source_and_output_escape(self):
        params = self.demo_params()
        source = self.plan(params, "demo-params.json")
        for index, request in enumerate([
                {"action": "rec-demo", "params": source, "dry_run": True},
                {"action": "rec-demo", "params": source, "command": "forbidden"},
                {"action": "rec-demo", "params": str(self.root / 'outside.json')},
                {"action": "rec-demo", "params": "relative.json"}]):
            self.assertEqual(self.request(f'demo-bad-{index}', request)['exit_code'], 2)
        outside = self.root / 'outside'
        outside.mkdir()
        (self.evidence / 'escape').symlink_to(outside, target_is_directory=True)
        params['output_dir'] = str(self.evidence / 'escape/video')
        self.assertEqual(self.request('demo-escape', {'action': 'rec-demo', 'params': self.plan(params)})['exit_code'], 2)
        self.assertFalse((self.fake / 'demo-request.json').exists())

    def test_demo_rejects_nested_recording_and_malformed_input_without_killing_queue(self):
        for index, key in enumerate(['input', 'ui']):
            params = self.demo_params()
            params[key] = []
            self.assertEqual(self.request(f'demo-malformed-{index}', {
                'action': 'rec-demo', 'params': self.plan(params)})['exit_code'], 2)
        params = self.demo_params()
        params['after'] = [{'name': 'bad', 'target': shot()['target'],
                            'steps': [{'type': 'rec_start', 'region': [0, 0, 100, 100], 'out': str(self.root / 'outside.mov')}]}]
        self.assertEqual(self.request('demo-nested', {'action': 'rec-demo', 'params': self.plan(params)})['exit_code'], 2)
        self.assertEqual(self.request('still-alive', {'action': 'ping'})['exit_code'], 0)
        self.assertFalse((self.fake / 'demo-request.json').exists())

    def test_ping_order_and_private_permissions(self):
        for name in ["003", "001", "002"]:
            bridge.write_json(self.service.queue / (name + ".json"), {"action": "ping"})
        with mock.patch.object(self.service, "process", wraps=self.service.process) as process:
            self.assertEqual(self.service.drain(), 3)
        self.assertEqual([c.args[0].name for c in process.call_args_list], ["001.json", "002.json", "003.json"])
        for path in [self.service.root, self.service.queue, self.service.done, self.service.private]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        for path in self.service.done.glob("*.json"):
            result = json.loads(path.read_text())
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(json.loads(result["stdout"])["status"], "ok")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(self.count(), 0)

    def test_unknown_actions_fields_and_malformed_json_are_rejected(self):
        for i, value in enumerate([{"action": "shell", "command": "touch forbidden"},
                                   {"action": "ping", "shell": "echo forbidden"},
                                   {"action": []}, {"action": None}]):
            with self.subTest(value=value):
                self.assertEqual(self.request(f"bad-{i}", value)["exit_code"], 2)
        path = self.service.queue / "malformed.json"
        path.write_text("{not json")
        self.service.drain()
        self.assertEqual(json.loads((self.service.done / path.name).read_text())["exit_code"], 2)
        self.assertEqual(self.request("after-bad", {"action": "ping"})["exit_code"], 0)
        self.assertEqual(self.count(), 0)

    def test_paths_outside_evidence_and_symlink_escapes_are_rejected(self):
        outside = self.root / "outside.json"
        bridge.write_json(outside, shot())
        link = self.evidence / "escape.json"
        link.symlink_to(outside)
        for i, path in enumerate([str(outside), str(link), "relative.json", str(self.evidence / "../outside.json")]):
            with self.subTest(path=path):
                result = self.request(f"escape-{i}", {"action": "rec-shot", "shot": path})
                self.assertEqual(result["exit_code"], 2)
        self.assertEqual(self.count(), 0)

    def test_output_path_outside_allowed_roots_is_rejected(self):
        result = self.request("bad-output", {"action": "rec-shot", "shot": self.plan(shot(self.root / "outside.mov"))})
        self.assertEqual(result["exit_code"], 2)
        self.assertFalse((self.root / "outside.mov").exists())
        self.assertEqual(self.count(), 0)

    def test_substitute_runs_and_dry_run_creates_no_take(self):
        output = self.evidence / "take.mov"
        source = self.plan(shot(output), "shot ; shell-is-not-used.json")
        dry = self.request("dry", {"action": "rec-shot", "shot": source, "dry_run": True})
        self.assertEqual(dry["exit_code"], 0)
        self.assertFalse(output.exists())
        result = self.request("record", {"action": "rec-shot", "shot": source})
        self.assertEqual(result["exit_code"], 0)
        self.assertIn(str(output.resolve()), result["artifacts"])
        self.assertEqual(self.count(), 2)
        self.assertEqual(json.loads(Path(str(output) + ".rec/events.json").read_text())["state"], "complete")
        self.assertIn("not a real video", output.read_text())
        for name in ["shot.json", "stdout.log", "stderr.log"]:
            self.assertEqual(stat.S_IMODE((self.service.private / "record" / name).stat().st_mode), 0o600)

    def test_guard_validation_cannot_be_disabled(self):
        value = shot()
        value["steps"] = [{"type": "paste", "text": "must not run", "guard": False}]
        result = self.request("unguarded", {"action": "rec-shot", "shot": self.plan(value)})
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(self.count(), 0)

    def test_timeout_stops_substitute_recorder_and_parent(self):
        result = self.request("timeout", {"action": "rec-shot", "shot": self.plan(shot(title="TIMEOUT"))})
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["timed_out"])
        events = (self.fake / "lifecycle.log").read_text().splitlines()
        self.assertCountEqual(events, ["start-parent", "start-recorder", "stop-recorder", "stop-parent"])
        pids = json.loads((self.fake / "pids.json").read_text())
        for pid in pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        bridge.write_json(self.evidence / "timeout-verification.json", {
            "simulated": True, "exit_code": result["exit_code"], "events": events,
            "checked_pids": pids, "alive_after_timeout": 0, "substitute_requests": self.count()})
        self.assertEqual(self.count(), 1)

    def test_single_instance_and_interrupted_request_is_not_replayed(self):
        other = bridge.Bridge(self.service.root, [self.evidence])
        with self.assertRaisesRegex(ValueError, "已有"):
            other.acquire()
        bridge.write_json(self.service.claimed / "interrupted.json", {"action": "rec-shot"})
        self.service.close()
        self.service.acquire()
        result = json.loads((self.service.done / "interrupted.json").read_text())
        self.assertEqual(result["exit_code"], 125)
        self.assertEqual(result["state"], "interrupted")
        self.assertEqual(self.count(), 0)

    def test_duplicate_request_is_not_replayed(self):
        value = {"action": "rec-shot", "shot": self.plan(shot())}
        self.assertEqual(self.request("same", value)["exit_code"], 0)
        self.assertEqual(self.request("same", value)["exit_code"], 0)
        self.assertEqual(self.count(), 1)
        self.assertEqual(len(list(self.service.claimed.glob("*.duplicate-*"))), 1)

    def test_probe_validates_region_without_capturing(self):
        result = self.request("bad-region", {"action": "probe", "region": [0, 0, 0, 10]})
        self.assertEqual(result["exit_code"], 2)
        folder = self.service.private / "probe-plan"
        command, artifacts = self.service.prepare({"action": "probe", "region": [1, 2, 30, 40]}, folder)
        self.assertEqual(command[-1], "1,2,30,40")
        self.assertEqual(artifacts, [folder / "probe.png", folder / "probe.json"])
        self.assertFalse(folder.exists())
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
