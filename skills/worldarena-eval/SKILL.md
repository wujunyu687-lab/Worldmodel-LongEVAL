---
name: worldarena-eval
description: Autonomously bootstrap and operate the WorldArena evaluation pipeline for local checkouts. Use when Codex should ask for missing evaluation inputs, create or repair required conda environments, download metric-specific checkpoints to a user-selected directory, generate a working config, run Track 1 standard/VLM/JEPA/action-following evaluations, monitor outputs, aggregate CSV results, and explain failures or metrics.
---

# WorldArena Eval

Use this skill to take ownership of WorldArena evaluation end to end. Do not stop at a command plan when the user asks to evaluate. Gather missing inputs once, bootstrap dependencies, execute the pipeline, monitor it, and report real artifacts.

## Default Repo

Default path if the user does not provide one:

```text
/mnt/cfs/e71s16/wjy/WorldArena
```

Verify the path exists before relying on it. If the user gives another path, use that path.

## Autonomous Workflow

1. Run intake immediately:

```bash
python ~/.codex/skills/worldarena-eval/scripts/worldarena_auto.py intake \
  --repo /mnt/cfs/e71s16/wjy/WorldArena
```

2. Ask one concise question containing only unresolved fields. Usually these are:

- generated video directory
- `summary.json`
- metrics or profile (`core`, `full`, or a metric list)
- checkpoint download directory; recommend `<repo>/models`
- Hugging Face token only if a gated download actually rejects anonymous access

Infer `model_name` from the generated-video directory unless the user specifies one. Do not repeatedly ask for values already discoverable from disk.

3. After the user answers, run the autonomous pipeline:

```bash
python ~/.codex/skills/worldarena-eval/scripts/worldarena_auto.py auto \
  --repo /mnt/cfs/e71s16/wjy/WorldArena \
  --model-name my_model \
  --video-dir /path/to/generated_videos \
  --summary-json /path/to/summary.json \
  --metrics core \
  --weights-dir /path/to/worldarena_weights \
  --execute
```

4. Monitor long installs, downloads, preprocessing, and evaluation until they finish or reach a concrete blocker. Preserve existing environments and downloaded files; resume rather than restart.

5. Separate validation boundaries in every report:

- format/preprocess success
- model/environment import success
- metric script completion
- output JSON/CSV existence
- actual quality or task-success claim

## Common Tasks

### Bootstrap Automatically

Read `references/bootstrap.md` before environment or weight installation. Use `worldarena_auto.py setup --execute` when setup is requested separately from evaluation.

The setup must:

- create only the conda environments required by selected metric families
- reuse existing environments and weights
- download only checkpoints required by selected metrics
- write `video_quality/config/config.autogen.yaml`, leaving the repository template untouched
- smoke-test imports after installation
- ask for `HF_TOKEN` only after an authenticated download is proven necessary

### Run Track 1 Pipeline

Treat metrics as four families:

- `standard`: evaluator metrics handled by `run_evaluation.sh`, for example `image_quality`, `subject_consistency`, `depth_accuracy`, `trajectory_accuracy`, `photometric_smoothness`, `motion_smoothness`, `psnr`, `ssim`.
- `action_following`: must run through `run_action_following.sh`, not as part of standard metrics.
- `vlm`: `Interaction Quality`, `Perspectivity`, `Instruction Following`, handled by `run_VLM_judge.sh`.
- `jepa`: handled by `run_evaluation_JEPA.sh`.

Use `worldarena_auto.py auto --execute` for the normal path. Use `worldarena_pipeline.py plan` only for debugging or when the user explicitly asks for commands without execution. Read `references/pipeline.md` when changing or diagnosing the sequence.

Before actual execution, verify:

- `GEN_VIDEO_DIR` exists and contains mp4 files.
- `SUMMARY_JSON` exists and is valid JSON.
- `video_quality/config/config.yaml` paths are not placeholder strings.
- the required conda environment exists if the user wants actual execution.
- JEPA has a real GT mp4 directory, not `REAL_DIR_TO_GT`.

### Execute Commands

When the user asks to run evaluation, execute it. Do not hand back commands as the final result. The autonomous runner uses the repository scripts for standard, action-following, and VLM metrics, and directly invokes JEDi to avoid the checkout's placeholder GT path.

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

- Read `references/bootstrap.md` before intake, environment setup, checkpoint download, generated config creation, or autonomous execution.
- Read `references/pipeline.md` when the user wants to use the pipeline, run evaluation, prepare commands, fix input/config, or collect outputs.
- Read `references/metrics.md` when the user asks what metrics mean, which metric maps to long-term consistency/stability, or whether FID/FVD is missing.
