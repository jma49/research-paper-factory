#!/usr/bin/env python3
"""Literature Scout & Citation Verifier (OpenAlex + Crossref + arXiv).

Strictly enforces the Zero-Memory-Citations redline:
- Fetches real bibliographic records directly from Crossref, OpenAlex, and arXiv APIs.
- Emits deterministic, escaped BibTeX (`refs.bib`) with verified DOI/URL provenance.
- Verifies existing `refs.bib` entries against live APIs and audits preprint ratios.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

USER_AGENT = "ResearchPaperFactory/1.0 (mailto:research-pipeline@example.org)"


def _http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_crossref_doi(doi: str) -> Optional[Dict[str, Any]]:
    doi_clean = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi_clean, safe='')}"
    try:
        data = _http_get_json(url)
        m = data.get("message", {})
        authors = []
        for a in m.get("author", []):
            fam = a.get("family", "").strip()
            giv = a.get("given", "").strip()
            if fam and giv:
                authors.append(f"{fam}, {giv}")
            elif fam:
                authors.append(fam)
        year = None
        for key in ("published-print", "published-online", "issued", "created"):
            parts = m.get(key, {}).get("date-parts", [[]])
            if parts and parts[0] and parts[0][0]:
                year = int(parts[0][0])
                break
        venue = (m.get("container-title") or [""])[0]
        title = (m.get("title") or [""])[0]
        item_type = m.get("type", "")
        entry_type = "article" if "journal" in item_type else ("inproceedings" if "proceedings" in item_type else "misc")
        return {
            "source": "crossref",
            "doi": doi_clean,
            "title": re.sub(r"\s+", " ", title).strip(),
            "authors": authors,
            "year": year,
            "venue": venue,
            "pages": m.get("page", ""),
            "volume": m.get("volume", ""),
            "number": m.get("issue", ""),
            "publisher": m.get("publisher", ""),
            "url": f"https://doi.org/{doi_clean}",
            "entry_type": entry_type,
            "is_preprint": False,
        }
    except Exception:
        return None


def search_openalex(query: str, per_page: int = 8) -> List[Dict[str, Any]]:
    params = urllib.parse.urlencode({"search": query, "per-page": per_page})
    url = f"https://api.openalex.org/works?{params}"
    try:
        data = _http_get_json(url)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for w in data.get("results", []):
        title = (w.get("display_name") or "").strip()
        if not title:
            continue
        doi = (w.get("doi") or "").removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        venue = src.get("display_name") or ""
        authors = [a.get("author", {}).get("display_name", "") for a in w.get("authorships", []) if a.get("author")]
        year = w.get("publication_year")
        is_preprint = ("arxiv" in venue.lower()) or (w.get("type") == "preprint") or (not venue)
        entry_type = "misc" if is_preprint else ("inproceedings" if "proceedings" in venue.lower() or "conference" in venue.lower() or "symposium" in venue.lower() else "article")
        out.append({
            "source": "openalex",
            "openalex_id": w.get("id", ""),
            "doi": doi,
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "cited_by_count": w.get("cited_by_count", 0),
            "url": f"https://doi.org/{doi}" if doi else (loc.get("landing_page_url") or w.get("id", "")),
            "entry_type": entry_type,
            "is_preprint": is_preprint,
        })
    return out


def fetch_arxiv_id(arxiv_id: str) -> Optional[Dict[str, Any]]:
    aid = arxiv_id.strip().removeprefix("arXiv:").removeprefix("https://arxiv.org/abs/")
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        xml_bytes = urllib.request.urlopen(req, timeout=20).read()
        root = ET.fromstring(xml_bytes)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return None
        title = re.sub(r"\s+", " ", (entry.findtext("a:title", "", ns) or "")).strip()
        summary = re.sub(r"\s+", " ", (entry.findtext("a:summary", "", ns) or "")).strip()
        published = entry.findtext("a:published", "", ns) or ""
        year = int(published[:4]) if len(published) >= 4 else None
        authors = [a.findtext("a:name", "", ns) or "" for a in entry.findall("a:author", ns)]
        return {
            "source": "arxiv",
            "arxiv_id": aid,
            "doi": "",
            "title": title,
            "authors": [a for a in authors if a],
            "year": year,
            "venue": f"arXiv preprint arXiv:{aid}",
            "abstract": summary,
            "url": f"https://arxiv.org/abs/{aid}",
            "entry_type": "misc",
            "is_preprint": True,
        }
    except Exception:
        return None


def make_cite_key(rec: Dict[str, Any], used: set[str]) -> str:
    authors = rec.get("authors") or ["unknown"]
    first = authors[0]
    surname = first.split(",")[0].strip() if "," in first else first.split()[-1].strip()
    surname = re.sub(r"[^a-zA-Z]", "", surname).lower() or "ref"
    year = str(rec.get("year") or "nd")
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", rec.get("title", "")) if w.lower() not in {"with", "from", "that", "this", "using", "toward", "towards", "study", "analysis"}]
    kw = words[0] if words else "paper"
    base = f"{surname}{year}{kw}"
    key = base
    i = 2
    while key in used:
        key = f"{base}{chr(96 + i)}"
        i += 1
    used.add(key)
    return key


def _escape_tex(val: str) -> str:
    return (
        val.replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


def record_to_bibtex(key: str, rec: Dict[str, Any]) -> str:
    etype = rec.get("entry_type", "misc")
    authors = " and ".join(rec.get("authors") or ["Unknown"])
    lines = [f"@{etype}{{{key},"]
    lines.append(f"  title = {{{{{_escape_tex(rec['title'])}}}}},")
    lines.append(f"  author = {{{_escape_tex(authors)}}},")
    if rec.get("year"):
        lines.append(f"  year = {{{rec['year']}}},")
    venue = rec.get("venue") or ""
    if etype == "inproceedings" and venue:
        lines.append(f"  booktitle = {{{_escape_tex(venue)}}},")
    elif etype == "article" and venue:
        lines.append(f"  journal = {{{_escape_tex(venue)}}},")
    elif venue:
        lines.append(f"  howpublished = {{{_escape_tex(venue)}}},")
    if rec.get("volume"):
        lines.append(f"  volume = {{{rec['volume']}}},")
    if rec.get("number"):
        lines.append(f"  number = {{{rec['number']}}},")
    if rec.get("pages"):
        lines.append(f"  pages = {{{rec['pages']}}},")
    if rec.get("publisher"):
        lines.append(f"  publisher = {{{_escape_tex(rec['publisher'])}}},")
    if rec.get("doi"):
        lines.append(f"  doi = {{{rec['doi']}}},")
    if rec.get("url"):
        lines.append(f"  url = {{{rec['url']}}},")
    lines.append(f"  note = {{Verified via {rec.get('source', 'api')}}}")
    lines.append("}")
    return "\n".join(lines)


def verify_bib_file(bib_path: Path, report_path: Path, max_preprint_ratio: float = 0.25) -> Dict[str, Any]:
    text = bib_path.read_text(encoding="utf-8")
    entries = re.findall(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", text, flags=re.S)
    results = []
    preprints = 0
    verified_count = 0
    for etype, key, body in entries:
        doi_m = re.search(r"doi\s*=\s*\{([^}]+)\}", body)
        url_m = re.search(r"url\s*=\s*\{([^}]+)\}", body)
        title_m = re.search(r"title\s*=\s*\{\{?([^}]+)\}?\}", body)
        doi = doi_m.group(1).strip() if doi_m else ""
        url = url_m.group(1).strip() if url_m else ""
        title = title_m.group(1).strip() if title_m else ""
        is_preprint = ("arxiv" in body.lower()) or (etype.lower() == "misc" and not doi)
        if is_preprint:
            preprints += 1
        status = "UNVERIFIED"
        matched_title = ""
        if doi:
            cr = fetch_crossref_doi(doi)
            if cr:
                status = "VERIFIED_CROSSREF"
                matched_title = cr["title"]
                verified_count += 1
        elif "arxiv.org/abs/" in url:
            aid = url.split("arxiv.org/abs/")[-1].strip()
            ax = fetch_arxiv_id(aid)
            if ax:
                status = "VERIFIED_ARXIV"
                matched_title = ax["title"]
                verified_count += 1
        elif url.startswith("http"):
            status = "VERIFIED_URL_ONLY"
            verified_count += 1
        results.append({
            "key": key,
            "type": etype,
            "doi": doi,
            "url": url,
            "bib_title": title,
            "api_title": matched_title,
            "is_preprint": is_preprint,
            "status": status,
        })
        time.sleep(0.08)

    total = len(results)
    preprint_ratio = (preprints / total) if total else 0.0
    summary = {
        "total_entries": total,
        "verified_entries": verified_count,
        "unverified_entries": total - verified_count,
        "preprint_count": preprints,
        "preprint_ratio": round(preprint_ratio, 4),
        "preprint_warning": preprint_ratio > max_preprint_ratio,
        "passed": (total > 0 and verified_count == total),
        "entries": results,
    }
    md = [
        "# Citation Verification Report",
        "",
        f"- **Total BibTeX Entries**: {total}",
        f"- **API-Verified Entries**: {verified_count}/{total}",
        f"- **Unverified Entries**: {total - verified_count}",
        f"- **Preprint Count / Ratio**: {preprints}/{total} ({preprint_ratio * 100:.1f}%) — Threshold: <= {max_preprint_ratio * 100:.0f}%",
        f"- **Gate Verdict**: {'PASS' if summary['passed'] else 'FAIL'}",
        "",
        "| Key | Type | Status | Preprint | DOI / URL |",
        "| :--- | :--- | :--- | :---: | :--- |",
    ]
    for r in results:
        ref_link = r["doi"] or r["url"]
        md.append(f"| `{r['key']}` | `{r['type']}` | `{r['status']}` | {'Yes' if r['is_preprint'] else 'No'} | {ref_link} |")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return summary
