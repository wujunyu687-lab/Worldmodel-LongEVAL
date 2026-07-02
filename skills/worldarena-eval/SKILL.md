---
name: worldarena-eval
description: Operate the WorldArena evaluation pipeline for local /mnt/cfs/e71s16/wjy/WorldArena-style checkouts. Use when Codex needs to run or prepare Track 1 video-quality evaluation, VLM judge evaluation, JEPA/JEDi evaluation, action_following preprocessing/evaluation, CSV aggregation, input preflight checks for generated videos and summary.json, config/conda/path diagnostics, or result collection from WorldArena outputs.
---

# WorldArena Eval

Use this skill to drive the WorldArena pipeline end to end. Prefer real preflight and concrete commands over generic advice. Always inspect the target checkout because local scripts and paths may be patched.

## Default Repo

Default path if the user does not provide one:

```text
/mnt/cfs/e71s16/wjy/WorldArena
```

Verify the path exists before relying on it. If the user gives another path, use that path.

## Quick Workflow

1. Locate the repo and run pipeline preflight:

```bash
python ~/.codex/skills/worldarena-eval/scripts/worldarena_pipeline.py preflight \
  --repo /mnt/cfs/e71s16/wjy/WorldArena \
  --video-dir /path/to/generated_videos \
  --summary-json /path/to/summary.json
```

2. Generate the command plan:

```bash
python ~/.codex/skills/worldarena-eval/scripts/worldarena_pipeline.py plan \
  --repo /mnt/cfs/e71s16/wjy/WorldArena \
  --model-name my_model \
  --video-dir /path/to/generated_videos \
  --summary-json /path/to/summary.json \
  --metrics "image_quality,subject_consistency,action_following,vlm,jepa"
```

3. If the user asks to run it, execute the plan commands from `video_quality/` and monitor output artifacts.

4. Separate validation boundaries in every report:

- format/preprocess success
- model/environment import success
- metric script completion
- output JSON/CSV existence
- actual quality or task-success claim

## Common Tasks

### Run Track 1 Pipeline

Treat metrics as four families:

- `standard`: evaluator metrics handled by `run_evaluation.sh`, for example `image_quality`, `subject_consistency`, `depth_accuracy`, `trajectory_accuracy`, `photometric_smoothness`, `motion_smoothness`, `psnr`, `ssim`.
- `action_following`: must run through `run_action_following.sh`, not as part of standard metrics.
- `vlm`: `Interaction Quality`, `Perspectivity`, `Instruction Following`, handled by `run_VLM_judge.sh`.
- `jepa`: handled by `run_evaluation_JEPA.sh`.

Use `worldarena_pipeline.py plan` to split mixed metric lists into the right commands. Read `references/pipeline.md` when changing or debugging the execution sequence.

Before actual execution, verify:

- `GEN_VIDEO_DIR` exists and contains mp4 files.
- `SUMMARY_JSON` exists and is valid JSON.
- `video_quality/config/config.yaml` paths are not placeholder strings.
- the required conda environment exists if the user wants actual execution.
- JEPA has a real GT mp4 directory, not `REAL_DIR_TO_GT`.

### Execute Commands

When the user asks to run evaluation, run commands from the target repo, usually:

```bash
cd /mnt/cfs/e71s16/wjy/WorldArena/video_quality
bash run_evaluation.sh ...
```

Do not report quality success just because a command launched. After each command, inspect expected output files.

### Explain Results

Inspect actual output files instead of inferring:

- standard metrics: `video_quality/output/*_results.json`
- action following: `video_quality/output_action_following/*_results.json`
- VLM: `video_quality/output_VLM/<model>/*.json`
- JEPA: `video_quality/output_JEDi/results.json`
- CSV: `video_quality/csv_results/*.csv`

Explain raw-vs-normalized fields carefully. Some metrics store `[aggregate, per_video_list]`; per-video entries may include `video_results_normalized`.

### Explain Available Metrics

For metric meaning questions, first inspect current support with:

```bash
python ~/.codex/skills/worldarena-eval/scripts/worldarena_probe.py --repo <repo>
```

Then read `references/metrics.md`.

### Diagnose Metric Gaps

Known in this checkout:

- FID/FVD are not wired into the main evaluator.
- `Photometric Consistency` in the CSV corresponds to code metric `photometric_smoothness`, but the aggregator maps `photometric_consistency`; check or patch before trusting that CSV column.
- `run_evaluation_JEPA.sh` contains a placeholder GT real directory unless locally edited.
- `Dynamic Degree` and `Flow Score` measure motion amount, not unconditional quality.
- `Depth Accuracy` raw value is AbsRel error; normalized score is inverted so higher is better.

## References

- Read `references/pipeline.md` when the user wants to use the pipeline, run evaluation, prepare commands, fix input/config, or collect outputs.
- Read `references/metrics.md` when the user asks what metrics mean, which metric maps to long-term consistency/stability, or whether FID/FVD is missing.
