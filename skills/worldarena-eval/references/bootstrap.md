# Autonomous Bootstrap

Use this reference when Codex must install and run WorldArena rather than only explain it.

## Intake Contract

Collect or infer these values:

- WorldArena repository path
- flat generated-video directory containing `.mp4`
- valid `summary.json` containing `gt_path`, `image`, and `prompt`
- metric profile or explicit metric list
- model name, normally inferred from the video directory name
- checkpoint root selected by the user; recommend `<repo>/models`

For JEPA, derive a flat GT video staging directory from `summary.json`. Ask for a separate GT directory only when the listed `gt_path` files do not exist.

For `action_following`, verify sibling directories ending in `_test_1` and `_test_2`; ask for missing variants because they cannot be invented from a single generated video set.

## Profiles

- `core`: image quality, subject/background consistency, dynamics, flow, photometric and motion smoothness, depth, trajectory, VLM, and JEPA.
- `full`: all registered standard metrics plus action following, VLM, and JEPA. Action-following variants remain mandatory.
- explicit list: install and download only what those metrics require.

## Environment Policy

Use the repository's three isolated environments:

- `WorldArena`: standard metrics and action following
- `WorldArena_VLM`: VLM judge
- `WorldArena_JEPA`: JEPA/JEDi

Do not remove or recreate an existing environment by default. Smoke-test it. Repair it only when imports fail. Keep proxy changes per-command and do not edit shell startup files.

## Checkpoint Policy

Download checkpoints selectively into the user-selected checkpoint root. Reuse completed files and Hugging Face snapshots. The autonomous script covers:

- CLIP ViT-B/32 and ViT-L/14
- Qwen2.5-VL caption model and CLIP text model
- Depth Anything V2 Small
- LAION aesthetic head
- RAFT
- SEA-RAFT checkpoint conversion from safetensors to a PyTorch checkpoint
- VFIMamba
- MUSIQ
- DINO source and checkpoint
- SAM3 and its BPE vocabulary
- Qwen3-VL judge model
- V-JEPA/JEDi checkpoints

If an upstream URL has changed, inspect the repository's current config comments and the upstream model listing, update the local download plan, and continue. Do not pretend a missing checkpoint was installed.

## Generated Config

Write a separate config at:

```text
<repo>/video_quality/config/config.autogen.yaml
```

Point data/output paths into the current repository and checkpoint paths into the selected checkpoint root. Do not overwrite `config.yaml`.

## Execution Boundary

`worldarena_auto.py auto --execute` performs setup, config generation, evaluation, and aggregation. A successful environment install is not an evaluation success. Verify expected JSON/CSV outputs and report failed metric families separately.

