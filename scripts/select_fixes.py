#!/usr/bin/env python3
"""
select_fixes.py — Interactive or automated fix selector from fixes.json.
Usage:
  python scripts/select_fixes.py \
    --fixes runs/domain/2026-05-31/fixes.json \
    --profile profiles/domain.json \
    [--non-interactive] \
    [--select p0|"1 3 5"]
Output: JSON to stdout {"selected": [fix_ids...], "skipped": [fix_ids...]}
"""
import argparse
import json
import sys


def load_fixes(fixes_path: str) -> list:
    with open(fixes_path, "r", encoding="utf-8") as f:
        return json.load(f)


def display_fix(index: int, fix: dict) -> None:
    priority = fix.get("priority", "?")
    title = fix.get("title", "(no title)")
    fix_id = fix.get("id", f"fix-{index}")
    before = fix.get("before")
    after = fix.get("after")
    print(f"\n[{index}] {priority} — {fix_id}")
    print(f"    {title}")
    if before is not None:
        before_str = json.dumps(before, ensure_ascii=False) if not isinstance(before, str) else before
        print(f"    Avant : {before_str[:120]}")
    if after is not None:
        after_str = json.dumps(after, ensure_ascii=False) if not isinstance(after, str) else after
        print(f"    Après : {after_str[:120]}")


def interactive_select(fixes: list) -> dict:
    selected = []
    skipped = []
    skip_all = False

    for i, fix in enumerate(fixes):
        fix_id = fix.get("id", f"fix-{i}")

        if skip_all:
            skipped.append(fix_id)
            continue

        display_fix(i, fix)
        while True:
            answer = input("    Appliquer ? [o/n/s=skip tout] : ").strip().lower()
            if answer in ("o", "oui", "y", "yes"):
                selected.append(fix_id)
                break
            elif answer in ("n", "non", "no"):
                skipped.append(fix_id)
                break
            elif answer in ("s", "skip"):
                skip_all = True
                skipped.append(fix_id)
                break
            else:
                print("    Répondre o (oui), n (non) ou s (skip tout).")

    return {"selected": selected, "skipped": skipped}


def non_interactive_select(fixes: list, select_arg: str) -> dict:
    selected = []
    skipped = []

    all_ids = [fix.get("id", f"fix-{i}") for i, fix in enumerate(fixes)]

    if select_arg.lower() == "p0":
        for fix in fixes:
            fix_id = fix.get("id", f"fix-{fixes.index(fix)}")
            if fix.get("priority", "").upper() == "P0":
                selected.append(fix_id)
            else:
                skipped.append(fix_id)
    else:
        try:
            indices = [int(x) for x in select_arg.split()]
        except ValueError:
            result = {
                "success": False,
                "selected": [],
                "skipped": all_ids,
                "error": f"invalid_select_value: {select_arg!r}",
            }
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(1)

        for i, fix in enumerate(fixes):
            fix_id = fix.get("id", f"fix-{i}")
            if i in indices:
                selected.append(fix_id)
            else:
                skipped.append(fix_id)

    return {"selected": selected, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(
        description="Select fixes interactively or automatically"
    )
    parser.add_argument("--fixes", required=True, help="Path to fixes.json")
    parser.add_argument("--profile", default=None, help="Path to profile JSON (unused, reserved)")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip interactive prompts",
    )
    parser.add_argument(
        "--select",
        default=None,
        help='Selection rule: "p0" or space-separated indices e.g. "1 3 5"',
    )
    args = parser.parse_args()

    try:
        fixes = load_fixes(args.fixes)
    except FileNotFoundError:
        result = {"error": "fixes_file_not_found"}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    except json.JSONDecodeError as e:
        result = {"error": f"fixes_json_invalid: {e}"}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    if not fixes:
        result = {"selected": [], "skipped": []}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    if args.non_interactive:
        if not args.select:
            result = {"error": "missing_select_arg_in_non_interactive_mode"}
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(1)
        result = non_interactive_select(fixes, args.select)
    else:
        result = interactive_select(fixes)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
