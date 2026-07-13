#!/usr/bin/env python3
"""Autonomous setup and execution controller for the WorldArena pipeline."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from worldarena_pipeline import STANDARD_METRICS, check_summary, classify_metrics, split_metrics


DEFAULT_REPO = Path("/mnt/cfs/e71s16/wjy/WorldArena")

CORE_METRICS = [
    "image_quality",
    "subject_consistency",
    "background_consistency",
    "dynamic_degree",
    "flow_score",
    "photometric_smoothness",
    "motion_smoothness",
    "depth_accuracy",
    "trajectory_accuracy",
    "vlm",
    "jepa",
]

FULL_METRICS = sorted(STANDARD_METRICS - {"psnr", "ssim"}) + [
    "action_following",
    "vlm",
    "jepa",
]


def expand_metrics(raw: str | None) -> list[str]:
    if not raw:
        return []
    key = raw.strip().lower()
    if key == "core":
        return CORE_METRICS.copy()
    if key == "full":
        return FULL_METRICS.copy()
    return split_metrics(raw)


def run(command: list[str], cwd: Path | None = None, log=None) -> None:
    rendered = " ".join(shlex.quote(part) for part in command)
    print(f"[run] {rendered}", flush=True)
    if log:
        log.write(f"\n[run] {rendered}\n")
        log.flush()
    proc = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    tail: list[str] = []
    for line in proc.stdout:
        print(line, end="")
        tail.append(line.rstrip())
        tail = tail[-30:]
        if log:
            log.write(line)
    code = proc.wait()
    if code != 0:
        detail = "\n".join(tail)
        raise RuntimeError(f"command failed with exit code {code}: {rendered}\n{detail}")


def conda_executable() -> str | None:
    candidates = [
        shutil.which("conda"),
        "/root/miniconda3/bin/conda",
        "/opt/conda/bin/conda",
    ]
    return next((item for item in candidates if item and Path(item).exists()), None)


def conda_env_names(conda: str) -> set[str]:
    proc = subprocess.run([conda, "env", "list", "--json"], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return set()
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return set()
    return {Path(path).name for path in data.get("envs", [])}


def smoke_env(conda: str, env: str, code: str) -> bool:
    proc = subprocess.run([conda, "run", "-n", env, "python", "-c", code], capture_output=True, text=True)
    return proc.returncode == 0


def env_install_commands(repo: Path, families: set[str]) -> dict[str, list[list[str]]]:
    commands: dict[str, list[list[str]]] = {}
    if "base" in families:
        commands["WorldArena"] = [
            ["python", "-m", "pip", "install", "-U", "pip"],
            ["python", "-m", "pip", "install", "setuptools<81", "wheel"],
            ["python", "-m", "pip", "install", "-r", str(repo / "video_quality/requirements.txt")],
            ["python", "-m", "pip", "install", "ipython", "ninja", "mamba-ssm", "transformers==4.51.3"],
        ]
    if "vlm" in families:
        commands["WorldArena_VLM"] = [
            ["python", "-m", "pip", "install", "torch==2.9.1", "torchvision==0.24.1", "torchaudio==2.9.1", "--index-url", "https://download.pytorch.org/whl/cu128"],
            ["python", "-m", "pip", "install", "-r", str(repo / "video_quality/requirements_worldarena_vlm.txt")],
            ["python", "-m", "pip", "install", "git+https://github.com/huggingface/transformers.git"],
        ]
    if "jepa" in families:
        commands["WorldArena_JEPA"] = [
            ["python", "-m", "pip", "install", "-r", str(repo / "video_quality/requirements_jedi.txt")],
        ]
    return commands


def ensure_envs(repo: Path, families: set[str], execute: bool, log=None) -> list[str]:
    conda = conda_executable()
    if not conda:
        raise RuntimeError("conda was not found; install Miniconda/Conda or provide it on PATH")
    existing = conda_env_names(conda)
    commands = env_install_commands(repo, families)
    smoke = {
        "WorldArena": "import torch, cv2, clip, pyiqa, sam3, mmcv",
        "WorldArena_VLM": "import torch, cv2; from transformers import AutoProcessor, Qwen3VLForConditionalGeneration",
        "WorldArena_JEPA": "import torch, decord; from videojedi import JEDiMetric",
    }
    actions: list[str] = []
    for env, installs in commands.items():
        needs_install = env not in existing or not smoke_env(conda, env, smoke[env])
        if not needs_install:
            actions.append(f"reuse healthy conda env: {env}")
            continue
        actions.append(f"create/repair conda env: {env}")
        if not execute:
            continue
        if env not in existing:
            run([conda, "create", "-y", "-n", env, "python=3.10"], log=log)
        for command in installs:
            run([conda, "run", "-n", env, *command], cwd=repo, log=log)
        if not smoke_env(conda, env, smoke[env]):
            raise RuntimeError(f"environment smoke test failed after installation: {env}")
    return actions


def download_file(url: str, destination: Path, execute: bool, log=None) -> str:
    if destination.exists() and destination.stat().st_size > 0:
        return f"reuse file: {destination}"
    if not execute:
        return f"download {url} -> {destination}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("curl is required for checkpoint downloads")
    run([curl, "-L", "--fail", "--retry", "5", "--continue-at", "-", "-o", str(destination), url], log=log)
    return f"downloaded: {destination}"


def hf_snapshot(
    conda: str,
    download_env: str,
    repo_id: str,
    destination: Path,
    marker: str,
    execute: bool,
    log=None,
) -> str:
    if (destination / marker).exists():
        return f"reuse snapshot: {destination}"
    if not execute:
        return f"hf download {repo_id} -> {destination}"
    destination.mkdir(parents=True, exist_ok=True)
    code = (
        "from huggingface_hub import snapshot_download; import sys; "
        "snapshot_download(repo_id=sys.argv[1], local_dir=sys.argv[2])"
    )
    command = [conda, "run", "-n", download_env, "python", "-c", code, repo_id, str(destination)]
    try:
        run(command, log=log)
    except RuntimeError as exc:
        if "401" in str(exc) or "403" in str(exc):
            raise RuntimeError(f"Hugging Face authentication is required for {repo_id}; set HF_TOKEN and retry") from exc
        raise
    return f"downloaded snapshot: {destination}"


def required_families(metrics: list[str]) -> tuple[set[str], list[str], bool, bool, bool]:
    standard, action, vlm, jepa, unknown = classify_metrics(metrics)
    if unknown:
        raise RuntimeError(f"unsupported metrics: {', '.join(unknown)}")
    families: set[str] = set()
    if standard or action:
        families.add("base")
    if vlm:
        families.add("vlm")
    if jepa:
        families.add("jepa")
    return families, standard, action, vlm, jepa


def required_weight_keys(standard: list[str], action: bool, vlm: bool, jepa: bool) -> set[str]:
    keys: set[str] = set()
    if standard:
        keys.add("sam3")
    if action:
        keys.add("clip_b32")
    mapping = {
        "semantic_alignment": {"qwen25_caption", "clip_text"},
        "depth_accuracy": {"depth_anything"},
        "aesthetic_quality": {"clip_l14", "aesthetic_head"},
        "background_consistency": {"clip_b32", "raft"},
        "dynamic_degree": {"raft"},
        "flow_score": {"raft"},
        "photometric_smoothness": {"sea_raft"},
        "motion_smoothness": {"vfimamba"},
        "image_quality": {"musiq"},
        "subject_consistency": {"dino_repo", "dino_weight", "raft"},
    }
    for metric in standard:
        keys.update(mapping.get(metric, set()))
    if vlm:
        keys.add("qwen3_vl")
    if jepa:
        keys.add("jepa_weights")
    return keys


def ensure_weights(
    repo: Path,
    weights: Path,
    keys: set[str],
    download_env: str,
    execute: bool,
    log=None,
) -> list[str]:
    conda = conda_executable()
    if not conda:
        raise RuntimeError("conda was not found")
    actions: list[str] = []
    direct = {
        "clip_b32": ("https://openaipublic.azureedge.net/clip/models/40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt", weights / "clip_model/ViT-B-32.pt"),
        "clip_l14": ("https://huggingface.co/jinaai/clip-models/resolve/main/ViT-L-14.pt", weights / "clip_model/ViT-L-14.pt"),
        "aesthetic_head": ("https://github.com/LAION-AI/aesthetic-predictor/raw/refs/heads/main/sa_0_4_vit_l_14_linear.pth", weights / "aesthetic_model/emb_reader/sa_0_4_vit_l_14_linear.pth"),
        "raft": ("https://huggingface.co/RaphaelLiu/EvalCrafter-Models/resolve/main/RAFT/models/raft-things.pth", weights / "raft_model/models/raft-things.pth"),
        "vfimamba": ("https://huggingface.co/MCG-NJU/VFIMamba/resolve/main/model.pkl", weights / "vfimamba/model.pkl"),
        "musiq": ("https://huggingface.co/chaofengc/IQA-PyTorch-Weights/resolve/main/musiq_spaq_ckpt-358bb6af.pth", weights / "pyiqa_model/musiq_spaq_ckpt-358bb6af.pth"),
        "dino_weight": ("https://huggingface.co/Xiaomabufei/lumos/resolve/main/dino_vitbase16_pretrain.pth", weights / "dino_model/dino_vitbase16_pretrain.pth"),
    }
    for key, pair in direct.items():
        if key in keys:
            actions.append(download_file(pair[0], pair[1], execute, log))

    snapshots = {
        "qwen25_caption": ("Qwen/Qwen2.5-VL-7B-Instruct", weights / "Qwen2.5-VL-7B-Instruct", "config.json"),
        "clip_text": ("openai/clip-vit-base-patch16", weights / "clip-vit-base-patch16", "config.json"),
        "depth_anything": ("depth-anything/Depth-Anything-V2-Small-hf", weights / "depth-anything", "config.json"),
        "sam3": ("facebook/sam3", weights / "sam", "sam3.pt"),
        "qwen3_vl": ("Qwen/Qwen3-VL-8B-Instruct", weights / "qwenvl3", "config.json"),
    }
    for key, pair in snapshots.items():
        if key in keys:
            actions.append(hf_snapshot(conda, download_env, pair[0], pair[1], pair[2], execute, log))

    if "sam3" in keys:
        actions.append(download_file(
            "https://huggingface.co/OpenGVLab/ViCLIP-B-16-hf/resolve/main/bpe_simple_vocab_16e6.txt.gz",
            weights / "sam/bpe_simple_vocab_16e6.txt.gz",
            execute,
            log,
        ))

    if "dino_repo" in keys:
        destination = weights / "dino_model/facebookresearch_dino_main"
        if destination.exists():
            actions.append(f"reuse git repo: {destination}")
        elif execute:
            destination.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", "--depth", "1", "https://github.com/facebookresearch/dino.git", str(destination)], log=log)
            actions.append(f"cloned: {destination}")
        else:
            actions.append(f"clone facebookresearch/dino -> {destination}")

    if "sea_raft" in keys:
        source = weights / "sea_raft/model.safetensors"
        target = weights / "sea_raft/Tartan-C-T-TSKH-spring540x960-M.pth"
        actions.append(download_file(
            "https://huggingface.co/MemorySlices/Tartan-C-T-TSKH-spring540x960-M/resolve/main/model.safetensors",
            source,
            execute,
            log,
        ))
        if target.exists():
            actions.append(f"reuse converted checkpoint: {target}")
        elif execute:
            code = "from safetensors.torch import load_file; import torch,sys; torch.save(load_file(sys.argv[1]), sys.argv[2])"
            run([conda, "run", "-n", "WorldArena", "python", "-c", code, str(source), str(target)], log=log)
            actions.append(f"converted: {target}")
        else:
            actions.append(f"convert safetensors -> {target}")

    if "jepa_weights" in keys:
        base = repo / "video_quality/JEDi/pretrained_models"
        actions.append(download_file("https://dl.fbaipublicfiles.com/jepa/vith16/vith16.pth.tar", base / "vith16.pth.tar", execute, log))
        actions.append(download_file("https://dl.fbaipublicfiles.com/jepa/vith16/ssv2-probe.pth.tar", base / "ssv2-probe.pth.tar", execute, log))
    return actions


def config_text(repo: Path, weights: Path) -> str:
    q = lambda path: json.dumps(str(path))
    return f'''model_name: test
data:
  gt_path: {q(repo / "video_quality/data/gt_dataset")}
  val_base: {q(repo / "video_quality/data/generated_dataset")}
data_action_following:
  gt_path: {q(repo / "video_quality/data_action_following/gt_dataset")}
  val_base: {q(repo / "video_quality/data_action_following/generated_dataset")}
save_path: {q(repo / "video_quality/output")}
save_path_action_following: {q(repo / "video_quality/output_action_following")}
ckpt:
  action_following: {q(weights / "clip_model/ViT-B-32.pt")}
  semantic_alignment:
    caption: {q(weights / "Qwen2.5-VL-7B-Instruct")}
    CLIP: {q(weights / "clip-vit-base-patch16")}
  depth_accuracy: {q(weights / "depth-anything")}
  aesthetic_quality:
    clip: {q(weights / "clip_model/ViT-L-14.pt")}
    aesthetic_head: {q(weights / "aesthetic_model/emb_reader/sa_0_4_vit_l_14_linear.pth")}
  background_consistency:
    clip: {q(weights / "clip_model/ViT-B-32.pt")}
    raft: {q(weights / "raft_model/models/raft-things.pth")}
  dynamic_degree:
    raft: {q(weights / "raft_model/models/raft-things.pth")}
  flow_score:
    raft: {q(weights / "raft_model/models/raft-things.pth")}
  photometric_smoothness:
    cfg: {q(repo / "video_quality/WorldArena/third_party/SEA-RAFT/config/eval/spring-M.json")}
    model: {q(weights / "sea_raft/Tartan-C-T-TSKH-spring540x960-M.pth")}
  motion_smoothness:
    model: {q(weights / "vfimamba/model.pkl")}
  image_quality:
    musiq: {q(weights / "pyiqa_model/musiq_spaq_ckpt-358bb6af.pth")}
  subject_consistency:
    repo: {q(weights / "dino_model/facebookresearch_dino_main")}
    weight: {q(weights / "dino_model/dino_vitbase16_pretrain.pth")}
    model: dino_vitb16
    raft: {q(weights / "raft_model/models/raft-things.pth")}
  sam3_model_ckpt: {q(weights / "sam")}
  vlm_model: {q(weights / "qwenvl3")}
'''


def write_config(repo: Path, weights: Path, execute: bool) -> Path:
    path = repo / "video_quality/config/config.autogen.yaml"
    if execute:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config_text(repo, weights), encoding="utf-8")
    return path


def infer_summary(video_dir: Path | None, repo: Path) -> Path | None:
    candidates = []
    if video_dir:
        candidates.extend([video_dir / "summary.json", video_dir.parent / "summary.json"])
    candidates.extend([repo / "summary.json", Path.cwd() / "summary.json"])
    return next((path.resolve() for path in candidates if path.exists()), None)


def intake(args: argparse.Namespace) -> dict:
    repo = args.repo.expanduser().resolve()
    video_dir = Path(args.video_dir).expanduser().resolve() if args.video_dir else None
    summary = Path(args.summary_json).expanduser().resolve() if args.summary_json else infer_summary(video_dir, repo)
    metrics = expand_metrics(args.metrics)
    model_name = args.model_name or (video_dir.name if video_dir else None)
    missing = []
    if not repo.exists():
        missing.append("repo")
    if not video_dir or not video_dir.exists():
        missing.append("video_dir")
    if not summary or not summary.exists():
        missing.append("summary_json")
    if not metrics:
        missing.append("metrics")
    if not args.weights_dir:
        missing.append("weights_dir")
    return {
        "status": "needs_input" if missing else "ready",
        "missing": missing,
        "inferred": {
            "repo": str(repo),
            "video_dir": str(video_dir) if video_dir else None,
            "summary_json": str(summary) if summary else None,
            "model_name": model_name,
            "metrics": metrics,
        },
        "recommended": {
            "metrics": "core",
            "weights_dir": str(repo / "models"),
        },
        "questions": {
            "video_dir": "Where is the flat directory containing generated mp4 videos?",
            "summary_json": "Where is the WorldArena summary.json?",
            "metrics": "Run core, full, or which explicit metrics?",
            "weights_dir": f"Where should checkpoints be downloaded? Recommended: {repo / 'models'}",
        },
    }


def action_variant_issues(video_dir: Path) -> list[str]:
    name = video_dir.name
    if "_test" not in name:
        return [f"action_following requires a base directory name containing _test: {video_dir}"]
    siblings = [
        video_dir.with_name(name.replace("_test", "_test_1", 1)),
        video_dir.with_name(name.replace("_test", "_test_2", 1)),
    ]
    return [f"missing action-following variant directory: {path}" for path in siblings if not path.exists()]


def stage_gt(summary: Path, generated: Path, destination: Path, execute: bool) -> tuple[Path, list[str]]:
    data = json.loads(summary.read_text(encoding="utf-8"))
    issues: list[str] = []
    if execute:
        destination.mkdir(parents=True, exist_ok=True)
    for item in data:
        gt = Path(item.get("gt_path", ""))
        if not gt.exists():
            issues.append(f"missing GT video: {gt}")
            continue
        stem = gt.stem
        parts = gt.parts
        names = [gt.name]
        if len(parts) >= 5:
            names.insert(0, f"{parts[-5]}_{stem}.mp4")
        name = next((candidate for candidate in names if (generated / candidate).exists()), names[0])
        target = destination / name
        if execute and not target.exists():
            target.symlink_to(gt.resolve())
    return destination, issues


def evaluation_commands(repo: Path, model: str, videos: Path, summary: Path, metrics: list[str], config: Path, gt_stage: Path) -> list[tuple[str, Path, list[str]]]:
    families, standard, action, vlm, jepa = required_families(metrics)
    del families
    vq = repo / "video_quality"
    commands: list[tuple[str, Path, list[str]]] = []
    if standard:
        commands.append(("standard", vq, ["bash", "run_evaluation.sh", model, str(videos), str(summary), ",".join(standard), str(config)]))
    if action:
        commands.append(("action_following", vq, ["bash", "run_action_following.sh", model, str(videos), str(summary), str(config)]))
    if vlm:
        commands.append(("vlm", vq, ["bash", "run_VLM_judge.sh", model, str(videos), str(summary), "all", str(config)]))
    if jepa:
        conda = conda_executable()
        if not conda:
            raise RuntimeError("conda was not found")
        commands.append(("jepa", vq / "JEDi", [conda, "run", "-n", "WorldArena_JEPA", "python", "batch.py", "--real_dir", str(gt_stage), "--gen_dir", str(videos), "--output_root", str(vq / "output_JEDi")]))
    commands.append(("aggregate", repo, [sys.executable, "video_quality/csv_results/aggregate_results.py", "--model_name", model, "--base_dir", "video_quality", "--csv_name", "aggregated_results.csv"]))
    return commands


def setup(args: argparse.Namespace, execute: bool) -> dict:
    repo = args.repo.expanduser().resolve()
    weights = args.weights_dir.expanduser().resolve()
    metrics = expand_metrics(args.metrics)
    if not metrics:
        raise RuntimeError("--metrics is required; use core, full, or an explicit list")
    families, standard, action, vlm, jepa = required_families(metrics)
    log_path = repo / ".worldarena_auto/logs/setup.log"
    log = None
    if execute:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("a", encoding="utf-8")
    try:
        env_actions = ensure_envs(repo, families, execute, log)
        if "base" in families:
            download_env = "WorldArena"
        elif "vlm" in families:
            download_env = "WorldArena_VLM"
        elif "jepa" in families:
            download_env = "WorldArena_JEPA"
        else:
            raise RuntimeError("no supported metric family was selected")
        keys = required_weight_keys(standard, action, vlm, jepa)
        weight_actions = ensure_weights(repo, weights, keys, download_env, execute, log)
        config = write_config(repo, weights, execute)
    finally:
        if log:
            log.close()
    return {
        "execute": execute,
        "metrics": metrics,
        "families": sorted(families),
        "environment_actions": env_actions,
        "weight_actions": weight_actions,
        "config": str(config),
        "log": str(log_path),
    }


def auto(args: argparse.Namespace) -> dict:
    repo = args.repo.expanduser().resolve()
    videos = args.video_dir.expanduser().resolve()
    summary = args.summary_json.expanduser().resolve()
    weights = args.weights_dir.expanduser().resolve()
    metrics = expand_metrics(args.metrics)
    model = args.model_name or videos.name
    if not repo.exists() or not videos.exists() or not summary.exists():
        raise RuntimeError("repo, video_dir, and summary_json must exist before auto execution")
    summary_issues = check_summary(summary)
    if summary_issues:
        raise RuntimeError("; ".join(summary_issues))
    _, _, action, _, jepa = required_families(metrics)
    if action:
        issues = action_variant_issues(videos)
        if issues:
            raise RuntimeError("; ".join(issues))
    setup_report = setup(args, args.execute)
    config = Path(setup_report["config"])
    gt_stage = repo / "video_quality/.worldarena_auto/gt_videos"
    gt_issues: list[str] = []
    if jepa:
        gt_stage, gt_issues = stage_gt(summary, videos, gt_stage, args.execute)
    commands = evaluation_commands(repo, model, videos, summary, metrics, config, gt_stage)
    run_log = repo / ".worldarena_auto/logs/evaluation.log"
    completed: list[str] = []
    failures: list[str] = []
    if args.execute:
        run_log.parent.mkdir(parents=True, exist_ok=True)
        with run_log.open("a", encoding="utf-8") as log:
            for name, cwd, command in commands:
                try:
                    run(command, cwd=cwd, log=log)
                    completed.append(name)
                except Exception as exc:
                    failures.append(f"{name}: {exc}")
                    if not args.continue_on_error:
                        break
    return {
        "execute": args.execute,
        "setup": setup_report,
        "model_name": model,
        "gt_stage": str(gt_stage),
        "gt_issues": gt_issues,
        "commands": [
            {"name": name, "cwd": str(cwd), "command": " ".join(shlex.quote(x) for x in command)}
            for name, cwd, command in commands
        ],
        "completed": completed,
        "failures": failures,
        "run_log": str(run_log),
        "expected_outputs": [
            str(repo / "video_quality/output"),
            str(repo / "video_quality/output_action_following"),
            str(repo / "video_quality/output_VLM" / model),
            str(repo / "video_quality/output_JEDi/results.json"),
            str(repo / "video_quality/csv_results/aggregated_results.csv"),
        ],
    }


def emit(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous WorldArena bootstrap and evaluation controller")
    sub = parser.add_subparsers(dest="command", required=True)

    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    intake_parser.add_argument("--video-dir")
    intake_parser.add_argument("--summary-json")
    intake_parser.add_argument("--metrics")
    intake_parser.add_argument("--model-name")
    intake_parser.add_argument("--weights-dir")

    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    setup_parser.add_argument("--metrics", required=True)
    setup_parser.add_argument("--weights-dir", type=Path, required=True)
    setup_parser.add_argument("--execute", action="store_true")

    auto_parser = sub.add_parser("auto")
    auto_parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    auto_parser.add_argument("--video-dir", type=Path, required=True)
    auto_parser.add_argument("--summary-json", type=Path, required=True)
    auto_parser.add_argument("--metrics", required=True)
    auto_parser.add_argument("--weights-dir", type=Path, required=True)
    auto_parser.add_argument("--model-name")
    auto_parser.add_argument("--execute", action="store_true")
    auto_parser.add_argument("--continue-on-error", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "intake":
            emit(intake(args))
        elif args.command == "setup":
            emit(setup(args, args.execute))
        elif args.command == "auto":
            emit(auto(args))
    except Exception as exc:
        emit({"status": "error", "error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
