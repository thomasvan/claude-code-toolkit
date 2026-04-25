import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CUSTOM_INSTALL = REPO_ROOT / "scripts" / "custom-install.py"
PROFILE = REPO_ROOT / "install-profiles" / "default"

if shutil.which("python3") is None:
    pytest.skip("python3 not available on this platform", allow_module_level=True)


def _load_custom_install_module():
    spec = importlib.util.spec_from_file_location("custom_install", CUSTOM_INSTALL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_custom_install(fake_home: Path, use_explicit_profile: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(fake_home), "TERM": "dumb"}
    args = [
        "python3",
        str(CUSTOM_INSTALL),
        "--home",
        str(fake_home),
    ]
    if use_explicit_profile:
        args.extend(["--profile", str(PROFILE)])
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_custom_install_filters_skills_agents_and_settings(fake_home: Path) -> None:
    result = _run_custom_install(fake_home)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    claude_skills = fake_home / ".claude" / "skills"
    codex_skills = fake_home / ".codex" / "skills"
    claude_agents = fake_home / ".claude" / "agents"
    codex_agents = fake_home / ".codex" / "agents"

    assert (claude_skills / "do" / "SKILL.md").exists()
    assert (codex_skills / "do" / "SKILL.md").exists()
    assert not (claude_skills / "voice-writer").exists()
    assert not (codex_skills / "voice-writer").exists()
    assert (claude_skills / "kubernetes-debugging" / "SKILL.md").exists()
    assert (claude_skills / "php-quality" / "SKILL.md").exists()
    assert (claude_skills / "generate-claudemd" / "SKILL.md").exists()

    skills_index = json.loads((claude_skills / "INDEX.json").read_text(encoding="utf-8"))
    assert "do" in skills_index["skills"]
    assert "voice-writer" not in skills_index["skills"]
    assert "kubernetes-debugging" in skills_index["skills"]
    assert "php-quality" in skills_index["skills"]
    assert "generate-claudemd" in skills_index["skills"]

    assert (claude_agents / "reviewer-code.md").exists()
    assert (codex_agents / "reviewer-code.md").exists()
    assert (claude_agents / "nextjs-ecommerce-engineer.md").exists()
    assert (claude_agents / "python-general-engineer.md").exists()
    assert not (claude_agents / "technical-journalist-writer.md").exists()
    assert not (codex_agents / "technical-journalist-writer.md").exists()
    assert not (claude_agents / "golang-general-engineer.md").exists()

    agents_index = json.loads((claude_agents / "INDEX.json").read_text(encoding="utf-8"))
    assert "reviewer-code" in agents_index["agents"]
    assert "nextjs-ecommerce-engineer" in agents_index["agents"]
    assert "python-general-engineer" in agents_index["agents"]
    assert "technical-journalist-writer" not in agents_index["agents"]
    assert "golang-general-engineer" not in agents_index["agents"]
    assert "go-patterns" not in agents_index["agents"]["reviewer-system"].get("pairs_with", [])

    assert not (fake_home / ".claude" / "hooks" / "sync-to-user-claude.py").exists()
    settings = json.loads((fake_home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    settings_text = json.dumps(settings)
    assert "sync-to-user-claude.py" not in settings_text
    assert "Sync agents/skills/hooks/commands to ~/.claude" not in settings_text


def test_custom_install_uses_default_profile_and_writes_clean_settings(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'python3 "$HOME/.claude/hooks/stale-local-hook.py"',
                                }
                            ]
                        }
                    ]
                },
                "localOnly": True,
            }
        ),
        encoding="utf-8",
    )

    result = _run_custom_install(fake_home, use_explicit_profile=False)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    settings_text = json.dumps(settings)
    assert "stale-local-hook.py" not in settings_text
    assert "localOnly" not in settings
    assert "sync-to-user-claude.py" not in settings_text
    assert "afk-mode.py" in settings_text


def test_custom_install_replaces_component_symlinks_with_real_dirs(fake_home: Path, tmp_path: Path) -> None:
    linked = tmp_path / "linked"
    (linked / "claude-skills").mkdir(parents=True)
    (linked / "codex-skills").mkdir(parents=True)

    claude_dir = fake_home / ".claude"
    codex_dir = fake_home / ".codex"
    claude_dir.mkdir()
    codex_dir.mkdir()
    (claude_dir / "skills").symlink_to(linked / "claude-skills")
    (codex_dir / "skills").symlink_to(linked / "codex-skills")

    result = _run_custom_install(fake_home)

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert (claude_dir / "skills").is_dir()
    assert not (claude_dir / "skills").is_symlink()
    assert (codex_dir / "skills").is_dir()
    assert not (codex_dir / "skills").is_symlink()
    assert (claude_dir / "skills" / "do" / "SKILL.md").exists()
    assert (codex_dir / "skills" / "do" / "SKILL.md").exists()


def test_sync_upstream_main_runs_expected_git_sequence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_custom_install_module()
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs.get("cwd")))
        if args == ["git", "status", "--porcelain", "--untracked-files=no"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module.sync_upstream_main(tmp_path)

    assert calls == [
        (["git", "status", "--porcelain", "--untracked-files=no"], tmp_path),
        (["git", "fetch", "upstream"], tmp_path),
        (["git", "switch", "main"], tmp_path),
        (["git", "merge", "upstream/main"], tmp_path),
        (["git", "push", "origin", "main"], tmp_path),
    ]
