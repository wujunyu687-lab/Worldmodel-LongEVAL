# WorldArena Pipeline Reference

This reference is for operating Track 1 evaluation in `/mnt/cfs/e71s16/wjy/WorldArena` and similar checkouts.

## Input Contract

Standard pipeline scripts expect:

- `MODEL_NAME`: output/model label, for example `my_model`.
- `GEN_VIDEO_DIR`: flat directory of generated videos. The scripts expect top-level `.mp4` files and no nested video folders.
- `SUMMARY_JSON`: JSON list with entries containing at least `gt_path`, `image`, and `prompt`.
- `video_quality/config/config.yaml`: absolute paths for data roots, output roots, and checkpoints.

Official naming rule from repo docs:

```text
generated video dir: modelname_test
video files: {taskname}_episode_{xx}.mp4
```

## Metric Families

### Standard Metrics

Run with:

```bash
cd <repo>/video_quality
bash run_evaluation.sh <MODEL_NAME> <GEN_VIDEO_DIR> <SUMMARY_JSON> "<METRIC_LIST>" [CONFIG_PATH]
```

The script:

1. activates conda env `WorldArena`
2. runs `preprocess_datasets.py`
3. runs `processing/video_resize.py`
4. runs `processing/detection_tracking.py --detect_gt`
5. runs `evaluate.py --dimension ... --overwrite`

Use this for:

```text
trajectory_accuracy, semantic_alignment, depth_accuracy,
aesthetic_quality, background_consistency, dynamic_degree,
flow_score, photometric_smoothness, motion_smoothness,
image_quality, subject_consistency, psnr, ssim
```

### Action Following

Run separately:

```bash
cd <repo>/video_quality
bash run_action_following.sh <MODEL_NAME> <GEN_VIDEO_DIR> <SUMMARY_JSON> [CONFIG_PATH]
```

The script:

1. activates conda env `WorldArena`
2. runs `preprocess_datasets_diversity.py`
3. runs `evaluate.py --dimension action_following --overwrite`

It requires action-following style generated variants. The docs mention directories such as `modelname_test`, `modelname_test_1`, `modelname_test_2`; inspect current script and data layout before assuming one flat directory is enough.

### VLM Metrics

Run with:

```bash
cd <repo>/video_quality
bash run_VLM_judge.sh <MODEL_NAME> <VIDEO_DIR> <SUMMARY_JSON> [METRICS] [CONFIG_PATH]
```

The script activates `WorldArena_VLM` and evaluates all three VLM metrics:

- Interaction Quality
- Perspectivity
- Instruction Following

It loads `ckpt.vlm_model` from config unless overridden in code.

### JEPA/JEDi

Run with:

```bash
cd <repo>/video_quality
bash run_evaluation_JEPA.sh <GEN_VIDEO_DIR>
```

Before running, check `run_evaluation_JEPA.sh`; this checkout may contain `REAL_DIR_TO_GT` placeholder. Replace or patch it, or run `JEDi/batch.py` directly:

```bash
cd <repo>/video_quality/JEDi
python batch.py \
  --real_dir /path/to/gt_mp4_dir \
  --gen_dir /path/to/generated_mp4_dir \
  --output_root <repo>/video_quality/output_JEDi
```

### CSV Aggregation

Run after individual metrics finish:

```bash
cd <repo>
python video_quality/csv_results/aggregate_results.py \
  --model_name <MODEL_NAME> \
  --base_dir video_quality \
  --csv_name aggregated_results.csv
```

Check the `Photometric Consistency` column. In this checkout the evaluator key is `photometric_smoothness`, but the aggregator maps `photometric_consistency`.

## Preflight Checklist

Run:

```bash
python ~/.codex/skills/worldarena-eval/scripts/worldarena_pipeline.py preflight \
  --repo <repo> \
  --video-dir <GEN_VIDEO_DIR> \
  --summary-json <SUMMARY_JSON>
```

Then verify manually if needed:

```bash
conda env list | rg 'WorldArena|WorldArena_VLM|WorldArena_JEPA'
python -m json.tool <SUMMARY_JSON> >/dev/null
find <GEN_VIDEO_DIR> -maxdepth 1 -type f -name '*.mp4' | head
rg -n 'your absolute path|REAL_DIR_TO_GT' <repo>/video_quality
```

## Output Locations

- Standard metrics: `<repo>/video_quality/output/*_results.json`
- Action following: `<repo>/video_quality/output_action_following/*_results.json`
- VLM: `<repo>/video_quality/output_VLM/<MODEL_NAME>/*.json`
- JEPA: `<repo>/video_quality/output_JEDi/results.json`
- CSV: `<repo>/video_quality/csv_results/*.csv`

## Reporting

Report:

- commands run
- output files created
- metrics completed
- metrics skipped and why
- placeholder/config/env blockers
- whether results are raw or normalized

Do not say the model improved or is high-quality unless the metric values and comparison baseline prove it.

