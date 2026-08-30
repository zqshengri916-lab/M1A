---
name: MAA
description: 用于MAA项目的skill
---

# MaaFramework Skills

Claude Code skills for building automation pipelines with [MaaFramework](https://github.com/MaaXYZ/MaaFramework) — JSON-based task pipelines with image/OCR recognition, multi-platform input control, and custom logic via Python/NodeJS agents.

## What's Included

This skill provides structured reference documentation covering:

- **Pipeline Protocol** — Node lifecycle, execution flow, v1/v2 formats
- **Recognition Algorithms** — TemplateMatch, OCR, FeatureMatch, ColorMatch, NeuralNetwork
- **Action Types** — Click, Swipe, Scroll, key input, Shell, Command, app control
- **Integration** — Python/NodeJS bindings, Tasker/Resource/Controller setup
- **Project Interface** — `interface.json` tasks, controllers, resources, options, presets
- **Custom Logic** — Agent process, Python/NodeJS custom recognition and actions
- **Troubleshooting** — Debug options, log files, common issues

## Installation

```bash
# Install via Claude Code
claude skills add ./skills/maaframework
```

## Project Structure

```
skills/
└── maaframework/
    ├── SKILL.md              # Skill definition
    ├── docs/                 # Source documentation (zh_cn / en_us)
    │   ├── zh_cn/
    │   └── en_us/
    └── references/           # Processed reference docs for Claude
        ├── core-*.md
        └── advanced-*.md
```

## Source

Generated from [MaaFramework](https://github.com/MaaXYZ/MaaFramework) documentation (v5.x), 2026-04-16.

## License

See the [MaaFramework license](https://github.com/MaaXYZ/MaaFramework) for the original documentation.