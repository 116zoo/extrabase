#!/usr/bin/env python3
"""
merge_audit.py — Merge all pillar JSON results into audit.json + fixes.json.

Usage:
  python scripts/merge_audit.py \
    --run-dir runs/domain-com/2026-05-31 \
    --profile profiles/domain-com.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PILLAR_WEIGHTS = {
    "seo": 0.25,
    "geo": 0.20,
    "aeo": 0.15,
    "metadata": 0.10,
    "schema": 0.10,
    "llms": 0.10,
    "keywords": 0.10,
}

# Pillars that contribute a bonus/malus but are not part of the weighted score
BONUS_PILLARS = {"pages", "competitors", "competitor-content"}

# Files to ignore when scanning run-dir
IGNORED_FILES = {
    "audit.json",
    "fixes.json",
    "report.md",
    "report.pdf",
    "crawl.json",
    "build_report.py",
    "competitor-content-snapshot.json",
}

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# ID prefix per pillar
PILLAR_ID_PREFIX = {
    "seo": "seo",
    "geo": "geo",
    "aeo": "aeo",
    "metadata": "meta",
    "schema": "schema",
    "llms": "llms",
    "keywords": "kw",
    "pages": "pages",
    "competitors": "comp",
    "competitor-content": "ccm",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict | list | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_profile(profile_path: str) -> dict:
    p = Path(profile_path)
    if not p.exists():
        return {}
    data = load_json(p)
    return data if isinstance(data, dict) else {}


def scan_pillar_files(run_dir: Path) -> dict[str, dict]:
    """
    Scan run-dir for JSON files that contain a "pillar" key.
    Returns {pillar_name: pillar_data}.
    """
    pillars: dict[str, dict] = {}
    for file in sorted(run_dir.glob("*.json")):
        if file.name in IGNORED_FILES:
            continue
        data = load_json(file)
        if not isinstance(data, dict):
            continue
        pillar_name = data.get("pillar")
        if not pillar_name:
            continue
        # Last file wins if duplicates
        pillars[pillar_name] = data
    return pillars


def compute_global_score(pillar_scores: dict[str, int | float]) -> int:
    """
    Compute weighted global score from available scoring pillars.
    Missing pillars have their weight redistributed proportionally.
    """
    available = {k: v for k, v in pillar_scores.items() if k in PILLAR_WEIGHTS}
    if not available:
        return 0

    total_weight = sum(PILLAR_WEIGHTS[k] for k in available)
    if total_weight == 0:
        return 0

    weighted_sum = sum(
        PILLAR_WEIGHTS[k] * v for k, v in available.items()
    )
    # Redistribute: divide by actual total weight so scores scale to 100
    raw = weighted_sum / total_weight
    return round(raw)


def extract_fixes(pillar_name: str, pillar_data: dict) -> list[dict]:
    """
    Extract the fixes list from a pillar dict.
    Accepts both {"fixes": [...]} and {"fixes": {"items": [...]}} shapes.
    """
    raw = pillar_data.get("fixes", [])
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # Some pillar agents wrap fixes in a sub-key
        for key in ("items", "list", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
    return []


def assign_fix_ids(pillar_name: str, fixes: list[dict]) -> list[dict]:
    """
    Assign sequential IDs and source_pillar to each fix.
    Returns new list of fix dicts (does not mutate originals).
    """
    prefix = PILLAR_ID_PREFIX.get(pillar_name, pillar_name)
    result = []
    for i, fix in enumerate(fixes, start=1):
        new_fix = dict(fix)
        new_fix["id"] = f"{prefix}-{i:03d}"
        new_fix["source_pillar"] = pillar_name
        result.append(new_fix)
    return result


def dedup_key(fix: dict) -> tuple:
    """Deduplication key: (source_pillar, category, url)."""
    pillar = fix.get("source_pillar", "")
    category = fix.get("category", "")
    # url can be a string or a list; normalise to a frozenset for hashing
    url_raw = fix.get("url") or fix.get("urls") or ""
    if isinstance(url_raw, list):
        url_key = tuple(sorted(url_raw))
    else:
        url_key = url_raw
    return (pillar, category, url_key)


def sort_key(fix: dict) -> int:
    priority = fix.get("priority", "P3").upper()
    return PRIORITY_ORDER.get(priority, 99)


def count_fixes_by_priority(fixes: list[dict]) -> dict:
    counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for fix in fixes:
        p = fix.get("priority", "P3").upper()
        if p in counts:
            counts[p] += 1
        else:
            counts["P3"] += 1
    counts["total"] = sum(counts[v] for v in ("P0", "P1", "P2", "P3"))
    return counts


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def merge(run_dir: Path, profile: dict) -> dict:
    # 1. Scan pillar files
    pillar_data_map = scan_pillar_files(run_dir)

    # 2. Separate scoring pillars from bonus pillars
    scoring_pillars = {k: v for k, v in pillar_data_map.items() if k in PILLAR_WEIGHTS}
    bonus_pillars = {k: v for k, v in pillar_data_map.items() if k in BONUS_PILLARS}

    # 3. Collect scores
    pillar_scores: dict[str, int] = {}
    for name, data in scoring_pillars.items():
        score = data.get("score", 0)
        try:
            pillar_scores[name] = int(round(float(score)))
        except (TypeError, ValueError):
            pillar_scores[name] = 0

    global_score = compute_global_score(pillar_scores)

    # 4. Aggregate fixes from all pillars (scoring + bonus)
    all_fixes_raw: list[dict] = []
    for pillar_name in list(scoring_pillars.keys()) + list(bonus_pillars.keys()):
        fixes = extract_fixes(pillar_name, pillar_data_map[pillar_name])
        id_fixes = assign_fix_ids(pillar_name, fixes)
        all_fixes_raw.extend(id_fixes)

    # 5. Sort by priority then deduplicate
    all_fixes_raw.sort(key=sort_key)
    seen: set[tuple] = set()
    all_fixes: list[dict] = []
    for fix in all_fixes_raw:
        key = dedup_key(fix)
        if key not in seen:
            seen.add(key)
            all_fixes.append(fix)

    fixes_count = count_fixes_by_priority(all_fixes)

    # 6. Build audit.json structure
    date_str = run_dir.name  # e.g. "2026-05-31"

    scores_block = dict(pillar_scores)
    scores_block["global"] = global_score
    scores_block["pillars_included"] = sorted(pillar_scores.keys())

    audit = {
        "domain": profile.get("domain", ""),
        "url": profile.get("url", profile.get("base_url", "")),
        "name": profile.get("name", profile.get("domain", "")),
        "date": date_str,
        "scores": scores_block,
        "pillars": {name: data for name, data in pillar_data_map.items()},
        "fixes_count": fixes_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return audit, all_fixes


def write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Merge pillar JSONs into audit.json + fixes.json"
    )
    parser.add_argument("--run-dir", required=True, help="Path to run directory")
    parser.add_argument("--profile", required=True, help="Path to profile JSON")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        result = {"status": "error", "error": f"run_dir not found: {args.run_dir}"}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    profile = load_profile(args.profile)

    audit, all_fixes = merge(run_dir, profile)

    audit_path = run_dir / "audit.json"
    fixes_path = run_dir / "fixes.json"

    write_json(audit_path, audit)
    write_json(fixes_path, all_fixes)

    result = {
        "status": "ok",
        "audit_file": str(audit_path),
        "fixes_file": str(fixes_path),
        "scores": audit["scores"],
        "fixes_count": audit["fixes_count"],
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
