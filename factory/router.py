#!/usr/bin/env python3
"""Quota-aware multi-provider model router for Research Paper Factory.

Supports Antigravity (Gemini), Codex (GPT-6.x), Cursor (Grok / Composer),
and Claude (Opus/Sonnet 5.5) with explicit quota reset windows (e.g., Claude
quota reset on Saturday afternoon PST: 2026-11-28T15:00:00-08:00).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_iso(ts: Optional[str]) -> Optional[dt.datetime]:
    if not ts:
        return None
    return dt.datetime.fromisoformat(ts)


class ModelRouter:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = json.loads(self.config_path.read_text(encoding="utf-8"))

    def is_provider_available(self, provider_id: str, now: Optional[dt.datetime] = None) -> tuple[bool, str]:
        if provider_id == "deterministic_python":
            return True, "deterministic local Python engine"
        providers = self.config.get("providers", {})
        if provider_id not in providers:
            return False, f"unknown provider {provider_id}"
        p = providers[provider_id]
        qw = p.get("quotaWindow", {})
        status = qw.get("status", "available")
        avail_after = _parse_iso(qw.get("availableAfter"))
        cur = now or dt.datetime.now(dt.timezone.utc)
        if cur.tzinfo is None:
            cur = cur.replace(tzinfo=dt.timezone.utc)
        if status == "available":
            return True, "available"
        if avail_after is not None:
            if cur >= avail_after:
                return True, f"quota reset passed ({avail_after.isoformat()})"
            return False, f"quota exhausted until {avail_after.isoformat()}"
        return False, f"status={status}"

    def resolve_role(
        self,
        role: str,
        now: Optional[dt.datetime] = None,
        exclude_providers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        exclude = set(exclude_providers or [])
        role_cfg = self.config["roles"][role]
        candidates = [role_cfg["primary"]] + list(role_cfg.get("fallbacks", []))
        reasons: List[str] = []
        for idx, cand in enumerate(candidates):
            pid = cand["provider"]
            if pid in exclude:
                reasons.append(f"skip {pid}/{cand['model']} (excluded for cross-model independence)")
                continue
            ok, reason = self.is_provider_available(pid, now=now)
            if ok:
                p_opts = self.config.get("providers", {}).get(pid, {}).get("options", {})
                return {
                    "role": role,
                    "provider": pid,
                    "model": cand["model"],
                    "options": p_opts,
                    "is_fallback": idx > 0,
                    "reason": reason,
                    "skipped": reasons,
                }
            reasons.append(f"skip {pid}/{cand['model']} ({reason})")
        raise RuntimeError(f"No available provider for role '{role}': {'; '.join(reasons)}")

    def routing_table(self, now: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        writer_provider: Optional[str] = None
        for role in self.config["roles"]:
            excl = [writer_provider] if (role == "reviewer" and writer_provider) else []
            res = self.resolve_role(role, now=now, exclude_providers=excl)
            if role == "writer":
                writer_provider = res["provider"]
            rows.append(res)
        return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect quota-aware routing table.")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "pipeline.config.json"))
    parser.add_argument("--at", default=None, help="ISO timestamp override (e.g. 2026-11-28T16:00:00-08:00)")
    args = parser.parse_args()
    router = ModelRouter(Path(args.config))
    override_now = _parse_iso(args.at) if args.at else None
    print(json.dumps(router.routing_table(now=override_now), indent=2, ensure_ascii=False))
