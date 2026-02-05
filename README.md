# Prompt Management Prototype

Jinja2-based prompt templating with variable inheritance and live preview.

## Setup

```bash
uv sync
```

## Usage

```bash
# Watch specific templates (recommended)
uv run render.py intent_planner --watch
uv run render.py intent_planner llm_prompt --watch

# Render once
uv run render.py intent_planner
uv run render.py intent_planner:default  # specific variant

# List all templates
uv run render.py --list
```

## How it works

```
templates/intent_planner.jinja2    # Jinja2 template
variables/intent_planner/
  default.json                     # Base variables
  image_generation.json            # Variant (overrides default)

rendered/intent_planner/           # Output (gitignored)
  default.md
  image_generation.md
```

Watch mode auto-renders on save and shows diffs in terminal.
