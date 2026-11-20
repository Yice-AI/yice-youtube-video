"""即时造画面入口的预算、账本和 Modal 闸门测试。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kit.scripts import produce_asset


class ProduceAssetTests(unittest.TestCase):
    def test_ledger_replaces_same_id_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            produce_asset.append_ledger(project, {"id": "a", "cost_usd": 0.1})
            produce_asset.append_ledger(project, {"id": "a", "cost_usd": 0.2})
            rows = produce_asset.read_ledger(project)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cost_usd"], 0.2)
            self.assertFalse((project / "asset-ledger.jsonl.tmp").exists())

    def test_image_budget_and_stock_budget_are_hard_limits(self):
        with self.assertRaisesRegex(RuntimeError, "image2"):
            produce_asset.budget_state([{"sourceType": "image2", "cost_usd": 5.01}], 5, 60)
        with self.assertRaisesRegex(RuntimeError, "图库"):
            produce_asset.budget_state([{"sourceType": "stock-footage", "api_calls": 60}], 5, 60)

    def test_modal_requires_zero_spend_limit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "spend_limit_usd"):
                produce_asset.modal_guard()
        with patch.dict(os.environ, {"YICE_MODAL_SPEND_LIMIT_USD": "1"}):
            with self.assertRaisesRegex(RuntimeError, "spend_limit_usd"):
                produce_asset.modal_guard()
        with patch.dict(os.environ, {"YICE_MODAL_SPEND_LIMIT_USD": "0"}):
            self.assertIsNone(produce_asset.modal_guard())

    def test_rec_task_writes_ledger_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = produce_asset.main(["--kind", "rec-task", "--project", str(project),
                                         "--output", str(project / "assets/rec-task/task.json"),
                                         "--id", "task", "--input", str(project), "--prompt", "录首页"])
            self.assertEqual(result, 0)
            row = json.loads((project / "asset-ledger.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["sourceType"], "recording")
            self.assertFalse(Path(row["path"]).is_absolute())
            self.assertTrue((project / row["path"]).resolve().is_relative_to(project.resolve()))
            self.assertTrue((project / row["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
