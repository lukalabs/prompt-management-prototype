# Prompt Management Prototype

Jinja2-based prompt templating with variable inheritance and live preview.

## Setup

```bash
uv sync
```

## Folder Structure

```
prompts/
├── templates/              # Jinja2 templates
│   └── intent_planner.jinja2
├── variables/
│   └── intent_planner/
│       ├── default.json        # Base variables
│       └── picture_present.json  # Override variant
├── rendered/               # Auto-generated output (gitignored)
│   └── intent_planner/
│       ├── default.md
│       └── picture_present.md
└── render.py
```

## Usage

```bash
uv run render.py --list                         # List templates/variants
uv run render.py                                # Render all
uv run render.py intent_planner                 # Render one template (all variants)
uv run render.py intent_planner:picture_present # Render specific variant
uv run render.py intent_planner --watch         # Watch mode (recommended for 1-2 templates)
```

## Features

- **Variable inheritance**: `default.json` merged with variant overrides
- **Watch mode**: Auto-re-render on file changes with colorized terminal diffs
- **Error handling**: Errors written inline to `.md` files
- **Diff support**: Auto `.old` files for comparing changes
