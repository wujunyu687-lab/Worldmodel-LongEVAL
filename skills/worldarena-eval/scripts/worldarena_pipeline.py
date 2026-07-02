#!/usr/bin/env python3
"""Plan and preflight WorldArena pipeline runs."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_REPO = Path("/mnt/cfs/e71s16/wjy/WorldArena")

STANDARD_METRICS = {
    "trajectory_accuracy",
    "semantic_alignment",
    "depth_accuracy",
    "aesthetic_quality",
    "background_consistency",
    "dynamic_degree",
    "flow_score",
    "photometric_smoothness",
    "motion_smoothness",
    "image_quality",
    "subject_consistency",
    "psnr",
    "ssim",
}

ACTION_ALIASES = {"action_following", "action-following"}
VLM_ALIASES = {
    "vlm",
    "interaction_quality",
    "interaction-quality",
    "perspectivity",
    "instruction_following",
    "instruction-following",
}
JEPA_ALIASES = {"jepa", "jedi", "jepa_similarity", "jepa-similarity"}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="replace")


def split_metrics(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,\s]+", raw) if item.strip()]


def classify_metrics(metrics: list[str]) -> tuple[list[str], bool, bool, bool, list[str]]:
    standard: list[str] = []
    action = False
    vlm = False
    jepa = False
    unknown: list[str] = []
    for metric in metrics:
        key = metric.lower()
        if key in STANDARD_METRICS:
            standard.append(key)
        elif key in ACTION_ALIASES:
            action = True
        elif key in VLM_ALIASES:
            vlm = True
        elif key in JEPA_ALIASES:
            jepa = True
        elif key == "all":
            standard.extend(sorted(STANDARD_METRICS - {"psnr", "ssim"}))
            action = True
            vlm = True
            jepa = True
        else:
            unknown.append(metric)
    deduped_standard = list(dict.fromkeys(standard))
    return deduped_standard, action, vlm, jepa, unknown


def conda_envs() -> set[str]:
    if not shutil.which("conda"):
        return set()
    try:
        proc = subprocess.run(["conda", "env", "list"], text=True, capture_output=True, check=False)
    except Exception:
        return set()
    envs: set[str] = set()
    for line in proc.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts:
            envs.add(parts[0].replace("*", ""))
    return envs


def check_summary(path: Path) -> list[str]:
    issues: list[str] = []
    if not path.exists():
        return [f"summary_json missing: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"summary_json invalid JSON: {path} ({exc})"]
    if not isinstance(data, list):
        issues.append("summary_json should be a JSON list")
        return issues
    if not data:
        issues.append("summary_json is empty")
        return issues
    sample = data[0]
    if not isinstance(sample, dict):
        issues.append("summary_json entries should be objects")
        return issues
    for key in ["gt_path", "image", "prompt"]:
        if key not in sample:
            issues.append(f"summary_json first entry missing key: {key}")
    return issues


def preflight(args: argparse.Namespace) -> dict:
    repo = args.repo.expanduser().resolve()
    video_dir = Path(args.video_dir).expanduser().resolve() if args.video_dir else None
    summary_json = Path(args.summary_json).expanduser().resolve() if args.summary_json else None
    config = Path(args.config).expanduser().resolve() if args.config else repo / "video_quality/config/config.yaml"

    issues: list[str] = []
    warnings: list[str] = []

    if not repo.exists():
        issues.append(f"repo missing: {repo}")
    for rel in [
        "video_quality/run_evaluation.sh",
        "video_quality/run_action_following.sh",
        "video_quality/run_VLM_judge.sh",
        "video_quality/run_evaluation_JEPA.sh",
        "video_quality/evaluate.py",
    ]:
        if not (repo / rel).exists():
            issues.append(f"required file missing: {repo / rel}")

    if video_dir:
        if not video_dir.exists():
            issues.append(f"video_dir missing: {video_dir}")
        else:
            mp4_count = len(list(video_dir.glob("*.mp4")))
            if mp4_count == 0:
                issues.append(f"video_dir has no top-level mp4 files: {video_dir}")
    else:
        mp4_count = None

    if summary_json:
        issues.extend(check_summary(summary_json))

    placeholder_files: list[str] = []
    for path in [config, repo / "video_quality/run_evaluation_JEPA.sh"]:
        if path.exists():
            text = read_text(path)
            if "your absolute path" in text or "REAL_DIR_TO_GT" in text:
                placeholder_files.append(str(path))
    if placeholder_files:
        warnings.append("placeholder paths found; edit config/scripts before full evaluation")

    envs = conda_envs()
    missing_envs = [name for name in ["WorldArena", "WorldArena_VLM", "WorldArena_JEPA"] if envs and name not in envs]
    if not envs:
        warnings.append("could not inspect conda envs; conda may be unavailable in this shell")
    elif missing_envs:
        warnings.append(f"missing conda envs: {', '.join(missing_envs)}")

    return {
        "repo": str(repo),
        "video_dir": str(video_dir) if video_dir else None,
        "summary_json": str(summary_json) if summary_json else None,
        "config": str(config),
        "mp4_count": mp4_count,
        "placeholder_files": placeholder_files,
        "conda_envs_seen": sorted(envs),
        "issues": issues,
        "warnings": warnings,
        "ok_to_run_basic_pipeline": not issues,
    }


def plan(args: argparse.Namespace) -> dict:
    repo = args.repo.expanduser().resolve()
    video_dir = Path(args.video_dir).expanduser().resolve()
    summary_json = Path(args.summary_json).expanduser().resolve()
    if args.config:
        config_path = Path(args.config).expanduser()
        config_arg = str(config_path.resolve()) if config_path.is_absolute() else str((repo / args.config).resolve())
    else:
        config_arg = "./config/config.yaml"
    metrics = split_metrics(args.metrics)
    standard, action, vlm, jepa, unknown = classify_metrics(metrics)

    commands: list[dict[str, str]] = []
    workdir = repo / "video_quality"

    if standard:
        commands.append({
            "name": "standard_metrics",
            "workdir": str(workdir),
            "command": (
                f"bash run_evaluation.sh {args.model_name} {video_dir} {summary_json} "
                f"\"{','.join(standard)}\" {config_arg}"
            ),
        })
    if action:
        commands.append({
            "name": "action_following",
            "workdir": str(workdir),
            "command": f"bash run_action_following.sh {args.model_name} {video_dir} {summary_json} {config_arg}",
        })
    if vlm:
        commands.append({
            "name": "vlm_judge",
            "workdir": str(workdir),
            "command": f"bash run_VLM_judge.sh {args.model_name} {video_dir} {summary_json} all {config_arg}",
        })
    if jepa:
        commands.append({
            "name": "jepa_jedi",
            "workdir": str(workdir),
            "command": f"bash run_evaluation_JEPA.sh {video_dir}",
            "note": "Check run_evaluation_JEPA.sh for REAL_DIR_TO_GT before running.",
        })

    commands.append({
        "name": "aggregate_csv",
        "workdir": str(repo),
        "command": (
            f"python video_quality/csv_results/aggregate_results.py "
            f"--model_name {args.model_name} --base_dir video_quality --csv_name aggregated_results.csv"
        ),
    })

    return {
        "repo": str(repo),
        "model_name": args.model_name,
        "requested_metrics": metrics,
        "standard_metrics": standard,
        "run_action_following": action,
        "run_vlm": vlm,
        "run_jepa": jepa,
        "unknown_metrics": unknown,
        "commands": commands,
        "expected_outputs": [
            str(repo / "video_quality/output/*_results.json"),
            str(repo / "video_quality/output_action_following/*_results.json"),
            str(repo / f"video_quality/output_VLM/{args.model_name}/*.json"),
            str(repo / "video_quality/output_JEDi/results.json"),
            str(repo / "video_quality/csv_results/aggregated_results.csv"),
        ],
    }


def emit(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for key, value in report.items():
        if key == "commands":
            print("\ncommands:")
            for idx, cmd in enumerate(value, 1):
                print(f"  {idx}. {cmd['name']}")
                print(f"     cd {cmd['workdir']}")
                print(f"     {cmd['command']}")
                if cmd.get("note"):
                    print(f"     note: {cmd['note']}")
        elif isinstance(value, list):
            print(f"\n{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight and plan WorldArena pipeline runs.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    pre.add_argument("--video-dir")
    pre.add_argument("--summary-json")
    pre.add_argument("--config")
    pre.add_argument("--json", action="store_true")

    pl = sub.add_parser("plan")
    pl.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    pl.add_argument("--model-name", required=True)
    pl.add_argument("--video-dir", required=True)
    pl.add_argument("--summary-json", required=True)
    pl.add_argument("--metrics", required=True)
    pl.add_argument("--config", default=None, help="Config path. Defaults to ./config/config.yaml relative to video_quality.")
    pl.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "preflight":
        emit(preflight(args), args.json)
    elif args.cmd == "plan":
        emit(plan(args), args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
