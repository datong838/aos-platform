from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check-interaction-honesty.py")
SPEC = importlib.util.spec_from_file_location("interaction_honesty", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class InteractionHonestyScannerTest(unittest.TestCase):
    def test_repository_manifest_has_exactly_35_unique_pages(self) -> None:
        root = SCRIPT.parents[2]
        entries = MODULE.load_manifest(root / "apps/web/src/interactionHonestyManifest.ts")
        self.assertEqual(35, len(entries))
        self.assertEqual(35, len({entry["route"] for entry in entries}))
        self.assertTrue(all(entry["tests"] for entry in entries))

    def test_apollo_manifest_matches_the_actual_app_entrypoint(self) -> None:
        root = SCRIPT.parents[2]
        entries = MODULE.load_manifest(root / "apps/web/src/interactionHonestyManifest.ts")
        apollo = next(entry for entry in entries if entry["route"] == "/apollo")
        self.assertEqual([], MODULE._check_explicit_app_binding(root, apollo))

    def test_detects_high_confidence_fake_interactions(self) -> None:
        source = """
const MOCK_ROWS = [{ id: 1 }];
const handleSave = () => {};
export function BadPage() {
  return <><a href="#">later</a><button>save</button>
    <button onClick={() => undefined}>noop</button></>;
}
"""
        findings = MODULE._scan_source("BadPage.tsx", source, "none")
        self.assertEqual({"IH001", "IH002", "IH003", "IH004", "IH005"}, {f.rule for f in findings})

    def test_detects_local_only_success_on_server_write_page(self) -> None:
        source = """
function save() {
  localStorage.setItem("draft", "1");
  setMessage("已保存成功");
}
export function Page() { return <button onClick={save}>save</button>; }
"""
        findings = MODULE._scan_source("Page.tsx", source, "server")
        self.assertIn("IH006", {f.rule for f in findings})

    def test_accepts_real_disabled_submit_and_api_write_controls(self) -> None:
        source = """
async function save() {
  await apiPost("/v1/items", {});
  setMessage("已保存");
}
export function Page() { return <form><button type="submit">save</button>
  <button disabled>later</button><button onClick={save}>write</button></form>; }
"""
        self.assertEqual([], MODULE._scan_source("Page.tsx", source, "server"))

    def test_allowlist_requires_reason_and_nonexpired_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "allowlist.json"
            path.write_text('[{"rule":"IH004","path":"Page.tsx"}]', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires rule, path, reason and expires"):
                MODULE.load_allowlist(path)


if __name__ == "__main__":
    unittest.main()
