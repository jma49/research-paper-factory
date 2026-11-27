# Pipeline Role Specifications & Handoff Contracts

Every role operates inside a deterministic envelope: it reads explicit input files, writes explicit output artifacts, logs its execution to `AI_USAGE.md`, and obeys `CLAUDE.md`.

| Role | Primary Model | Fallback (Pre-Claude Reset) | Input Artifacts | Output Artifacts | Hard Redlines |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Coordinator** | `antigravity/gemini-4-neon` | `codex/gpt-6.2-sol` | Topic brief | `plan.md`, `state/pipeline_state.json` | Enforce G1–G4 gates; never bypass failed checks |
| **Scout** | `antigravity/gemini-4-neon` | `cursor/grok-4.7` | `plan.md` | `literature/refs.bib`, `literature/evidence.md` | Zero memory citations; API DOI/arXiv required |
| **Architect** | `codex/gpt-6.2-sol` | `cursor/composer-2.5` | `plan.md`, `data/traces/` | `src/`, `tests/`, `eval/harness.py` | Freeze harness after G1; deterministic seeds |
| **Runner** | `codex/gpt-6.2-astra` | `cursor/grok-4.7` | `eval/harness.py`, `data/traces/` | `runs/<run_id>/manifest.json`, `metrics.json` | Never modify harness; every run sealed with SHA-256 |
| **Auditor** | `deterministic_python` | None (Zero LLM) | `runs/*/manifest.json` | `results/results.json`, `paper/generated/numbers.tex`, `reports/audit_report.md` | Block on checksum mismatch or missing run |
| **Writer** | `claudeAgent/claude-opus-5-5` *(after Sat PM PST)* | `antigravity/gemini-4-neon` | `results/results.json`, `numbers.tex`, `evidence.md`, `refs.bib` | `paper/main.tex`, `paper/sections/*.tex` | Zero hand-typed numbers; Results -> Methods -> Intro -> Abstract |
| **Verifier** | `deterministic_python` + `cursor/grok-4.7` | None | `refs.bib`, `paper/main.tex`, `numbers.tex` | `reports/citation_report.md`, `reports/claim_trace_report.md` | 100% API existence check; flag preprint ratio >25% |
| **Reviewer** | `codex/gpt-6.2-sol` + `cursor/grok-4.7` *(+ Claude post-reset)* | — | `paper/main.tex`, `audit_report.md`, `citation_report.md` | `reports/review_*.md` | Different model family from Writer; no auto-fabricated experiments |
| **Typesetter** | `deterministic_python` | None | `paper/main.tex`, `AI_USAGE.md` | `paper/sections/ai_disclosure.tex`, `reports/compliance_checklist.md` | Disclosure strictly from `AI_USAGE.md` |
