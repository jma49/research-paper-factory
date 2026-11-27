#!/usr/bin/env python3
"""Unit tests for research-paper-factory core modules."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from factory.auditor import audit_runs, bootstrap_ci, cliffs_delta, sha256_file, write_numbers_tex
from factory.disclosure import generate_disclosure_tex
from factory.router import ModelRouter


class TestPaperFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parent.parent
        self.router = ModelRouter(self.root / "pipeline.config.json")

    def test_claude_quota_window_routing(self) -> None:
        before_reset = dt.datetime.fromisoformat("2026-11-26T17:00:00-08:00")
        after_reset = dt.datetime.fromisoformat("2026-11-28T16:00:00-08:00")

        w_before = self.router.resolve_role("writer", now=before_reset)
        self.assertEqual(w_before["provider"], "antigravity")
        self.assertTrue(w_before["is_fallback"])

        w_after = self.router.resolve_role("writer", now=after_reset)
        self.assertEqual(w_after["provider"], "claudeAgent")
        self.assertEqual(w_after["model"], "claude-opus-5-5")
        self.assertFalse(w_after["is_fallback"])

    def test_cross_model_independence(self) -> None:
        table = {r["role"]: r for r in self.router.routing_table()}
        self.assertNotEqual(table["writer"]["provider"], table["reviewer"]["provider"])

    def test_auditor_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td) / "runs"
            r1 = runs / "run_001"
            r1.mkdir(parents=True)
            metrics_p = r1 / "metrics.json"
            metrics_p.write_text(json.dumps({"throughput": 12.5}), encoding="utf-8")
            manifest = {
                "run_id": "run_001",
                "experiment": "unit_test",
                "timestamp_utc": "2026-11-26T00:00:00Z",
                "git_commit": "abc1234",
                "harness_sha256": "0" * 64,
                "dataset_sha256": "1" * 64,
                "command": "python3 eval/run.py",
                "seeds": [1, 2, 3],
                "metrics_file": "metrics.json",
                "metrics_sha256": sha256_file(metrics_p),
            }
            (r1 / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            ok = audit_runs(runs)
            self.assertTrue(ok["passed"])

            # Tamper with metrics.json -> must fail!
            metrics_p.write_text(json.dumps({"throughput": 999.9}), encoding="utf-8")
            bad = audit_runs(runs)
            self.assertFalse(bad["passed"])
            self.assertTrue(any("Tamper" in e for e in bad["errors"]))

    def test_stats_and_macros(self) -> None:
        mean, lo, hi = bootstrap_ci([10.0, 11.0, 12.0, 13.0])
        self.assertAlmostEqual(mean, 11.5)
        self.assertLessEqual(lo, mean)
        self.assertGreaterEqual(hi, mean)
        self.assertAlmostEqual(cliffs_delta([10, 11], [1, 2]), 1.0)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "numbers.tex"
            write_numbers_tex({"TestMetric": ("12.3", "run_001")}, out)
            self.assertIn(r"\newcommand{\TestMetric}{12.3}", out.read_text(encoding="utf-8"))

    def test_disclosure_generation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            usage = Path(td) / "AI_USAGE.md"
            usage.write_text(
                "| Date (UTC) | Provider / Model | Pipeline Role | Purpose | Touched Artifacts |\n"
                "| :--- | :--- | :--- | :--- | :--- |\n"
                "| 2026-11-26 17:00 | `codex/gpt-6.2-sol` | Architect | Implemented simulator | src/sim.py |\n",
                encoding="utf-8",
            )
            out = Path(td) / "disclosure.tex"
            info = generate_disclosure_tex(usage, out)
            self.assertEqual(info["logged_steps"], 1)
            self.assertIn("codex/gpt-6.2-sol", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
