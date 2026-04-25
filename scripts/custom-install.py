#!/usr/bin/env python3
"""Install a filtered Claude Code Toolkit profile.

This installer is intentionally separate from install.sh so a fork can keep
upstream behavior intact while deploying a smaller personal subset.
"""

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = REPO_ROOT / "install-profiles" / "default"
COMPONENT_DIRS = ("agents", "skills", "hooks", "commands", "scripts")


def read_name_file(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        names.add(line)
    return names


def ensure_real_dir(path: Path, dry_run: bool = False) -> None:
    if path.is_symlink() or path.is_file():
        if dry_run:
            print(f"Would replace {path} with a real directory")
            return
        path.unlink()
    if dry_run:
        print(f"Would create directory {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)


def remove_path(path: Path, dry_run: bool = False) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if dry_run:
        print(f"Would remove {path}")
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_entry(source: Path, target: Path, dry_run: bool = False) -> None:
    if dry_run:
        print(f"Would copy {source} -> {target}")
        return
    if source.is_file() and target.exists() and target.is_file() and filecmp.cmp(source, target, shallow=False):
        return
    remove_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any], dry_run: bool = False) -> None:
    if dry_run:
        print(f"Would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def filter_skills_index(disabled_skills: set[str]) -> tuple[dict[str, Any], set[str], set[str]]:
    index = load_json(REPO_ROOT / "skills" / "INDEX.json")
    source_names = set(index.get("skills", {}))
    enabled = source_names - disabled_skills
    index["skills"] = {name: entry for name, entry in index.get("skills", {}).items() if name in enabled}
    index["generated_by"] = "scripts/custom-install.py"
    index["profile_filtered_at"] = datetime.now().isoformat(timespec="seconds")
    return index, source_names, enabled


def filter_agents_index(
    disabled_agents: set[str], enabled_skills: set[str]
) -> tuple[dict[str, Any], set[str], set[str]]:
    index = load_json(REPO_ROOT / "agents" / "INDEX.json")
    source_names = set(index.get("agents", {}))
    enabled_agents = source_names - disabled_agents
    allowed_pairs = enabled_agents | enabled_skills
    filtered_agents: dict[str, Any] = {}
    for name, entry in index.get("agents", {}).items():
        if name not in enabled_agents:
            continue
        entry = dict(entry)
        if "pairs_with" in entry:
            entry["pairs_with"] = [pair for pair in entry["pairs_with"] if pair in allowed_pairs]
        filtered_agents[name] = entry
    index["agents"] = filtered_agents
    index["generated_by"] = "scripts/custom-install.py"
    index["profile_filtered_at"] = datetime.now().isoformat(timespec="seconds")
    return index, source_names, enabled_agents


def sync_skills(
    dest: Path,
    disabled_skills: set[str],
    index: dict[str, Any],
    source_names: set[str],
    enabled: set[str],
    dry_run: bool,
) -> None:
    ensure_real_dir(dest, dry_run)
    for name in sorted(source_names):
        target = dest / name
        if name not in enabled:
            remove_path(target, dry_run)
            continue
        copy_entry(REPO_ROOT / "skills" / name, target, dry_run)
    write_json(dest / "INDEX.json", index, dry_run)


def sync_agents(
    dest: Path,
    disabled_agents: set[str],
    index: dict[str, Any],
    source_names: set[str],
    enabled: set[str],
    dry_run: bool,
) -> None:
    ensure_real_dir(dest, dry_run)
    for name in sorted(source_names):
        file_target = dest / f"{name}.md"
        refs_target = dest / name
        if name not in enabled:
            remove_path(file_target, dry_run)
            remove_path(refs_target, dry_run)
            continue
        copy_entry(REPO_ROOT / "agents" / f"{name}.md", file_target, dry_run)
        refs_source = REPO_ROOT / "agents" / name
        if refs_source.exists():
            copy_entry(refs_source, refs_target, dry_run)
    write_json(dest / "INDEX.json", index, dry_run)


def sync_whole_dir(source: Path, dest: Path, excluded_names: set[str], dry_run: bool) -> None:
    ensure_real_dir(dest, dry_run)
    for item in sorted(source.iterdir()):
        if item.name in excluded_names:
            remove_path(dest / item.name, dry_run)
            continue
        copy_entry(item, dest / item.name, dry_run)


def hook_filename_from_command(command: str) -> str | None:
    marker = "/hooks/"
    if marker not in command:
        return None
    tail = command.split(marker, 1)[1]
    return tail.split('"', 1)[0].split("'", 1)[0].split()[0]


def filter_settings_hooks(settings: dict[str, Any], disabled_hooks: set[str]) -> dict[str, Any]:
    settings = dict(settings)
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings

    filtered_hooks: dict[str, Any] = {}
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            filtered_hooks[event] = groups
            continue
        filtered_groups = []
        for group in groups:
            if not isinstance(group, dict):
                filtered_groups.append(group)
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                filtered_groups.append(group)
                continue
            kept = []
            for entry in entries:
                command = entry.get("command", "") if isinstance(entry, dict) else ""
                filename = hook_filename_from_command(command)
                if filename and filename in disabled_hooks:
                    continue
                kept.append(entry)
            if kept:
                next_group = dict(group)
                next_group["hooks"] = kept
                filtered_groups.append(next_group)
        if filtered_groups:
            filtered_hooks[event] = filtered_groups

    settings["hooks"] = filtered_hooks
    return settings


def sync_claude_settings(claude_dir: Path, disabled_hooks: set[str], dry_run: bool) -> None:
    target = claude_dir / "settings.json"
    settings = load_json(REPO_ROOT / ".claude" / "settings.json")
    filtered = filter_settings_hooks(settings, disabled_hooks)
    write_json(target, filtered, dry_run)


def load_codex_hook_generator():
    path = REPO_ROOT / "scripts" / "generate-codex-hooks-json.py"
    spec = importlib.util.spec_from_file_location("generate_codex_hooks_json", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_codex_allowlist(disabled_hooks: set[str]) -> list[dict[str, Any]]:
    allowlist = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"
    lines = []
    for raw in allowlist.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(raw)
            continue
        filename = stripped.split(":", 1)[1].strip().split()[0]
        if filename in disabled_hooks:
            continue
        lines.append(raw)
    module = load_codex_hook_generator()
    return module.parse_allowlist("\n".join(lines))


def sync_codex_hooks(codex_dir: Path, disabled_hooks: set[str], dry_run: bool) -> None:
    hooks_dir = codex_dir / "hooks"
    ensure_real_dir(hooks_dir, dry_run)
    entries = parse_codex_allowlist(disabled_hooks)
    for entry in entries:
        filename = entry["filename"]
        copy_entry(REPO_ROOT / "hooks" / filename, hooks_dir / filename, dry_run)
    for filename in disabled_hooks:
        remove_path(hooks_dir / filename, dry_run)
    copy_entry(REPO_ROOT / "hooks" / "lib", hooks_dir / "lib", dry_run)

    module = load_codex_hook_generator()
    hooks_json = module.build_hooks_json(entries, codex_hooks_dir=str(hooks_dir))
    write_json(codex_dir / "hooks.json", hooks_json, dry_run)

    if not dry_run:
        config_script = REPO_ROOT / "scripts" / "ensure-codex-feature-flag.py"
        result = subprocess.run(
            [sys.executable, str(config_script), "--config", str(codex_dir / "config.toml")],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)


def write_manifest(
    home: Path,
    profile: Path,
    disabled_skills: set[str],
    disabled_agents: set[str],
    disabled_hooks: set[str],
    dry_run: bool,
) -> None:
    manifest = {
        "installer": "scripts/custom-install.py",
        "repo_root": str(REPO_ROOT),
        "profile": str(profile),
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "disabled_skills": sorted(disabled_skills),
        "disabled_agents": sorted(disabled_agents),
        "disabled_hooks": sorted(disabled_hooks),
    }
    write_json(home / ".claude" / ".custom-install-manifest.json", manifest, dry_run)


def install(profile: Path, home: Path, dry_run: bool = False) -> None:
    disabled_skills = read_name_file(profile / "disabled-skills.txt")
    disabled_agents = read_name_file(profile / "disabled-agents.txt")
    disabled_hooks = read_name_file(profile / "disabled-hooks.txt")

    claude_dir = home / ".claude"
    codex_dir = home / ".codex"
    ensure_real_dir(claude_dir, dry_run)
    ensure_real_dir(codex_dir, dry_run)

    skills_index, source_skills, enabled_skills = filter_skills_index(disabled_skills)
    agents_index, source_agents, enabled_agents = filter_agents_index(disabled_agents, enabled_skills)

    sync_skills(claude_dir / "skills", disabled_skills, skills_index, source_skills, enabled_skills, dry_run)
    sync_skills(codex_dir / "skills", disabled_skills, skills_index, source_skills, enabled_skills, dry_run)
    sync_agents(claude_dir / "agents", disabled_agents, agents_index, source_agents, enabled_agents, dry_run)
    sync_agents(codex_dir / "agents", disabled_agents, agents_index, source_agents, enabled_agents, dry_run)

    sync_whole_dir(REPO_ROOT / "hooks", claude_dir / "hooks", disabled_hooks, dry_run)
    sync_whole_dir(REPO_ROOT / "commands", claude_dir / "commands", set(), dry_run)
    sync_whole_dir(REPO_ROOT / "scripts", claude_dir / "scripts", set(), dry_run)
    sync_claude_settings(claude_dir, disabled_hooks, dry_run)
    sync_codex_hooks(codex_dir, disabled_hooks, dry_run)
    write_manifest(home, profile, disabled_skills, disabled_agents, disabled_hooks, dry_run)

    print(f"Installed filtered profile: {profile}")
    print(f"  skills: {len(enabled_skills)} enabled, {len(disabled_skills & source_skills)} disabled")
    print(f"  agents: {len(enabled_agents)} enabled, {len(disabled_agents & source_agents)} disabled")
    print(f"  hooks disabled: {len(disabled_hooks)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a filtered Claude Code Toolkit profile.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile = args.profile.resolve()
    if not profile.is_dir():
        print(f"Profile not found: {profile}", file=sys.stderr)
        return 1

    install(profile=profile, home=args.home.expanduser().resolve(), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
