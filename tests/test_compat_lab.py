import importlib
import json
import unittest
from pathlib import Path
from unittest import mock

from _support import make_repo_tmpdir
from retrotui.compat_lab import (
    CompatibilityCheck,
    CompatibilityReport,
    automated_checks,
    build_report,
    resolve_report_paths,
    run_compatibility_lab,
)


class CompatibilityLabTests(unittest.TestCase):
    def test_report_summary_and_markdown(self):
        report = CompatibilityReport(
            label="xterm",
            generated_at="2026-07-23T14:00:00+00:00",
            environment={"term": "xterm-256color"},
            checks=[
                CompatibilityCheck("a", "A", "pass", "ok", kind="automated"),
                CompatibilityCheck("b", "B", "warn", "maybe", "note"),
            ],
        )

        self.assertEqual(
            report.summary(),
            {"pass": 1, "warn": 1, "fail": 0, "skip": 0, "total": 2},
        )
        self.assertEqual(report.to_dict()["schema_version"], 1)
        markdown = report.to_markdown()
        self.assertIn("[PASS] A", markdown)
        self.assertIn("**Notes:** note", markdown)

    def test_automated_checks_detect_good_baseline(self):
        checks = automated_checks(
            {
                "stdout_encoding": "UTF-8",
                "preferred_encoding": "UTF-8",
                "stdin_tty": True,
                "stdout_tty": True,
                "terminal_columns": 120,
                "terminal_lines": 35,
                "term": "xterm-256color",
            }
        )
        by_id = {check.check_id: check for check in checks}

        self.assertEqual(by_id["encoding.utf8"].status, "pass")
        self.assertEqual(by_id["host.tty"].status, "pass")
        self.assertEqual(by_id["host.size"].status, "pass")
        self.assertEqual(by_id["host.identity"].status, "pass")
        self.assertEqual(by_id["unicode.width_model"].status, "pass")

    def test_automated_checks_warn_for_headless_small_terminal(self):
        checks = automated_checks(
            {
                "stdout_encoding": "ascii",
                "preferred_encoding": "ascii",
                "stdin_tty": False,
                "stdout_tty": False,
                "terminal_columns": 40,
                "terminal_lines": 10,
            }
        )
        by_id = {check.check_id: check for check in checks}

        self.assertEqual(by_id["encoding.utf8"].status, "warn")
        self.assertEqual(by_id["host.tty"].status, "warn")
        self.assertEqual(by_id["host.size"].status, "warn")
        self.assertEqual(by_id["host.identity"].status, "warn")

    def test_resolve_report_paths_accepts_directory_or_file(self):
        root = Path("reports")
        json_path, markdown_path = resolve_report_paths(
            root,
            label="Windows Terminal",
            stamp="20260723-140000",
        )
        self.assertEqual(
            json_path,
            root / "20260723-140000-Windows-Terminal.json",
        )
        self.assertEqual(
            markdown_path,
            root / "20260723-140000-Windows-Terminal.md",
        )

        json_path, markdown_path = resolve_report_paths(
            root / "result.json",
            label="ignored",
            stamp="ignored",
        )
        self.assertEqual(json_path, root / "result.json")
        self.assertEqual(markdown_path, root / "result.md")

    def test_noninteractive_run_writes_json_and_markdown(self):
        tmpdir = make_repo_tmpdir(prefix="_tmp_compat_")
        self.addCleanup(tmpdir.cleanup)
        output_dir = Path(tmpdir.name)
        environment = {
            "platform": "TestOS",
            "stdout_encoding": "UTF-8",
            "preferred_encoding": "UTF-8",
            "stdin_tty": False,
            "stdout_tty": False,
            "terminal_columns": 120,
            "terminal_lines": 35,
            "term": "test-term",
        }

        with mock.patch(
            "retrotui.compat_lab.collect_environment",
            return_value=environment,
        ):
            rc = run_compatibility_lab(
                output_path=output_dir,
                label="CI",
                interactive=False,
            )

        self.assertEqual(rc, 0)
        json_files = list(output_dir.glob("*.json"))
        markdown_files = list(output_dir.glob("*.md"))
        self.assertEqual(len(json_files), 1)
        self.assertEqual(len(markdown_files), 1)
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        self.assertEqual(data["label"], "CI")
        self.assertTrue(
            any(item["check_id"] == "lab.guided" for item in data["checks"])
        )

    def test_build_report_uses_terminal_identity_in_default_label(self):
        environment = {
            "platform": "Linux",
            "term_program": "kitty",
            "stdout_encoding": "UTF-8",
            "preferred_encoding": "UTF-8",
            "stdin_tty": True,
            "stdout_tty": True,
            "terminal_columns": 100,
            "terminal_lines": 30,
        }
        with mock.patch(
            "retrotui.compat_lab.collect_environment",
            return_value=environment,
        ):
            report = build_report()

        self.assertEqual(report.label, "Linux-kitty")


class CompatibilityLabEntryTests(unittest.TestCase):
    def test_main_cli_routes_compatibility_arguments(self):
        entry = importlib.import_module("retrotui.__main__")
        argv = ["--compat-lab", "--compat-auto"]

        with mock.patch.object(entry, "_compat_lab_cli", return_value=7) as runner:
            rc = entry.main_cli(argv)

        self.assertEqual(rc, 7)
        runner.assert_called_once_with(argv)

    def test_compatibility_cli_forwards_options_without_loading_desktop(self):
        entry = importlib.import_module("retrotui.__main__")
        argv = [
            "--compat-lab",
            "--compat-auto",
            "--compat-output",
            "reports",
            "--compat-label",
            "Windows Terminal",
        ]

        with mock.patch(
            "retrotui.compat_lab.run_compatibility_lab",
            return_value=3,
        ) as runner:
            rc = entry._compat_lab_cli(argv)

        self.assertEqual(rc, 3)
        runner.assert_called_once_with(
            output_path="reports",
            label="Windows Terminal",
            interactive=False,
        )


if __name__ == "__main__":
    unittest.main()
