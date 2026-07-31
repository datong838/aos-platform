from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import scan_sensitive


class SensitiveScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, relative_path: str, content: str) -> Path:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_private_key_marker_is_blocked_without_echoing_value(self) -> None:
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        target = self._write("fixtures/unsafe.txt", marker + "\nsynthetic-body")
        findings = scan_sensitive.scan_file(target, self.root, set())

        self.assertEqual(["PRIVATE_KEY"], [item.rule_id for item in findings])
        rendered = repr(findings)
        self.assertNotIn(marker, rendered)
        self.assertEqual(12, len(findings[0].fingerprint))

    def test_placeholder_secret_is_not_reported(self) -> None:
        target = self._write(
            "config.example",
            'client_secret="replace_me_with_your_secret"\n',
        )
        self.assertEqual([], scan_sensitive.scan_file(target, self.root, set()))

    def test_literal_secret_and_credential_url_are_blocked(self) -> None:
        target = self._write(
            "config.txt",
            "api_key=AbCdEfGhIjKlMnOpQrStUv\n"
            "postgresql://app:Sup3rSecretValue@db.internal:5432/app\n",
        )
        rule_ids = {
            item.rule_id
            for item in scan_sensitive.scan_file(target, self.root, set())
        }
        self.assertIn("GENERIC_SECRET", rule_ids)
        self.assertIn("CREDENTIAL_URL", rule_ids)

    def test_warning_only_succeeds_unless_fail_on_warning(self) -> None:
        target = self._write("contact.txt", "synthetic user: 13800138000\n")
        with contextlib.redirect_stdout(io.StringIO()):
            normal_code = scan_sensitive.main(
                ["--repo-root", str(self.root), str(target)]
            )
            strict_code = scan_sensitive.main(
                [
                    "--repo-root",
                    str(self.root),
                    "--fail-on-warning",
                    str(target),
                ]
            )
        self.assertEqual(0, normal_code)
        self.assertEqual(1, strict_code)

    def test_cli_output_is_redacted_and_report_filter_is_respected(self) -> None:
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        target = self._write(
            "unsafe.txt",
            marker + "\ncontact@example.invalid\n",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = scan_sensitive.main(
                [
                    "--repo-root",
                    str(self.root),
                    "--report",
                    "critical",
                    str(target),
                ]
            )
        rendered = output.getvalue()
        self.assertEqual(1, code)
        self.assertIn("CRITICAL PRIVATE_KEY", rendered)
        self.assertNotIn(marker, rendered)
        self.assertNotIn("contact@example.invalid", rendered)

    def test_allowlist_requires_reason_and_is_exact(self) -> None:
        target = self._write("known.txt", "password=RealisticValue123\n")
        allowlist_path = self._write(
            "allowlist.json",
            json.dumps(
                [
                    {
                        "rule": "GENERIC_SECRET",
                        "path": "known.txt",
                        "reason": "synthetic negative fixture",
                    }
                ]
            ),
        )
        allowlist = scan_sensitive.load_allowlist(allowlist_path)
        self.assertEqual(
            [],
            scan_sensitive.scan_file(target, self.root, allowlist),
        )

        invalid_path = self._write(
            "invalid.json",
            json.dumps([{"rule": "GENERIC_SECRET", "path": "known.txt"}]),
        )
        with self.assertRaises(ValueError):
            scan_sensitive.load_allowlist(invalid_path)

    def test_explicit_unicode_path_and_nested_node_modules(self) -> None:
        safe = self._write("中文目录/safe.txt", "ordinary content\n")
        self._write(
            "中文目录/node_modules/ignored.txt",
            "password=ShouldNotBeScanned123\n",
        )
        files = scan_sensitive.collect_files(self.root, [str(self.root / "中文目录")])
        self.assertEqual([safe.resolve()], files)

    def test_explicit_delivery_root_named_dist_is_scanned(self) -> None:
        artifact = self._write("dist/assets/app.js", "ordinary bundled content\n")
        self._write(
            "dist/node_modules/ignored.js",
            "password=ShouldNotBeScanned123\n",
        )

        files = scan_sensitive.collect_files(self.root, [str(self.root / "dist")])

        self.assertEqual([artifact.resolve()], files)

    def test_binary_file_is_skipped(self) -> None:
        target = self.root / "binary.dat"
        target.write_bytes(b"\0password=BinarySecret123")
        self.assertEqual([], scan_sensitive.scan_file(target, self.root, set()))


if __name__ == "__main__":
    unittest.main()
