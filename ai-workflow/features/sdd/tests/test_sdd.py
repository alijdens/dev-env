"""Drives the `sdd` CLI against throwaway git repos and bare remotes.

The CLI is the lowest layer here, so these tests cover its behavior in detail; `gh` is never
reached because every PR-opening command runs with `--no-pr`.
"""
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

TASKS = Path(__file__).resolve().parents[1] / "bin" / "sdd"


def run(*args, cwd, check=True):
    r = subprocess.run([str(TASKS), *map(str, args)], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"sdd {' '.join(map(str, args))} failed:\n{r.stdout}{r.stderr}")
    return r


def fails(*args, cwd):
    r = run(*args, cwd=cwd, check=False)
    assert r.returncode != 0, f"expected failure, got:\n{r.stdout}"
    return r.stderr


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def init_repo(path, branch="main"):
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", branch, cwd=path)
    git("config", "user.email", "dev@example.com", cwd=path)
    git("config", "user.name", "Dev", cwd=path)
    return path


def commit_all(repo, message="update"):
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)


def add_remote(repo, bare, branch="main"):
    """A bare remote reached through `git remote add`, which unlike a clone leaves origin/HEAD unset."""
    bare.mkdir(parents=True)
    git("init", "-q", "--bare", "-b", branch, cwd=bare)
    git("remote", "add", "origin", str(bare), cwd=repo)
    git("push", "-q", "-u", "origin", branch, cwd=repo)


def remote_branches(bare):
    return set(git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=bare).split())


def states(repo):
    return {line.split("\t")[0]: line.split("\t")[1] for line in run("list", cwd=repo).stdout.splitlines()}


@pytest.fixture
def repo(tmp_path):
    repo = init_repo(tmp_path / "repo")
    run("init", cwd=repo)
    commit_all(repo, "set up task workflow")
    return repo


@pytest.fixture
def shared(repo, tmp_path):
    """A shared-mode repo with tasks a -> b on a bare remote, and the CLI pointed at that remote."""
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    commit_all(repo, "plan")
    add_remote(repo, tmp_path / "remote.git")
    return repo


# --- setup ---------------------------------------------------------------------------------


def test_init_creates_layout_and_agent_section(repo):
    for d in ("todo", "in-progress", "tech-debt"):
        assert (repo / "docs/tasks" / d / ".gitkeep").is_file()
    assert (repo / "docs/arch").is_dir()
    content = (repo / "AGENTS.md").read_text()
    assert "sdd: docs" in content
    assert "<!-- sdd:start -->" in content
    assert run("root", cwd=repo).stdout == f"{repo / 'docs'}\nmode: shared\n"

    run("init", cwd=repo)  # re-running rewrites the section instead of appending a second one
    assert (repo / "AGENTS.md").read_text().count("sdd:start") == 1


def test_init_agent_file_is_chosen_once(tmp_path):
    repo = init_repo(tmp_path / "r")
    out = run("init", "--agent-file", "CLAUDE.md", cwd=repo).stdout
    assert "sdd: docs" in (repo / "CLAUDE.md").read_text()
    assert not (repo / "AGENTS.md").exists()
    assert "note:" not in out
    assert "already lives in CLAUDE.md" in fails("init", "--agent-file", "AGENTS.md", cwd=repo)


def test_init_without_claude_md_warns_about_claude_code(tmp_path):
    repo = init_repo(tmp_path / "r")
    assert "Claude Code only loads CLAUDE.md" in run("init", cwd=repo).stdout


def test_local_mode_wins_over_marker_and_stays_out_of_the_repo(repo, tmp_path):
    data = tmp_path / "localdata"
    run("init", "--local", data, cwd=repo)
    assert run("root", cwd=repo).stdout == f"{data}\nmode: local\n"
    assert (data / "tasks/todo/.gitkeep").is_file()
    assert git("status", "--porcelain", "--", "docs", cwd=repo) == ""


def test_root_fails_when_not_set_up(tmp_path):
    repo = init_repo(tmp_path / "r")
    assert "not initialized" in fails("root", cwd=repo)


# --- tasks, dependencies and ADRs ----------------------------------------------------------


def test_new_list_show_and_ready_follow_dependencies(repo):
    run("adr", "store", "--title", "Store", cwd=repo)
    adr = next((repo / "docs/arch").glob("*-store.md")).stem
    assert "already exists" in fails("adr", "store", "--title", "Again", cwd=repo)
    run("new", "a", "--title", "[WIP] fix [x]", "--arch", adr, cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    run("new", "td", "--title", "Debt", "--tech-debt", cwd=repo)

    assert "[WIP] fix [x]" in run("list", cwd=repo).stdout  # brackets in a title are not a list
    assert states(repo) == {"a": "todo", "b": "todo", "td": "tech-debt"}
    assert set(run("ready", cwd=repo).stdout.split("\n")[:-1]) == {"a\ttodo\t[WIP] fix [x]\t1", "td\ttech-debt\tDebt\t0"}
    show = run("show", "b", cwd=repo).stdout
    assert "prereqs:\n  a\ttodo" in show and "ready: no, waiting on a" in show
    assert str(repo / "docs/arch" / f"{adr}.md") in run("show", "a", cwd=repo).stdout

    assert "unknown prerequisite" in fails("new", "c", "--title", "C", "--after", "zzz", cwd=repo)
    assert "unknown architecture decision" in fails("new", "c", "--title", "C", "--arch", "nope", cwd=repo)
    assert "already exists" in fails("new", "a", "--title", "A", cwd=repo)
    assert "kebab-case" in fails("new", "Bad_Slug", "--title", "x", cwd=repo)


def test_ready_counts_the_work_waiting_behind_each_task(repo):
    for slug, after in (("a", []), ("b", ["a"]), ("c", ["b"]), ("d", [])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), cwd=repo)
    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t2\nd\ttodo\tD\t0\n"


