#!/usr/bin/env python3
"""Inspect a WorldArena checkout using only stdlib."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


DEFAULT_REPO = Path("/mnt/cfs/e71s16/wjy/WorldArena")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="replace")


def extract_dimension_list(repo: Path) -> list[str]:
    path = repo / "video_quality/WorldArena/__init__.py"
    if not path.exists():
        return []
    text = read_text(path)
    match = re.search(r"def build_full_dimension_list\(self,\s*\):\s*return\s*(\[[^\]]+\])", text, re.S)
    if not match:
        return []
    try:
        value = ast.literal_eval(match.group(1))
    except Exception:
        return []
    return [str(item) for item in value]


def extract_csv_columns(repo: Path) -> list[str]:
    path = repo / "video_quality/csv_results/aggregate_results.py"
    if not path.exists():
        return []
    text = read_text(path)
    match = re.search(r"COLUMN_ORDER:\s*List\[str\]\s*=\s*(\[[^\]]+\])", text, re.S)
    if not match:
        match = re.search(r"COLUMN_ORDER\s*=\s*(\[[^\]]+\])", text, re.S)
    if not match:
        return []
    try:
        value = ast.literal_eval(match.group(1))
    except Exception:
        return []
    return [str(item) for item in value]


def detect_metric_mentions(repo: Path, names: list[str]) -> dict[str, bool]:
    roots = [
        repo / "video_quality/evaluate.py",
        repo / "video_quality/WorldArena/__init__.py",
        repo / "video_quality/csv_results/aggregate_results.py",
    ]
    combined = "\n".join(read_text(path) for path in roots if path.exists()).lower()
    return {name: name.lower() in combined for name in names}


def placeholder_paths(repo: Path) -> list[str]:
    files = [
        repo / "video_quality/config/config.yaml",
        repo / "video_quality/run_evaluation_JEPA.sh",
    ]
    hits: list[str] = []
    for path in files:
        if path.exists():
            text = read_text(path)
            if "your absolute path" in text or "REAL_DIR_TO_GT" in text:
                hits.append(str(path))
    return hits


def validate_inputs(video_dir: str | None, summary_json: str | None) -> list[str]:
    issues: list[str] = []
    if video_dir:
        path = Path(video_dir)
        if not path.exists():
            issues.append(f"video dir missing: {path}")
        elif not any(path.glob("*.mp4")):
            issues.append(f"video dir has no top-level mp4 files: {path}")
    if summary_json:
        path = Path(summary_json)
        if not path.exists():
            issues.append(f"summary json missing: {path}")
        else:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                issues.append(f"summary json is not valid JSON: {path} ({exc})")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect WorldArena metrics and common configuration issues.")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--video-dir", default=None)
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    report = {
        "repo": str(repo),
        "repo_exists": repo.exists(),
        "dimensions": extract_dimension_list(repo),
        "csv_columns": extract_csv_columns(repo),
        "main_metric_mentions": detect_metric_mentions(repo, ["fid", "fvd", "inception", "i3d"]),
        "placeholder_files": placeholder_paths(repo),
        "input_issues": validate_inputs(args.video_dir, args.summary_json),
        "known_issues": [
            "FID/FVD are not wired into the main evaluator unless current repo search proves otherwise.",
            "CSV uses Photometric Consistency but evaluator writes photometric_smoothness.",
            "JEPA script may need REAL_DIR_TO_GT replaced with the actual GT mp4 directory.",
        ],
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"WorldArena repo: {report['repo']}")
    print(f"exists: {report['repo_exists']}")
    print("\nEvaluator dimensions:")
    for item in report["dimensions"]:
        print(f"  - {item}")
    print("\nCSV columns:")
    for item in report["csv_columns"]:
        print(f"  - {item}")
    print("\nMain evaluator mentions:")
    for key, value in report["main_metric_mentions"].items():
        print(f"  - {key}: {value}")
    if report["placeholder_files"]:
        print("\nPlaceholder paths found:")
        for item in report["placeholder_files"]:
            print(f"  - {item}")
    if report["input_issues"]:
        print("\nInput issues:")
        for item in report["input_issues"]:
            print(f"  - {item}")
    print("\nKnown issues:")
    for item in report["known_issues"]:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
