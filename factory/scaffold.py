#!/usr/bin/env python3
"""Topic Repository Scaffolder & Pipeline State Manager.

Instantiates a complete, policy-enforced research paper repository for any new topic,
including CLAUDE.md, AGENTS.md, AI_USAGE.md, state tracking, directory skeleton,
and GitHub Actions verification workflow.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path


def append_ai_usage(repo_dir: Path, provider: str, model: str, role: str, purpose: str, files: str) -> None:
    log = repo_dir / "AI_USAGE.md"
    if not log.exists():
        log.write_text(
            "# AI Usage Audit Log\n\n"
            "> Single source of truth for IEEE/ACM AI-generated content disclosure.\n\n"
            "| Date (UTC) | Provider / Model | Pipeline Role | Purpose | Touched Artifacts |\n"
            "| :--- | :--- | :--- | :--- | :--- |\n",
            encoding="utf-8",
        )
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"| {now} | `{provider}/{model}` | {role} | {purpose} | {files} |\n")


def scaffold_topic(
    target_dir: Path,
    topic_slug: str,
    title: str,
    target_venue: str,
    factory_root: Path,
) -> Path:
    target_dir = Path(target_dir).resolve()
    subdirs = [
        "literature",
        "data/traces",
        "src",
        "tests",
        "eval",
        "runs",
        "results",
        "paper/sections",
        "paper/generated/tables",
        "paper/figures",
        "reports",
        "state",
        ".github/workflows",
        ".agents",
    ]
    for sd in subdirs:
        (target_dir / sd).mkdir(parents=True, exist_ok=True)

    # Copy policy & pipeline config
    shutil.copy2(factory_root / "CLAUDE.md", target_dir / "CLAUDE.md")
    shutil.copy2(factory_root / "CLAUDE.md", target_dir / "AGENTS.md")
    shutil.copy2(factory_root / "pipeline.config.json", target_dir / "pipeline.config.json")

    state_file = target_dir / "state" / "pipeline_state.json"
    if not state_file.exists():
        state = {
            "topic_slug": topic_slug,
            "title": title,
            "target_venue": target_venue,
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "current_stage": "STAGE_1_PLAN_AND_SCOUT",
            "gates": {
                "G1_PLAN_FREEZE": {"status": "pending", "approved_by": None, "approved_at": None},
                "G2_RESULTS_AUDIT": {"status": "pending", "approved_by": None, "approved_at": None},
                "G3_REVIEW_DECISION": {"status": "pending", "approved_by": None, "approved_at": None},
                "G4_SUBMISSION_COMPLIANCE": {"status": "pending", "approved_by": None, "approved_at": None},
            },
            "revision_rounds": 0,
            "max_revision_rounds": 3,
        }
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ci_yml = target_dir / ".github" / "workflows" / "verify-lineage.yml"
    ci_yml.write_text(
        """name: Verify Paper Lineage & Reproducibility

on:
  push:
  pull_request:

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run unit tests
        run: python3 -m unittest discover -s tests -p "test_*.py" -v
      - name: Verify sealed runs & deterministic audit
        run: |
          if [ -f eval/audit.py ]; then
            python3 eval/audit.py --verify-only
          fi
""",
        encoding="utf-8",
    )

    append_ai_usage(
        target_dir,
        provider="antigravity",
        model="gemini-4-neon",
        role="Coordinator",
        purpose=f"Scaffolded topic repository '{topic_slug}' from research-paper-factory",
        files="CLAUDE.md, AGENTS.md, pipeline.config.json, state/pipeline_state.json",
    )
    return target_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold a new research paper repository.")
    parser.add_argument("--dir", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--venue", default="ICSE / FSE / ASE (IEEEtran)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = scaffold_topic(Path(args.dir), args.slug, args.title, args.venue, root)
    print(f"Scaffolded topic repo at {out}")
