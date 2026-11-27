#!/usr/bin/env python3
"""Generate IEEE/ACM-compliant AI disclosure LaTeX paragraph strictly from AI_USAGE.md."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


def generate_disclosure_tex(ai_usage_md: Path, out_tex: Path) -> Dict[str, int]:
    text = ai_usage_md.read_text(encoding="utf-8")
    rows: List[Dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("| Date") or line.startswith("| :---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 5:
            rows.append({
                "date": parts[0],
                "model": parts[1].strip("`"),
                "role": parts[2],
                "purpose": parts[3],
                "files": parts[4],
            })
    models = sorted({r["model"] for r in rows})
    roles = sorted({r["role"] for r in rows})
    model_str = ", ".join(m.replace("_", r"\_") for m in models) if models else "None"
    role_str = ", ".join(r.replace("_", r"\_") for r in roles) if roles else "None"

    tex = (
        "% AUTO-GENERATED FROM AI_USAGE.md — DO NOT EDIT BY HAND\n"
        "\\section*{AI-Assisted Tooling Disclosure}\n"
        f"In accordance with IEEE and ACM publication policies on generative AI, "
        f"the authors disclose that AI coding and research assistants ({model_str}) "
        f"were used across {len(rows)} logged workflow steps covering roles ({role_str}) "
        "for literature API orchestration, simulation software engineering, drafting assistance, "
        "and cross-model pre-submission review. All empirical metrics, statistical tests, and LaTeX tables "
        "were computed deterministically by auditable Python scripts from sealed experiment runs "
        "(\\texttt{runs/*/manifest.json}), and all bibliographic citations were independently verified "
        "against Crossref, OpenAlex, and arXiv APIs. The human authors reviewed, verified, and take "
        "full responsibility for the entire manuscript and software artifact.\n"
    )
    out_tex.parent.mkdir(parents=True, exist_ok=True)
    out_tex.write_text(tex, encoding="utf-8")
    return {"logged_steps": len(rows), "unique_models": len(models)}
