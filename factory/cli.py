#!/usr/bin/env python3
"""Unified CLI for Research Paper Factory."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from factory.auditor import audit_runs
from factory.disclosure import generate_disclosure_tex
from factory.router import ModelRouter
from factory.scaffold import scaffold_topic
from factory.scout import verify_bib_file


def main() -> None:
    parser = argparse.ArgumentParser(prog="paper-factory", description="Research Paper Factory CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_route = sub.add_parser("route", help="Show active quota-aware provider routing table")
    p_route.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "pipeline.config.json"))
    p_route.add_argument("--at", default=None, help="ISO timestamp override to test quota reset windows")

    p_init = sub.add_parser("init", help="Scaffold a new research topic repository")
    p_init.add_argument("--dir", required=True)
    p_init.add_argument("--slug", required=True)
    p_init.add_argument("--title", required=True)
    p_init.add_argument("--venue", default="ICSE / FSE / ASE (IEEEtran)")

    p_verify = sub.add_parser("verify-bib", help="Verify every citation in refs.bib against live APIs")
    p_verify.add_argument("--bib", required=True)
    p_verify.add_argument("--report", required=True)

    p_audit = sub.add_parser("audit-runs", help="Audit all sealed runs under runs/")
    p_audit.add_argument("--runs", required=True)

    p_disc = sub.add_parser("gen-disclosure", help="Generate IEEE/ACM AI disclosure .tex from AI_USAGE.md")
    p_disc.add_argument("--usage", required=True)
    p_disc.add_argument("--out", required=True)

    args = parser.parse_args()
    factory_root = Path(__file__).resolve().parent.parent

    if args.cmd == "route":
        router = ModelRouter(Path(args.config))
        now = dt.datetime.fromisoformat(args.at) if args.at else None
        print(json.dumps(router.routing_table(now=now), indent=2, ensure_ascii=False))
    elif args.cmd == "init":
        out = scaffold_topic(Path(args.dir), args.slug, args.title, args.venue, factory_root)
        print(f"Initialized topic repository at: {out}")
    elif args.cmd == "verify-bib":
        res = verify_bib_file(Path(args.bib), Path(args.report))
        print(json.dumps({k: v for k, v in res.items() if k != "entries"}, indent=2))
        if not res["passed"]:
            raise SystemExit(1)
    elif args.cmd == "audit-runs":
        res = audit_runs(Path(args.runs))
        print(json.dumps({k: v for k, v in res.items() if k != "runs"}, indent=2))
        if not res["passed"]:
            raise SystemExit(1)
    elif args.cmd == "gen-disclosure":
        res = generate_disclosure_tex(Path(args.usage), Path(args.out))
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
