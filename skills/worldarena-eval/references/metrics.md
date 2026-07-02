# WorldArena Metrics Reference

Use this reference for `/mnt/cfs/e71s16/wjy/WorldArena` and similar checkouts. Verify against the current repo when precision matters.

## Main Code Anchors

- Track 1 entry: `video_quality/evaluate.py`
- Metric dispatcher: `video_quality/WorldArena/__init__.py`
- Submodule wiring: `video_quality/WorldArena/utils.py`
- Final CSV aggregator: `video_quality/csv_results/aggregate_results.py`
- VLM judge: `video_quality/VLM_judge.py`
- JEPA/JEDi: `video_quality/JEDi/batch.py`
- Track 2 docs: `embodied_task/worldarena_track2/docs/`

## Track 1 Metrics

| User-facing column | Code metric | Meaning | Direction |
|---|---|---|---|
| Subject Consistency | `subject_consistency` | DINO feature similarity across frames for robot/object identity stability | higher better |
| Aesthetic Quality | `aesthetic_quality` | CLIP + aesthetic head visual appeal score | higher better |
| Image Quality | `image_quality` | MUSIQ technical image quality: blur/noise/distortion | higher better |
| Background Consistency | `background_consistency` | CLIP feature stability of background across frames | higher better |
| Dynamic Degree | `dynamic_degree` | RAFT optical-flow based motion amount | higher means more motion |
| Flow Score | `flow_score` | mean RAFT optical-flow magnitude | higher means more motion |
| Photometric Consistency | `photometric_smoothness` | SEA-RAFT forward/backward flow consistency, implemented roughly as inverse EPE | higher better |
| Motion Smoothness | `motion_smoothness` | VFIMamba interpolation consistency with SSIM weighting | higher better |
| Depth Accuracy | `depth_accuracy` | Depth Anything generated-vs-GT AbsRel depth error | raw lower better, normalized higher better |
| Trajectory Accuracy | `trajectory_accuracy` | NDTW/DTW similarity between predicted and GT `traj.npy` | higher better |
| Semantic Alignment | `semantic_alignment` | Qwen-VL captions for gen/GT compared by CLIP text similarity | higher better |
| Action Following | `action_following` | CLIP feature diversity between videos generated from different actions for an episode | higher means more action-sensitive |
| Interaction Quality | VLM metric | robot-object contact and physical interaction plausibility | 1-5 then normalized, higher better |
| Perspectivity | VLM metric | 3D geometry, depth, occlusion, camera perspective consistency | 1-5 then normalized, higher better |
| Instruction Following | VLM metric | video compliance with text instruction; penalizes human-hand hallucination | 1-5 then normalized, higher better |
| JEPA Similarity | JEDi/J-EPA metric | V-JEPA/JEDi feature similarity between real and generated video sets | higher better |

Optional evaluator metrics not in the final CSV table:

- `psnr`: pixel peak signal-to-noise ratio against GT frames, higher better.
- `ssim`: structural similarity against GT frames, higher better.

## Long-Term Consistency / Stability Mapping

There is no single dedicated metric named long-term consistency. Use a bundle:

- `subject_consistency`: closest proxy for long-term robot/object identity stability.
- `background_consistency`: background stability over time.
- `perspectivity`: VLM-based 3D/perspective stability.
- `motion_smoothness` and `photometric_smoothness`: short-range temporal smoothness and flicker/flow consistency.
- `depth_accuracy` and `trajectory_accuracy`: spatial and motion alignment against GT when available.

Avoid overclaiming: these are proxy metrics, not a purpose-built long-rollout drift score.

## FID/FVD Status

In this checkout, standard FID and FVD are not wired into the WorldArena evaluator or CSV aggregation.

- FID would use image-level Inception features and Frechet distance between real and generated frame distributions.
- FVD would use video-level I3D or similar features and Frechet distance between real and generated video distributions.
- `JEPA Similarity` is a distribution/feature similarity alternative, but it is not standard FVD and should not be compared directly to FVD numbers in papers.

## Track 2 Functional Metrics

### Data Engine

Docs: `embodied_task/worldarena_track2/docs/DATA_ENGINE.md`.

WorldArena fine-tunes official pi0.5 policy on submitted generated data and evaluates in RoboTwin 2.0 clean setting. Report final success rate per task, normally 100 trials per task.

Current docs list five subtasks:

- `adjust_bottle`
- `click_bell`
- `blocks_ranking_rgb`
- `open_laptop`
- `pick_dual_bottles`

Metric:

```text
success_rate = successful_trials / total_trials
```

### Policy Evaluator

Docs/scripts:

- `embodied_task/worldarena_track2/docs/Policy_eval.md`
- `embodied_task/worldarena_track2/scripts/vlm_policy_evaluator.py`

The VLM compares GT video frames and policy/world-model rollout frames, then emits `answer: 0` or `answer: 1`.

Success criteria:

- correct left/right arm when specified
- final state similar to GT
- action intent matches instruction
- no wrong object, wrong direction, or incomplete task

Metric:

```text
vlm_success_rate = successful_videos / evaluated_videos
```

## Known Local Pitfalls

- CSV aggregator maps `photometric_consistency`, but evaluator writes `photometric_smoothness`; inspect before trusting the `Photometric Consistency` CSV column.
- `run_evaluation_JEPA.sh` may contain `REAL_DIR_TO_GT` placeholder.
- Config path values may still contain `"your absolute path"`.
- Some metrics require external checkpoints: RAFT, SEA-RAFT, VFIMamba, DINO, CLIP, MUSIQ, Depth Anything, Qwen-VL, JEDi weights.
- Do not equate successful preprocessing or JSON creation with meaningful model quality.