def test_brief_prints_the_task_and_everything_linked_to_it(repo):
    run("adr", "store", "--title", "Store", cwd=repo)
    adr = next((repo / "docs/arch").glob("*-store.md"))
    adr.write_text(adr.read_text().replace("## Decision\n", "## Decision\n\nKeep it in Redis.\n") + "## Review checks\n\n- Every key has a TTL.\n")
    run("new", "a", "--title", "A", "--arch", adr.stem, cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    fill_question(Path(run("ask", "ttl", "--title", "How long?", "--task", "a", cwd=repo).stdout.strip()))
    fill_doc(Path(run("doc", "new", "goal", cwd=repo).stdout.strip()))

    out = run("brief", "a", cwd=repo).stdout
    assert out.startswith("slug: a\nstate: todo\n")
    assert f"=== architecture decision: arch/{adr.stem}.md" in out and "Keep it in Redis." in out
    assert "=== question (open): questions/open/ttl.md" in out and "=== task: tasks/todo/a.md" in out
    assert "tasks/todo/b.md" not in out and "=== goal" not in out and "=== review checks" not in out

    review = run("brief", "a", "--review", cwd=repo).stdout
    assert "=== dependent task: tasks/todo/b.md" in review and "=== goal: goal.md" in review
    assert review.rstrip().endswith("=== review checks (sdd checks --task)\n\n" + f"{adr.stem}\t\tStore\n  - Every key has a TTL.")
    assert "unknown task" in fails("brief", "zzz", cwd=repo)


def test_accept_marks_proposed_decisions_accepted(repo):
    run("adr", "store", "--title", "Store", cwd=repo)
    adr = next((repo / "docs/arch").glob("*-store.md"))
    assert run("accept", adr.stem, cwd=repo).stdout == f"accepted {adr.stem}\n"
    assert "status: accepted" in adr.read_text()
    assert "not proposed" in fails("accept", adr.stem, cwd=repo)
    assert "unknown architecture decision" in fails("accept", "nope", cwd=repo)


def test_dep_edits_frontmatter_and_rejects_cycles(repo):
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    run("new", "c", "--title", "C", cwd=repo)

    assert "dependency cycle: a -> b -> a" in fails("dep", "add", "a", "b", cwd=repo)
    assert "can't depend on itself" in fails("dep", "add", "a", "a", cwd=repo)
    run("dep", "add", "c", "a", "b", cwd=repo)
    assert "after: [a, b]" in (repo / "docs/tasks/todo/c.md").read_text()
    run("dep", "rm", "c", "a", cwd=repo)
    assert "after: [b]" in (repo / "docs/tasks/todo/c.md").read_text()
    assert "no such dependencies" in fails("dep", "rm", "c", "a", cwd=repo)


def test_rm_only_deletes_unreferenced_planned_tasks(repo):
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    assert "prerequisite of: b" in fails("rm", "a", cwd=repo)
    run("rm", "b", cwd=repo)
    run("rm", "a", cwd=repo)
    assert states(repo) == {}


def test_validate_reports_inconsistencies(repo):
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    assert run("validate", cwd=repo).stdout.endswith("ok: 2 tasks, 1 dependencies, 0 architecture decisions, 0 open questions\n")

    (repo / "docs/tasks/todo/b.md").write_text("---\ntitle: B\nafter: [a, ghost]\narch: [missing-adr]\n---\n")
    (repo / "docs/tasks/todo/.gitkeep").unlink()
    (repo / "docs/tasks/done/not-a-date").mkdir(parents=True)
    (repo / "docs/tasks/done/not-a-date/a.md").write_text("---\ntitle: dup\n---\n")
    out = run("validate", cwd=repo, check=False)
    assert out.returncode == 1
    for msg in ("unknown prerequisite ghost", "unknown architecture decision missing-adr", "missing tasks/todo/.gitkeep",
                "not a YYYY-MM-DD date", "duplicate task slug a"):
        assert msg in out.stdout, msg


def test_validate_warns_when_a_claimed_task_has_unmet_prerequisites(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", cwd=repo)
    run("start", "b", cwd=repo, check=False)  # refused: a isn't done
    assert states(repo)["b"] == "todo"
    run("start", "a", cwd=repo)
    (tmp_path / "data/tasks/todo/b.md").rename(tmp_path / "data/tasks/in-progress/b.md")
    out = run("validate", cwd=repo).stdout
    assert "warning: b is in-progress but prerequisites aren't done: a" in out


def test_render_labels_states(repo):
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", "--after", "a", "--tech-debt", cwd=repo)
    out = run("render", cwd=repo).stdout
    assert '"a" [label="a\\n(todo)"];' in out
    assert '"b" [label="b\\n(tech-debt)" style=dashed];' in out
    assert '"a" -> "b";' in out


# --- questions -----------------------------------------------------------------------------


def fill_question(path, question="Per key or per user?", context="See limits.py; assumed per key meanwhile.", answer=""):
    text = path.read_text().split("\n## Question")[0]
    path.write_text(f"{text}\n## Question\n\n{question}\n\n## Context\n\n{context}\n\n## Answer\n\n{answer}\n")


def test_open_blocking_question_holds_a_task_like_a_prerequisite(repo):
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", cwd=repo)
    run("adr", "limits", "--title", "Limits", cwd=repo)
    adr = next((repo / "docs/arch").glob("*-limits.md")).stem
    path = Path(run("ask", "per-key", "--title", "Per key?", "--task", "a", "--blocks", "b", "--arch", adr, cwd=repo).stdout.strip())
    assert path == repo / "docs/questions/open/per-key.md"
    assert f"tasks: [a]\narch: [{adr}]\nblocks: [b]\nasked: " in path.read_text()

    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t0\n"
    assert "ready: no, waiting on question per-key" in run("show", "b", cwd=repo).stdout
    assert "per-key\topen (blocks this task)" in run("show", "b", cwd=repo).stdout
    assert "per-key\topen\t" in run("show", "a", cwd=repo).stdout
    assert "already exists" in fails("ask", "per-key", "--title", "x", cwd=repo)
    assert "unknown task" in fails("ask", "other", "--title", "x", "--task", "zzz", cwd=repo)

    fill_question(path)
    assert run("questions", cwd=repo).stdout.startswith("per-key\topen\tPer key?\ta\tb\t20")
    assert run("questions", "--task", "b", cwd=repo).stdout.startswith("per-key")
    assert run("questions", "--arch", adr, cwd=repo).stdout.startswith("per-key")
    assert run("questions", "--task", "zzz", cwd=repo).stdout == ""

    assert "write the answer" in fails("answer", "per-key", cwd=repo)
    fill_question(path, answer="Per key.")
    run("answer", "per-key", cwd=repo)
    answered = repo / "docs/questions/answered/per-key.md"
    assert answered.is_file() and "answered: " in answered.read_text()
    assert run("questions", cwd=repo).stdout == ""
    assert "per-key\tanswered" in run("questions", "--all", cwd=repo).stdout
    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t0\nb\ttodo\tB\t0\n"
    assert "already answered" in fails("answer", "per-key", cwd=repo)


def test_questions_are_listed_by_how_much_they_hold_back(repo):
    for slug in ("a", "b", "c"):
        run("new", slug, "--title", slug.upper(), cwd=repo)
    run("ask", "old-unlinked", "--title", "x", "--task", "a", cwd=repo)
    run("ask", "blocks-two", "--title", "x", "--blocks", "a", "b", cwd=repo)
    run("ask", "blocks-one", "--title", "x", "--blocks", "c", "--task", "a", "b", "c", cwd=repo)
    run("ask", "links-two", "--title", "x", "--task", "a", "b", cwd=repo)
    old = repo / "docs/questions/open/old-unlinked.md"
    old.write_text(old.read_text().replace("asked: 20", "asked: 19"))
    order = [line.split("\t")[0] for line in run("questions", cwd=repo).stdout.splitlines()]
    assert order == ["blocks-two", "blocks-one", "links-two", "old-unlinked"]


def test_validate_requires_questions_to_stand_alone(repo):
    run("new", "a", "--title", "A", cwd=repo)
    path = Path(run("ask", "q", "--title", "Q", "--task", "a", cwd=repo).stdout.strip())
    out = run("validate", cwd=repo, check=False).stdout
    assert "empty `## Question` section" in out and "empty `## Context` section" in out

    fill_question(path, answer="Done")
    out = run("validate", cwd=repo).stdout
    assert "has an answer but is still open" in out

    path.write_text("---\ntitle: Q\ntasks: [ghost]\narch: [nope]\nblocks: []\n---\n\n## Question\n\nQ\n\n## Context\n\nC\n\n## Answer\n")
    out = run("validate", cwd=repo, check=False).stdout
    assert "unknown task ghost in tasks" in out and "unknown architecture decision nope" in out

    path.write_text("---\ntitle: Q\ntasks: []\narch: []\nblocks: []\n---\n\n## Question\n\nQ\n\n## Context\n\nC\n\n## Answer\n")
    assert "links to no task or architecture decision" in run("validate", cwd=repo).stdout


def test_validate_warns_when_a_claimed_task_is_blocked_by_a_question(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", cwd=repo)
    run("start", "a", cwd=repo)
    fill_question(Path(run("ask", "q", "--title", "Q", "--blocks", "a", "b", "--task", "a", cwd=repo).stdout.strip()))
    assert "a is in-progress but blocked by open questions: q" in run("validate", cwd=repo).stdout
    assert "b is waiting on: question q" in fails("start", "b", cwd=repo)


# --- ADRs, specs and context ---------------------------------------------------------------


def adr(repo, slug, *args):
    return next((repo / "docs/arch").glob(f"*-{slug}.md")).stem if not args else Path(run("adr", slug, *args, cwd=repo).stdout.strip()).stem


def test_adr_frontmatter_amend_and_supersede(repo):
    old = adr(repo, "limits", "--title", "Limits in memory", "--areas", "backend/rate-limiting")
    text = (repo / f"docs/arch/{old}.md").read_text()
    assert text.startswith(f"---\ntitle: Limits in memory\nstatus: proposed\ndate: ") and "areas: [backend/rate-limiting]" in text

    amend = adr(repo, "limits-keys", "--title", "Limits keyed per API key", "--areas", "backend/rate-limiting", "--amends", old)
    text = (repo / f"docs/arch/{old}.md").read_text()
    assert f"amended-by: [{amend}]" in text and "status: proposed" in text
    new = adr(repo, "limits-redis", "--title", "Limits in Redis", "--supersedes", old)
    text = (repo / f"docs/arch/{old}.md").read_text()
    assert f"superseded-by: [{new}]" in text and "status: superseded" in text
    assert "unknown architecture decision" in fails("adr", "x", "--title", "x", "--amends", "nope", cwd=repo)

    out = run("adrs", cwd=repo).stdout
    assert f"{old}\tsuperseded\t0\tbackend/rate-limiting\tLimits in memory" in out
    assert run("adrs", "--area", "backend", cwd=repo).stdout.count("\n") == 2
    assert run("areas", cwd=repo).stdout == "2\tbackend/rate-limiting\n"


def test_context_ranks_foundations_and_matches_areas_or_words(repo):
    base = adr(repo, "stack", "--title", "Go with SQLite", "--areas", "backend")
    auth = adr(repo, "sessions", "--title", "Sessions in Redis", "--areas", "backend/auth")
    web = adr(repo, "tokens", "--title", "CSS tokens", "--areas", "web/design")
    for i in range(4):
        run("new", f"t{i}", "--title", f"T{i}", "--arch", base, cwd=repo)
    run("new", "login", "--title", "Login", "--arch", auth, cwd=repo)
    run("spec", "data-model", "--title", "Data model", "--areas", "backend/db", "--arch", base, cwd=repo)
    run("new", "schema", "--title", "Schema", "--spec", "data-model", cwd=repo)
    q = Path(run("ask", "q", "--title", "Q", "--task", "login", "--arch", auth, cwd=repo).stdout.strip())

    out = run("context", "--area", "backend/auth", cwd=repo).stdout
    assert f"  {base}\tproposed\t5 refs" in out.split("matching ADRs:")[0]
    assert f"  {auth}\tproposed\t1 refs\tSessions in Redis" in out.split("matching ADRs:")[1]
    assert web not in out
    assert "  login\ttodo\tLogin" in out and "  t0" not in out.split("tasks referencing")[1]
    assert "  q\topen\tQ" in out

    out = run("context", "--grep", "redis", cwd=repo).stdout
    assert auth in out.split("matching ADRs:")[1]
    out = run("context", "--area", "backend/db", cwd=repo).stdout
    assert "  data-model\tData model" in out
    assert "  schema\ttodo\tSchema" in out
    assert "showing only the foundations" in run("context", cwd=repo).stdout
    assert "specs:\n  " + str(repo / "docs/specs/data-model.md") in run("show", "schema", cwd=repo).stdout


def test_link_adds_references_to_done_tasks(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    a = adr(repo, "x", "--title", "X")
    run("spec", "s", "--title", "S", cwd=repo)
    run("new", "t", "--title", "T", cwd=repo)
    run("start", "t", cwd=repo)
    run("done", "t", cwd=repo)
    run("link", "t", "--arch", a, "--spec", "s", cwd=repo)
    text = next((tmp_path / "data/tasks/done").glob("*/t.md")).read_text()
    assert f"arch: [{a}]" in text and "spec: [s]" in text
    assert "unknown spec" in fails("link", "t", "--spec", "nope", cwd=repo)


def test_defer_hides_a_question_until_its_tasks_are_done(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "t", "--title", "T", cwd=repo)
    fill_question(Path(run("ask", "q", "--title", "Q", "--task", "t", cwd=repo).stdout.strip()))
    run("defer", "q", "--until", "t", cwd=repo)
    assert run("questions", cwd=repo).stdout == ""
    assert "q\tdeferred until t\tQ" in run("questions", "--all", cwd=repo).stdout
    run("start", "t", cwd=repo)
    run("done", "t", cwd=repo)
    assert run("questions", cwd=repo).stdout.startswith("q\topen\tQ")


def test_validate_flags_adrs_that_read_as_specs(repo):
    a = adr(repo, "big", "--title", "Big", "--areas", "x")
    path = repo / f"docs/arch/{a}.md"
    path.write_text(path.read_text().replace("status: proposed", "status: accepted") + "filler\n" * 100)
    out = run("validate", cwd=repo).stdout
    assert "over 100 lines" in out and "no alternatives considered" in out
    path.write_text(path.read_text().replace("status: accepted", "status: done"))
    assert "status must be one of" in run("validate", cwd=repo, check=False).stdout


def test_checks_collects_review_checks_by_area_or_task(repo):
    db = adr(repo, "migrations", "--title", "Reversible migrations", "--areas", "backend/db")
    (repo / f"docs/arch/{db}.md").write_text((repo / f"docs/arch/{db}.md").read_text() + "\n## Review checks\n\n- Every migration has a down step.\n")
    run("spec", "api", "--title", "API conventions", "--areas", "backend/api", cwd=repo)
    (repo / "docs/specs/api.md").write_text((repo / "docs/specs/api.md").read_text() + "\n## Review checks\n\n- New endpoints are in `openapi.yaml`\n  and the client.\nprose\n")
    old = adr(repo, "old", "--title", "Old", "--areas", "backend/db")
    (repo / f"docs/arch/{old}.md").write_text((repo / f"docs/arch/{old}.md").read_text() + "\n## Review checks\n\n- Stale check.\n")
    adr(repo, "newer", "--title", "Newer", "--supersedes", old)
    run("new", "schema", "--title", "Schema", "--arch", db, cwd=repo)

    out = run("checks", cwd=repo).stdout
    assert f"{db}\tbackend/db\tReversible migrations\n  - Every migration has a down step.\n" in out
    assert "api\tbackend/api\tAPI conventions\n  - New endpoints are in `openapi.yaml`\n    and the client.\n" in out
    assert "Stale check" not in out
    assert "api" not in run("checks", "--area", "backend/db", cwd=repo).stdout
    assert "api" not in run("checks", "--task", "schema", cwd=repo).stdout and db in run("checks", "--task", "schema", cwd=repo).stdout
    out = run("validate", cwd=repo).stdout
    assert "api.md: `## Review checks` has lines that aren't bullets" in out
    (repo / "docs/specs/api.md").write_text((repo / "docs/specs/api.md").read_text().replace("prose\n", "".join(f"- c{i}\n" for i in range(10))))
    assert "over 10 review checks" in run("validate", cwd=repo).stdout


def test_validate_refuses_edits_to_accepted_adr_bodies(shared):
    a = adr(shared, "fixed", "--title", "Fixed", "--areas", "x")
    path = shared / f"docs/arch/{a}.md"
    path.write_text(path.read_text().replace("status: accepted", "status: accepted").replace("status: proposed", "status: accepted").replace("## Alternatives considered\n", "## Alternatives considered\n\nnone really\n"))
    commit_all(shared, "accept")
    git("push", "-q", cwd=shared)
    assert "body changed" not in run("validate", cwd=shared).stdout

    path.write_text(path.read_text() + "\n## Errata\n\n- 2026-10-30: the variable is TURNOS_ENV.\n")
    path.write_text(path.read_text().replace("areas: [x]", "areas: [x, y]"))
    path.write_text(path.read_text() + "\n## Review checks\n\n- The variable is read once at startup.\n")
    assert "body changed" not in run("validate", cwd=shared).stdout

    path.write_text(path.read_text().replace("## Decision\n", "## Decision\n\nchanged my mind\n"))
    assert "body changed since origin/main" in run("validate", cwd=shared, check=False).stdout


def test_validate_warns_when_agent_section_is_outdated(repo):
    agents = repo / "AGENTS.md"
    agents.write_text(agents.read_text().replace("When planning a feature", "When planning a thing"))
    assert "section is from an older version" in run("validate", cwd=repo).stdout
    run("init", cwd=repo)
    assert "older version" not in run("validate", cwd=repo).stdout


# --- project docs --------------------------------------------------------------------------


def fill_doc(path, filler="Something."):
    """Replaces every template comment with text, so each section has content."""
    import re
    path.write_text(re.sub(r"<!--.*?-->", filler, path.read_text(), flags=re.S))


def test_doc_templates_are_drafts_until_filled(repo):
    assert run("doc", "list", cwd=repo).stdout == f"goal\tmissing\t{repo / 'docs/goal.md'}\nprinciples\tmissing\t{repo / 'docs/principles.md'}\n"
    assert "no goal.md" in run("validate", cwd=repo).stdout

    path = Path(run("doc", "new", "goal", cwd=repo).stdout.strip())
    assert "already exists" in fails("doc", "new", "goal", cwd=repo)
    assert "needs a name" in fails("doc", "new", cwd=repo)
    out = run("doc", "check", cwd=repo, check=False)
    assert out.returncode == 1
    assert "still has template guidance comments" in out.stdout and "empty `## Problem` section" in out.stdout
    assert run("validate", cwd=repo, check=False).returncode == 1

    fill_doc(path)
    assert run("doc", "check", cwd=repo).stdout == "goal: ok\nprinciples: missing\n"
    assert run("validate", cwd=repo).returncode == 0

    path.write_text(path.read_text() + "filler\n" * 60)
    assert "over the 60-line limit" in run("doc", "check", cwd=repo, check=False).stdout
    run("doc", "new", "goal", "--force", cwd=repo)
    assert "<!--" in path.read_text()


def test_doc_check_reports_missing_sections(repo):
    path = Path(run("doc", "new", "principles", cwd=repo).stdout.strip())
    fill_doc(path)
    path.write_text(path.read_text().replace("## Quality\n", "## Speed\n"))
    assert "missing `## Quality` section" in run("doc", "check", cwd=repo, check=False).stdout


# --- claims against a remote ---------------------------------------------------------------


def test_claim_is_a_branch_on_main_and_only_one_wins(shared, tmp_path):
    bare = tmp_path / "remote.git"
    assert run("start", "a", "--no-pr", cwd=shared).stdout == "pushed claim/a\n"
    assert "claim/a" in remote_branches(bare)
    assert states(shared)["a"] == "todo"  # the checkout is untouched until main is pulled
    assert git("status", "--porcelain", cwd=shared) == ""

    assert "could not push claim/a" in fails("start", "a", "--no-pr", cwd=shared)
    assert "waiting on: a" in fails("start", "b", "--no-pr", cwd=shared)

    git("fetch", "-q", "origin", cwd=shared)
    git("merge", "-q", "--ff-only", "origin/claim/a", cwd=shared)
    git("push", "-q", cwd=shared)
    assert "claimed: " in run("show", "a", cwd=shared).stdout
    assert "already claimed" in fails("start", "a", "--no-pr", cwd=shared)
    assert run("list", "in-progress", cwd=shared).stdout.startswith("a\tin-progress\tA\t20")


def test_stale_fails_when_behind_main_or_dirty(shared, tmp_path):
    assert run("stale", cwd=shared).stdout == "up to date with origin/main\n"

    run("new", "c", "--title", "C", cwd=shared)
    out = run("stale", cwd=shared, check=False)
    assert out.returncode == 1 and "uncommitted changes under docs" in out.stdout
    commit_all(shared, "plan c")
    git("push", "-q", cwd=shared)

    other = tmp_path / "other"
    git("clone", "-q", str(tmp_path / "remote.git"), str(other), cwd=tmp_path)
    git("config", "user.email", "x@example.com", cwd=other)
    git("config", "user.name", "X", cwd=other)
    git("reset", "-q", "--hard", "HEAD~1", cwd=other)
    out = run("stale", cwd=other, check=False)
    assert out.returncode == 1 and "behind origin/main by 1 commits" in out.stdout


def other_clone(tmp_path, name="other"):
    other = tmp_path / name
    git("clone", "-q", str(tmp_path / "remote.git"), str(other), cwd=tmp_path)
    git("config", "user.email", "x@example.com", cwd=other)
    git("config", "user.name", "X", cwd=other)
    return other


def test_stale_fix_drops_only_the_changes_that_match_main(shared, tmp_path):
    # Someone else plans c, edits a and removes b, and ships it.
    other = other_clone(tmp_path)
    run("new", "c", "--title", "C", cwd=other)
    (other / "docs/tasks/todo/a.md").write_text((other / "docs/tasks/todo/a.md").read_text() + "\nAdded on main.\n")
    run("rm", "b", cwd=other)
    commit_all(other, "plan c")
    git("push", "-q", cwd=other)
    # The same changes sit uncommitted here, as when work is shipped from a worktree, plus a real one.
    for name in ("a", "c"):
        (shared / "docs/tasks/todo" / f"{name}.md").write_text((other / "docs/tasks/todo" / f"{name}.md").read_text())
    (shared / "docs/tasks/todo/b.md").unlink()
    run("new", "d", "--title", "D", cwd=shared)

    out = run("stale", "--fix", cwd=shared, check=False)
    assert out.returncode == 1
    assert "dropped docs/tasks/todo/a.md: same as origin/main" in out.stdout
    assert "dropped docs/tasks/todo/c.md: same as origin/main" in out.stdout
    assert "dropped docs/tasks/todo/b.md: deleted on origin/main too" in out.stdout
    assert "kept docs/tasks/todo/d.md: differs from origin/main" in out.stdout
    assert "uncommitted changes under docs" in out.stdout and "behind origin/main" in out.stdout
    assert (shared / "docs/tasks/todo/d.md").is_file()  # a real change is never dropped

    (shared / "docs/tasks/todo/d.md").unlink()
    assert run("stale", "--fix", cwd=shared).stdout.endswith("up to date with origin/main\n")
    assert git("status", "--porcelain", cwd=shared) == ""
    assert states(shared) == {"a": "todo", "c": "todo"}
    assert "Added on main." in (shared / "docs/tasks/todo/a.md").read_text()


def test_stale_fix_keeps_a_branch_where_it_is(shared, tmp_path):
    other = other_clone(tmp_path)
    run("new", "c", "--title", "C", cwd=other)
    commit_all(other, "plan c")
    git("push", "-q", cwd=other)
    git("switch", "-q", "-c", "feature", cwd=shared)
    out = run("stale", "--fix", cwd=shared, check=False)
    assert out.returncode == 1 and "on feature, not main: not fast-forwarding" in out.stdout


def test_stale_is_a_no_op_in_local_mode(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    assert run("stale", cwd=repo).stdout == "local mode: nothing to sync\n"


def test_dep_refuses_to_replan_claimed_work(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", cwd=repo)
    run("start", "a", cwd=repo)
    assert "a is in-progress: its prerequisites are fixed" in fails("dep", "add", "a", "b", cwd=repo)
    run("dep", "add", "b", "a", cwd=repo)  # depending on claimed work is fine


def test_done_in_the_code_repo_is_a_working_tree_move(shared):
    assert "not in-progress" in fails("done", "a", cwd=shared)
    run("start", "a", "--no-pr", cwd=shared)
    git("fetch", "-q", "origin", cwd=shared)
    git("merge", "-q", "--ff-only", "origin/claim/a", cwd=shared)

    dest = run("done", "a", cwd=shared).stdout.strip()
    assert Path(dest).parent.parent.name == "done" and Path(dest).is_file()
    assert git("status", "--porcelain", cwd=shared) != ""
    assert run("ready", cwd=shared).stdout == "b\ttodo\tB\t0\n"


def test_release_moves_a_claimed_task_back(shared, tmp_path):
    assert "not in-progress" in fails("release", "a", "--no-pr", cwd=shared)
    run("start", "a", "--no-pr", cwd=shared)
    git("fetch", "-q", "origin", cwd=shared)
    git("merge", "-q", "--ff-only", "origin/claim/a", cwd=shared)
    git("push", "-q", cwd=shared)

    run("release", "a", "--tech-debt", "--no-pr", cwd=shared)
    git("fetch", "-q", "origin", cwd=shared)
    git("merge", "-q", "--ff-only", "origin/release/a", cwd=shared)
    assert states(shared)["a"] == "tech-debt"
    assert "claimed:" not in (shared / "docs/tasks/tech-debt/a.md").read_text()


def test_ship_pushes_the_data_changes_on_a_branch_from_main(shared, tmp_path):
    bare = tmp_path / "remote.git"
    assert "no uncommitted changes under docs" in fails("ship", "--title", "Nothing", "--no-pr", cwd=shared)
    run("new", "c", "--title", "C", "--after", "a", cwd=shared)
    (shared / "docs/tasks/todo/a.md").write_text((shared / "docs/tasks/todo/a.md").read_text() + "\nMore.\n")
    run("rm", "b", cwd=shared)
    (shared / "README").write_text("outside the data root\n")
    before = git("status", "--porcelain", cwd=shared)

    assert run("ship", "--title", "Plan: c after a!", "--no-pr", cwd=shared).stdout == "pushed ship/plan-c-after-a\n"
    assert "ship/plan-c-after-a" in remote_branches(bare)
    tree = set(git("ls-tree", "-r", "--name-only", "ship/plan-c-after-a", cwd=bare).splitlines())
    assert "docs/tasks/todo/c.md" in tree and "docs/tasks/todo/b.md" not in tree and "README" not in tree
    assert "More." in git("show", "ship/plan-c-after-a:docs/tasks/todo/a.md", cwd=bare)
    assert git("status", "--porcelain", cwd=shared) == before  # untouched until the PR merges
    assert "--merge needs the PR" in fails("ship", "--title", "x", "--merge", "--no-pr", cwd=shared)

    # Once main has it, `stale --fix` drops the local copies and nothing but the README stays dirty.
    git("fetch", "-q", "origin", cwd=shared)
    git("push", "-q", "origin", "origin/ship/plan-c-after-a:main", cwd=shared)
    run("stale", "--fix", cwd=shared)
    assert git("status", "--porcelain", cwd=shared) == "?? README"
    assert states(shared) == {"a": "todo", "c": "todo"}


def test_ship_refuses_changes_that_fail_validation(shared, tmp_path):
    (shared / "docs/tasks/todo/c.md").write_text("---\ntitle: C\nafter: [ghost]\narch: []\n---\n")
    err = fails("ship", "--title", "Broken", "--no-pr", cwd=shared)
    assert "sdd validate` fails" in err and "unknown prerequisite ghost" in err
    assert "ship/broken" not in remote_branches(tmp_path / "remote.git")


def test_start_branch_switches_to_the_task_branch_in_a_clean_checkout(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    (repo / "x").write_text("x")
    assert "uncommitted changes" in fails("start", "a", "--branch", cwd=repo)
    assert states(repo)["a"] == "todo"  # refused before claiming
    (repo / "x").unlink()
    assert run("start", "a", "--branch", cwd=repo).stdout == "claimed a\non branch a from main\n"
    assert git("branch", "--show-current", cwd=repo) == "a"


def test_start_branch_in_shared_mode_needs_the_claim_on_main(shared):
    assert "needs the claim on main first" in fails("start", "a", "--branch", "--no-pr", cwd=shared)
    assert "--merge needs the claim PR" in fails("start", "a", "--merge", "--no-pr", cwd=shared)
    assert states(shared)["a"] == "todo"


def test_default_branch_is_asked_from_the_remote(tmp_path):
    repo = init_repo(tmp_path / "repo", branch="trunk")
    run("init", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    commit_all(repo)
    add_remote(repo, tmp_path / "remote.git", branch="trunk")
    assert "refs/remotes/origin/HEAD" not in git("for-each-ref", cwd=repo)

    run("start", "a", "--no-pr", cwd=repo)
    bare = tmp_path / "remote.git"
    assert git("merge-base", "--is-ancestor", "trunk", "claim/a", cwd=bare) == ""


def test_done_in_a_separate_data_repo_opens_a_branch_there(tmp_path):
    code = init_repo(tmp_path / "code")
    data = init_repo(tmp_path / "data")
    run("init", "../data", cwd=code)
    run("new", "a", "--title", "A", cwd=code)
    commit_all(data, "plan")
    add_remote(data, tmp_path / "data.git")
    assert run("root", cwd=code).stdout == f"{data}\nmode: shared\n"

    run("start", "a", "--no-pr", cwd=code)
    assert "claim/a" in remote_branches(tmp_path / "data.git")
    git("fetch", "-q", "origin", cwd=data)
    git("merge", "-q", "--ff-only", "origin/claim/a", cwd=data)
    git("push", "-q", cwd=data)

    assert run("done", "a", "--no-pr", cwd=code).stdout == "pushed done/a\n"
    assert "done/a" in remote_branches(tmp_path / "data.git")
    assert states(code)["a"] == "in-progress"  # the move lives on the branch, not in the checkout
    assert git("status", "--porcelain", cwd=data) == ""


def test_local_mode_claims_and_finishes_with_plain_moves(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    assert run("start", "a", cwd=repo).stdout == "claimed a\n"
    assert states(repo)["a"] == "in-progress"
    run("release", "a", cwd=repo)
    assert states(repo)["a"] == "todo"
    run("start", "a", cwd=repo)
    run("done", "a", cwd=repo)
    assert states(repo)["a"].startswith("done/")
    assert git("status", "--porcelain", cwd=repo) == ""


# --- blockers ------------------------------------------------------------------------------


def test_blockers_are_the_questions_that_alone_hold_up_a_task(repo):
    for slug, after in (("a", []), ("b", ["a"]), ("c", ["b"]), ("d", []), ("e", ["d"])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), cwd=repo)
    # Blocks `a`, which is otherwise ready, with b and c waiting behind it.
    fill_question(Path(run("ask", "key", "--title", "Per key?", "--blocks", "a", "--task", "a", cwd=repo).stdout.strip()))
    # Blocks `d`, otherwise ready, with only e behind it.
    fill_question(Path(run("ask", "ttl", "--title", "How long?", "--blocks", "d", "--task", "d", cwd=repo).stdout.strip()))
    # Blocks `c`, which waits on `b` anyway, so it isn't holding anything up yet.
    fill_question(Path(run("ask", "later", "--title", "Later?", "--blocks", "c", "--task", "c", cwd=repo).stdout.strip()))
    # Open but blocks nothing: counted, not listed.
    fill_question(Path(run("ask", "note", "--title", "Note?", "--task", "a", cwd=repo).stdout.strip()))

    out = run("blockers", cwd=repo).stdout.splitlines()
    assert out[0] == "open: 4"
    assert [line.split("\t")[:4] for line in out[1:]] == [["key", "Per key?", "a", "3"], ["ttl", "How long?", "d", "2"]]

    import json
    data = json.loads(run("blockers", "--json", cwd=repo).stdout)
    assert data["open"] == 4
    assert [(r["slug"], r["blocks"], r["downstream"]) for r in data["blockers"]] == [("key", ["a"], 3), ("ttl", ["d"], 2)]

    run("defer", "ttl", "--until", "a", cwd=repo)
    assert run("blockers", cwd=repo).stdout.startswith("open: 3\nkey\t")


def test_blockers_main_reads_the_remote_branch_not_the_checkout(shared):
    # On the remote: `a` is ready and nothing blocks it. Locally, an unpushed question blocks it.
    fill_question(Path(run("ask", "q", "--title", "Q?", "--blocks", "a", "--task", "a", cwd=shared).stdout.strip()))
    assert run("blockers", cwd=shared).stdout == "open: 1\nq\tQ?\ta\t2\t" + run("blockers", cwd=shared).stdout.split("\t")[-1]
    assert run("blockers", "--main", cwd=shared).stdout == "open: 0\n"
    commit_all(shared, "ask")
    git("push", "-q", "origin", "main", cwd=shared)
    assert run("blockers", "--main", cwd=shared).stdout.startswith("open: 1\nq\tQ?\ta\t2\t")


def test_main_flag_reads_the_remote_branch_for_read_only_commands(shared, repo, tmp_path):
    run("new", "c", "--title", "C", cwd=shared)
    assert "c\ttodo" in run("ready", cwd=shared).stdout
    assert "c\ttodo" not in run("--main", "ready", cwd=shared).stdout
    assert "unknown task: c" in fails("--main", "show", "c", cwd=shared)
    assert "read-only commands" in fails("--main", "new", "d", "--title", "D", cwd=shared)
    assert not (shared / "docs/tasks/todo/d.md").exists()

    run("init", "--local", tmp_path / "data", cwd=repo)
    assert "local mode" in fails("--main", "ready", cwd=repo)
