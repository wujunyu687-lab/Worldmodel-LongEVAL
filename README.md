Utilities for long-horizon world-model evaluation workflows.

## Codex Skill: `worldarena-eval`

This repository currently includes a Codex skill for operating the WorldArena
evaluation pipeline:

```text
skills/worldarena-eval/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── bootstrap.md
│   ├── metrics.md
│   └── pipeline.md
└── scripts/
    ├── worldarena_auto.py
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

Installing the skill does not start a job by itself. Invoke it in Codex and it
will inspect the machine, ask once for unresolved inputs, install missing
environments, download only required checkpoints to your chosen directory,
generate a config, run evaluation, and collect outputs.

Recommended prompt:

```text
Use $worldarena-eval to evaluate my generated videos end to end. Ask me only for inputs you cannot infer, let me choose the checkpoint directory, then install missing environments and weights and run the evaluation automatically.
```

中文示例：

```text
使用 $worldarena-eval 全自动评测我的生成视频。先检查本机，只询问无法自动找到的输入和权重下载目录，然后自动安装缺失环境与权重、运行评测并汇总结果。
```

The first intake pass can also be run directly:

```bash
~/.codex/skills/worldarena-eval/scripts/worldarena_auto.py intake \
  --repo /path/to/WorldArena
```

After resolving the requested inputs, run the full automatic workflow:

```bash
~/.codex/skills/worldarena-eval/scripts/worldarena_auto.py auto \
  --repo /path/to/WorldArena \
  --video-dir /path/to/generated_videos \
  --summary-json /path/to/summary.json \
  --metrics core \
  --weights-dir /path/to/checkpoints \
  --execute
```
