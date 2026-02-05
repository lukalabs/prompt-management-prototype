#!/usr/bin/env python3
"""
Auto-render Jinja2 templates with watch mode support.

Usage:
    uv run render.py                    # Render all templates
    uv run render.py --watch            # Watch mode with auto-re-render
    uv run render.py --list             # List all templates and variants
    uv run render.py intent_planner     # Render specific template (all variants)
    uv run render.py intent_planner:default  # Render specific variant
"""

import argparse
import difflib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError, UndefinedError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Paths
ROOT = Path(__file__).parent
TEMPLATES_DIR = ROOT / "templates"
VARIABLES_DIR = ROOT / "variables"
RENDERED_DIR = ROOT / "rendered"


class TemplateRenderer:
    """Discovers and renders Jinja2 templates with variable inheritance."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            keep_trailing_newline=True,
        )

    def discover_templates(self) -> dict[str, list[str]]:
        """
        Discover all templates and their variants.
        Returns: {template_name: [variant1, variant2, ...]}
        """
        templates = {}
        for var_dir in VARIABLES_DIR.iterdir():
            if var_dir.is_dir():
                template_name = var_dir.name
                template_file = TEMPLATES_DIR / f"{template_name}.jinja2"
                if template_file.exists():
                    variants = []
                    for json_file in sorted(var_dir.glob("*.json")):
                        variants.append(json_file.stem)
                    if variants:
                        templates[template_name] = variants
        return templates

    def load_variables(self, template_name: str, variant: str) -> dict:
        """
        Load variables with inheritance: default.json first, then variant overrides.
        """
        var_dir = VARIABLES_DIR / template_name
        variables = {}

        # Load default.json first (if exists and not the variant itself)
        default_file = var_dir / "default.json"
        if default_file.exists():
            with open(default_file) as f:
                variables = json.load(f)

        # Load variant overrides (if different from default)
        if variant != "default":
            variant_file = var_dir / f"{variant}.json"
            if variant_file.exists():
                with open(variant_file) as f:
                    overrides = json.load(f)
                    variables.update(overrides)

        return variables

    def render(self, template_name: str, variant: str) -> tuple[str, str | None]:
        """
        Render a template with given variant.
        Returns: (rendered_content, error_message)
        """
        try:
            template = self.env.get_template(f"{template_name}.jinja2")
            variables = self.load_variables(template_name, variant)
            content = template.render(**variables)
            return content, None
        except UndefinedError as e:
            return "", f"Undefined variable: {e}"
        except TemplateError as e:
            return "", f"Template error: {e}"
        except json.JSONDecodeError as e:
            return "", f"JSON parse error: {e}"
        except Exception as e:
            return "", f"Error: {e}"

    def render_error_content(
        self, template_name: str, variant: str, error: str
    ) -> str:
        """Generate error markdown for failed renders."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""<!-- RENDER ERROR: {template_name}/{variant} -->
<!-- Time: {timestamp} -->

**Error:** {error}

