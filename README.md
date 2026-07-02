# Worldmodel-LongEVAL

Utilities for long-horizon world-model evaluation workflows.

## Codex Skill: `worldarena-eval`

This repository currently includes a Codex skill for operating the WorldArena
evaluation pipeline:

```text
skills/worldarena-eval/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── metrics.md
│   └── pipeline.md
└── scripts/
    ├── worldarena_pipeline.py
    └── worldarena_probe.py
```

### Install

Copy or symlink the skill into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -a skills/worldarena-eval ~/.codex/skills/
```

### Use

Ask Codex to use the skill:

```text
Use $worldarena-eval to preflight my WorldArena generated videos and summary.json.
```

Generate a WorldArena pipeline plan directly:

```bash
~/.codex/skills/worldarena-eval/scripts/worldarena_pipeline.py plan \
  --repo /mnt/cfs/e71s16/wjy/WorldArena \
  --model-name my_model \
  --video-dir /path/to/generated_videos \
  --summary-json /path/to/summary.json \
  --metrics "image_quality,subject_consistency,action_following,vlm,jepa"
```

Run a preflight check:

```bash
~/.codex/skills/worldarena-eval/scripts/worldarena_pipeline.py preflight \
  --repo /mnt/cfs/e71s16/wjy/WorldArena \
  --video-dir /path/to/generated_videos \
  --summary-json /path/to/summary.json
```
