"""Runs install.sh against a copy of this directory in a throwaway git repo, installing into a
throwaway home (AI_WORKFLOW_HOME), so nothing here or under ~ changes. The copy keeps only the core
feature and adds a `demo` one with every part, so the tests don't depend on which features exist."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1]

DEMO = {
    "docs/guide.md": "# Guide\n",
    "skills/demo-skill/SKILL.md": "Read {{AI_WORKFLOW_DOCS_DIR}}/demo/guide.md\n",
    "bin/demo": "#!/bin/sh\n",
    "plugins/claude-code/demo-plugin/.claude-plugin/plugin.json": '{ "name": "demo-plugin" }\n',
}


def sh(*args, cwd, env=None):
    return subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True, check=True, env=env).stdout


def git(*args, cwd):
    return sh("git", *args, cwd=cwd).strip()


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / "repo"
    wf = repo / "ai-workflow"
    shutil.copytree(SRC, wf, ignore=shutil.ignore_patterns(".rendered*", "__pycache__", ".git"))
    for feature in (wf / "features").iterdir():
        if feature.name != "core":
            shutil.rmtree(feature)
    for path, text in DEMO.items():
        (wf / "features/demo" / path).parent.mkdir(parents=True, exist_ok=True)
        (wf / "features/demo" / path).write_text(text)
    (wf / "features/demo/bin/demo").chmod(0o755)
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "dev@example.com", cwd=repo)
    git("config", "user.name", "Dev", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    home = tmp_path / "home"
    env = {**os.environ, "AI_WORKFLOW_HOME": str(home), "SHELL": "/bin/bash"}
    return wf, home, env


def install(wf, env, *args):
    return sh(wf / "install.sh", *args, cwd=wf, env=env)


def test_tools_see_only_the_rendered_copy(setup):
    wf, home, env = setup
    out = install(wf, env, "claude")
    rendered = wf / ".rendered"
    assert "skipping git hooks" in out
    assert (home / ".claude/CLAUDE.md").resolve() == rendered / "AGENTS.md"
    assert (home / ".claude/docs").resolve() == rendered / "docs"
    assert (home / ".claude/skills/demo-skill").resolve() == rendered / "skills/demo-skill"
    assert (home / ".claude/skills/demo-plugin").resolve() == rendered / "plugins/claude-code/demo-plugin"
    assert (home / ".claude/skills/pending-items").resolve() == rendered / "plugins/claude-code/pending-items"
    skill = (rendered / "skills/demo-skill/SKILL.md").read_text()
    assert f"{rendered}/docs/demo/guide.md" in skill and "{{AI_WORKFLOW_DOCS_DIR}}" not in skill
    assert (rendered / "docs/demo/guide.md").is_file() and (rendered / "docs/pull-requests.md").is_file()
    assert not (home / ".codex").exists()
    # The rc wiring: bin/ on PATH and the core shell snippets loaded.
    shell = sh("bash", "--norc", "-c", f'. "{home}/.bashrc" && command -v demo && type git', cwd=home)
    assert f"{rendered}/bin/demo" in shell and "git is a function" in shell


def test_refresh_only_follows_the_default_branch(setup):
    wf, home, env = setup
    install(wf, env, "claude")
    demo = wf / ".rendered/bin/demo"
    before = demo.read_text()

    git("switch", "-q", "-c", "feature", cwd=wf)
    (wf / "features/demo/bin/demo").write_text(before + "# feature\n")
    shutil.rmtree(wf / "features/demo/skills/demo-skill")
    git("commit", "-q", "-am", "feature work", cwd=wf)
    install(wf, env, "--refresh")
    assert demo.read_text() == before and (home / ".claude/skills/demo-skill").exists()

    install(wf, env, "claude")  # explicit: renders what is checked out
    assert demo.read_text().endswith("# feature\n") and not (home / ".claude/skills/demo-skill").exists()

    git("switch", "-q", "main", cwd=wf)
    install(wf, env, "--refresh")
    assert demo.read_text() == before and (home / ".claude/skills/demo-skill").exists()


def test_features_install_and_uninstall_as_a_unit(setup):
    wf, home, env = setup
    install(wf, env, "claude")
    rendered = wf / ".rendered"

    install(wf, env, "--features", "none", "claude")
    for part in ["skills/demo-skill", "plugins/claude-code/demo-plugin", "bin/demo", "docs/demo"]:
        assert not (rendered / part).exists()
    assert sorted(p.name for p in (home / ".claude/skills").iterdir()) == ["pending-items"]
    assert (rendered / "bin/pull-pr-description").is_file()

    install(wf, env, "--refresh")  # the git hooks keep the selection
    install(wf, env, "claude")  # and so does a run without --features
    assert not (home / ".claude/skills/demo-skill").exists()

    install(wf, env, "--features", "demo", "claude")
    assert (home / ".claude/skills/demo-skill").exists() and (home / ".claude/skills/demo-plugin").exists()


def test_a_feature_missing_from_the_checkout_stays_selected(setup):
    wf, home, env = setup
    install(wf, env, "claude")

    # A checkout of a branch that doesn't have the feature (e.g. main while it lives on a branch).
    git("switch", "-q", "-c", "without-demo", cwd=wf)
    shutil.rmtree(wf / "features/demo")
    git("commit", "-q", "-am", "no demo", cwd=wf)
    install(wf, env, "claude")
    assert not (home / ".claude/skills/demo-skill").exists()
    assert "demo (installed, not in this checkout)" in install(wf, env, "--list")

    git("switch", "-q", "main", cwd=wf)
    install(wf, env, "--refresh")
    assert (home / ".claude/skills/demo-skill").exists()


@pytest.mark.parametrize("files, error", [
    (["features/extra/bin/demo"], "another feature already provides bin/demo"),
    (["features/extra/plugins/claude-code/demo-skill/README.md"], "a skill has the same name"),
    (["features/core/docs/extra/a.md", "features/extra/docs/b.md"], "core already provides docs/extra"),
])
def test_a_name_clash_between_features_keeps_the_installed_copy(setup, files, error):
    wf, home, env = setup
    install(wf, env, "claude")
    demo = (wf / ".rendered/bin/demo").read_text()
    for file in files:
        (wf / file).parent.mkdir(parents=True, exist_ok=True)
        (wf / file).write_text("x\n")

    with pytest.raises(subprocess.CalledProcessError) as failed:
        install(wf, env, "--features", "demo,extra", "claude")
    assert error in failed.value.stderr
    assert (wf / ".rendered/bin/demo").read_text() == demo
    assert (wf / ".rendered/features").read_text() == "demo\n"
    assert not (wf / ".rendered.new").exists()


# MIGRATION(feature-dirs): remove with the migration code in install.sh.
def test_migrates_an_install_from_before_feature_dirs(setup):
    wf, home, env = setup
    (home / ".claude/skills").mkdir(parents=True)
    old_plugins = wf / "plugins/claude-code"
    (home / ".claude/skills/pending-items").symlink_to(old_plugins / "pending-items")
    (home / ".codex/skills").mkdir(parents=True)
    (home / ".codex/skills/removed-plugin").symlink_to(old_plugins / "removed-plugin")
    (home / ".bashrc").write_text(f'echo mine\nexport PATH="{wf}/.rendered/bin:$PATH" # dev-env:ai-workflow-bin\n')

    install(wf, env, "claude")
    assert (home / ".claude/skills/pending-items").resolve() == wf / ".rendered/plugins/claude-code/pending-items"
    assert not (home / ".codex/skills/removed-plugin").is_symlink()
    rc = (home / ".bashrc").read_text()
    assert rc.startswith("echo mine\n") and "ai-workflow-bin" not in rc and rc.count("ai-workflow-env") == 1