<!-- Auto-updates when fixed -->
"""


class DiffManager:
    """Manages .old files and shows diffs in terminal."""

    @staticmethod
    def save_old_if_changed(output_path: Path, new_content: str) -> bool:
        """
        Save current content to .old file if content changed.
        Returns True if content changed.
        """
        if not output_path.exists():
            return True

        old_content = output_path.read_text()
        if old_content == new_content:
            return False

        # Save to .old file
        old_path = output_path.with_suffix(".old.md")
        old_path.write_text(old_content)
        return True

    @staticmethod
    def show_diff(output_path: Path, old_content: str, new_content: str):
        """Show colorized diff in terminal."""
        if old_content == new_content:
            return

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"{output_path.name} (old)",
                tofile=f"{output_path.name} (new)",
                lineterm="",
            )
        )

        if not diff:
            return

        # Color codes
        RED = "\033[91m"
        GREEN = "\033[92m"
        CYAN = "\033[96m"
        RESET = "\033[0m"

        for line in diff[:50]:  # Limit diff output
            line = line.rstrip("\n")
            if line.startswith("---") or line.startswith("+++"):
                print(f"{CYAN}{line}{RESET}")
            elif line.startswith("-"):
                print(f"{RED}{line}{RESET}")
            elif line.startswith("+"):
                print(f"{GREEN}{line}{RESET}")
            else:
                print(line)

        if len(diff) > 50:
            print(f"... ({len(diff) - 50} more lines)")


class RenderEngine:
    """Main rendering engine that coordinates rendering and output."""

    def __init__(self, verbose: bool = True):
        self.renderer = TemplateRenderer()
        self.diff_manager = DiffManager()
        self.verbose = verbose

    def ensure_output_dir(self, template_name: str):
        """Ensure output directory exists."""
        output_dir = RENDERED_DIR / template_name
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def render_one(
        self, template_name: str, variant: str, show_diff: bool = False
    ) -> bool:
        """
        Render a single template/variant combination.
        Returns True if successful.
        """
        output_dir = self.ensure_output_dir(template_name)
        output_path = output_dir / f"{variant}.md"

        # Get old content for diff
        old_content = output_path.read_text() if output_path.exists() else ""

        # Render
        content, error = self.renderer.render(template_name, variant)

        if error:
            content = self.renderer.render_error_content(template_name, variant, error)
            status = "error"
        else:
            status = "ok"

        # Check if changed and save .old
        changed = self.diff_manager.save_old_if_changed(output_path, content)

        # Write new content
        output_path.write_text(content)

        # Output
        if self.verbose:
            change_indicator = " (changed)" if changed else " (unchanged)"
            status_icon = "\033[91m\u2717\033[0m" if error else "\033[92m\u2713\033[0m"
            print(f"  {status_icon} {template_name}/{variant}.md{change_indicator}", flush=True)

            if show_diff and changed:
                self.diff_manager.show_diff(output_path, old_content, content)

        return error is None

    def render_all(self, show_diff: bool = False) -> bool:
        """Render all discovered templates. Returns True if all successful."""
        templates = self.renderer.discover_templates()
        if not templates:
            print("No templates found. Create variables/<name>/*.json files.")
            return False

        all_ok = True
        for template_name, variants in sorted(templates.items()):
            if self.verbose:
                print(f"\n{template_name}:")
            for variant in variants:
                if not self.render_one(template_name, variant, show_diff):
                    all_ok = False

        return all_ok

    def render_template(
        self, template_name: str, variant: str | None = None, show_diff: bool = False
    ) -> bool:
        """Render specific template (optionally specific variant)."""
        templates = self.renderer.discover_templates()

        if template_name not in templates:
            print(f"Template '{template_name}' not found.")
            print(f"Available: {', '.join(templates.keys())}")
            return False

        variants = [variant] if variant else templates[template_name]

        if self.verbose:
            print(f"\n{template_name}:")

        all_ok = True
        for v in variants:
            if v not in templates[template_name]:
                print(f"  Variant '{v}' not found for {template_name}")
                all_ok = False
                continue
            if not self.render_one(template_name, v, show_diff):
                all_ok = False

        return all_ok


class WatchHandler(FileSystemEventHandler):
    """Handles file system events for watch mode."""

    def __init__(self, engine: RenderEngine):
        self.engine = engine
        self.last_event_time = 0
        self.debounce_seconds = 0.5

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_change(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_change(event.src_path)

    def _handle_change(self, path: str):
        # Debounce rapid events
        now = time.time()
        if now - self.last_event_time < self.debounce_seconds:
            return
        self.last_event_time = now

        path = Path(path)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Determine what changed and re-render appropriately
        if path.suffix == ".jinja2" and TEMPLATES_DIR in path.parents or path.parent == TEMPLATES_DIR:
            template_name = path.stem
            print(f"\n[{timestamp}] {path.name} changed", flush=True)
            self.engine.render_template(template_name, show_diff=True)
            sys.stdout.flush()

        elif path.suffix == ".json" and VARIABLES_DIR in path.parents:
            # Variable file changed - find template name from parent dir
            template_name = path.parent.name
            variant = path.stem
            print(f"\n[{timestamp}] {template_name}/{path.name} changed", flush=True)
            self.engine.render_one(template_name, variant, show_diff=True)
            sys.stdout.flush()


def list_templates():
    """List all templates and variants."""
    renderer = TemplateRenderer()
    templates = renderer.discover_templates()

    if not templates:
        print("No templates found.")
        print("\nTo add a template:")
        print("  1. Create templates/<name>.jinja2")
        print("  2. Create variables/<name>/default.json")
        return

    print("Available templates:\n")
    for template_name, variants in sorted(templates.items()):
        print(f"  {template_name}:")
        for variant in variants:
            print(f"    - {variant}")


def watch_mode(engine: RenderEngine):
    """Start watch mode."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Watching templates/ and variables/", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    # Initial render
    engine.render_all()

    handler = WatchHandler(engine)
    observer = Observer()
    observer.schedule(handler, str(TEMPLATES_DIR), recursive=True)
    observer.schedule(handler, str(VARIABLES_DIR), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped watching.")
    observer.join()


def main():
    parser = argparse.ArgumentParser(
        description="Render Jinja2 templates with variable inheritance."
    )
    parser.add_argument("target", nargs="?", help="template[:variant] to render")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch mode")
    parser.add_argument("--list", "-l", action="store_true", help="List templates")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    if args.list:
        list_templates()
        return

    engine = RenderEngine(verbose=not args.quiet)

    if args.watch:
        watch_mode(engine)
        return

    if args.target:
        # Parse template:variant
        if ":" in args.target:
            template_name, variant = args.target.split(":", 1)
        else:
            template_name, variant = args.target, None

        success = engine.render_template(template_name, variant, show_diff=True)
    else:
        success = engine.render_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
