"""Drives the `sdd` CLI against throwaway git repos and bare remotes.

The CLI is the lowest layer here, so these tests cover its behavior in detail; `gh` is never
reached because every PR-opening command runs with `--no-pr`.
"""
import os
import shutil
import subprocess
import textwrap
from collections import namedtuple
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
    assert set(run("ready", cwd=repo).stdout.split("\n")[:-1]) == {"a\ttodo\t[WIP] fix [x]\t1\t", "td\ttech-debt\tDebt\t0\t"}
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
    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t2\t\nd\ttodo\tD\t0\t\n"


def test_ready_for_a_target_starts_its_longest_chain_first(repo):
    # a0 has less work behind it than b but a longer chain to t; x and b's extra work aren't on the way to t.
    for slug, after in (("a0", []), ("a1", ["a0"]), ("a", ["a1"]), ("b", []), ("b1", ["b"]), ("b2", ["b"]), ("b3", ["b"]),
                        ("t", ["a", "b1", "b2", "b3"]), ("x", []), ("bx1", ["b"]), ("bx2", ["b"])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), cwd=repo)
    r = run("ready", "--for", "t", cwd=repo)
    assert r.stdout == "a0\ttodo\tA0\t3\t\t4\nb\ttodo\tB\t4\t\t3\n"
    assert r.stderr == ""
    assert run("ready", "--for", "a0", cwd=repo).stdout == "a0\ttodo\tA0\t0\t\t1\n"
    assert "unknown task" in fails("ready", "--for", "zzz", cwd=repo)
    assert "unknown task" in fails("ready", "--for", "", cwd=repo)


def test_ready_for_a_target_names_what_finishing_ready_tasks_will_not_free(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    for slug, after, extra in (("a", [], []), ("b", [], ["--needs", "user"]), ("c", [], []), ("d", ["c"], []), ("t", ["a", "b", "d"], [])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), *extra, cwd=repo)
    fill_question(Path(run("ask", "q", "--title", "Q", "--task", "d", "--blocks", "d", cwd=repo).stdout.strip()))
    run("start", "a", cwd=repo)
    (tmp_path / "data/tasks/todo/c.md").write_text((tmp_path / "data/tasks/todo/c.md").read_text().replace("after: []", "after: [gone]"))
    r = run("ready", "--for", "t", cwd=repo)
    assert [line.split("\t")[0] for line in r.stdout.splitlines()] == ["b"]
    assert r.stderr == "t also waits on: a (in-progress); b (needs user); c (unknown prerequisite gone); d (question q)\n"
    (tmp_path / "data/tasks/todo/c.md").write_text((tmp_path / "data/tasks/todo/c.md").read_text().replace("after: [gone]", "after: []"))
    assert [line.split("\t")[0] for line in run("ready", "--for", "t", cwd=repo).stdout.splitlines()] == ["c", "b"]
    run("done", "a", cwd=repo)
    run("start", "b", cwd=repo)
    run("done", "b", cwd=repo)
    assert run("ready", "--for", "t", cwd=repo).stderr == "t also waits on: d (question q)\n"
    assert run("ready", "--for", "a", cwd=repo).stderr == "a is already done\n"
    run("start", "c", cwd=repo)
    assert run("ready", "--for", "c", cwd=repo).stderr == "c itself: in-progress\n"


def test_ready_for_a_target_takes_the_longest_of_several_paths_and_stops_at_done_tasks(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    # r reaches t through a -> c and through b: its chain is the longer path, not their sum.
    for slug, after in (("r", []), ("a", ["r"]), ("b", ["r"]), ("c", ["a"]), ("t", ["b", "c"]), ("p", []), ("m", []), ("u", ["m"])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), cwd=repo)
    assert run("ready", "--for", "t", cwd=repo).stdout == "r\ttodo\tR\t4\t\t4\n"
    # A done task keeps its `after:` as history: what it once waited on isn't on the way to u.
    run("start", "m", cwd=repo)
    run("done", "m", cwd=repo)
    done_m = next((tmp_path / "data/tasks/done").glob("*/m.md"))
    done_m.write_text(done_m.read_text().replace("after: []", "after: [p]"))
    assert run("ready", "--for", "u", cwd=repo).stdout == "u\ttodo\tU\t0\t\t1\n"


def test_ready_reports_a_dependency_cycle_instead_of_crashing(repo):
    for slug, after in (("a", []), ("b", ["a"]), ("t", ["b"]), ("x", [])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), cwd=repo)
    path = repo / "docs/tasks/todo/a.md"
    path.write_text(path.read_text().replace("after: []", "after: [b]"))  # a hand edit; `sdd dep add` rejects it
    r = run("ready", cwd=repo)
    assert r.stdout == "x\ttodo\tX\t0\t\n"
    assert "dependency cycle: a -> b -> a" in r.stderr
    assert fails("ready", "--for", "t", cwd=repo) == "sdd: dependency cycle: a -> b -> a\n"


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
    assert "tasks/todo/b.md" not in out and "=== goal" not in out
    assert out.rstrip().endswith("=== review checks (sdd checks --task)\n\n" + f"{adr.stem}\t\tStore\n  - Every key has a TTL.")

    review = run("brief", "a", "--review", cwd=repo).stdout
    assert "=== dependent task: tasks/todo/b.md" in review and "=== goal: goal.md" in review
    assert review.rstrip().endswith("  - Every key has a TTL.")
    assert "unknown task" in fails("brief", "zzz", cwd=repo)


# Architecture decisions and business rules share one engine: the record tests run for both kinds.
Kind = namedtuple("Kind", "cmd dir label listing frozen")
KINDS = [Kind("adr", "arch", "architecture decision", ["adrs"], "Decision"),
         Kind("rule", "rules", "business rule", ["rules", "--all"], "Rule")]
each_kind = pytest.mark.parametrize("kind", KINDS, ids=[k.cmd for k in KINDS])


def record(repo, kind, slug, *args):
    return Path(run(kind.cmd, slug, *args, cwd=repo).stdout.strip()).stem


@each_kind
def test_accept_marks_proposed_records_accepted(repo, kind):
    name = record(repo, kind, "store", "--title", "Store")
    path = repo / f"docs/{kind.dir}/{name}.md"
    assert run("accept", name, cwd=repo).stdout == f"accepted {name}\n"
    assert "status: accepted" in path.read_text()
    assert "not proposed" in fails("accept", name, cwd=repo)
    assert "unknown architecture decision or business rule" in fails("accept", "nope", cwd=repo)


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
    assert run("validate", cwd=repo).stdout.endswith("ok: 2 tasks, 1 dependencies, 0 architecture decisions, 0 business rules, 0 open questions, 0 open ideas\n")

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
    assert f"tasks: [a]\narch: [{adr}]\nrules: []\nblocks: [b]\nasked: " in path.read_text()

    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t0\t\n"
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
    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t0\t\nb\ttodo\tB\t0\t\n"
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
    assert "links to no task, architecture decision or business rule" in run("validate", cwd=repo).stdout


def test_a_claimed_task_may_be_held_by_a_question_but_not_a_done_one(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", cwd=repo)
    run("start", "a", cwd=repo)
    fill_question(Path(run("ask", "q", "--title", "Q", "--blocks", "a", "b", "--task", "a", cwd=repo).stdout.strip()))
    assert "blocked by open questions" not in run("validate", cwd=repo).stdout  # held for a decision, by design
    assert "b is waiting on: question q" in fails("start", "b", cwd=repo)
    run("done", "a", cwd=repo)
    assert "a is done but blocked by open questions: q" in run("validate", cwd=repo).stdout


# --- ADRs, specs and context ---------------------------------------------------------------


def adr(repo, slug, *args):
    return next((repo / "docs/arch").glob(f"*-{slug}.md")).stem if not args else Path(run("adr", slug, *args, cwd=repo).stdout.strip()).stem


@each_kind
def test_records_amend_and_supersede(repo, kind):
    old = record(repo, kind, "limits", "--title", "Limits in memory", "--areas", "backend/rate-limiting")
    path = repo / f"docs/{kind.dir}/{old}.md"
    text = path.read_text()
    assert text.startswith(f"---\ntitle: Limits in memory\nstatus: proposed\ndate: ") and "areas: [backend/rate-limiting]" in text
    assert f"\n## {kind.frozen}\n" in text

    amend = record(repo, kind, "limits-keys", "--title", "Limits keyed per API key", "--areas", "backend/rate-limiting", "--amends", old)
    assert f"amended-by: [{amend}]" in path.read_text() and "status: proposed" in path.read_text()
    new = record(repo, kind, "limits-redis", "--title", "Limits in Redis", "--supersedes", old)
    assert f"superseded-by: [{new}]" in path.read_text() and "status: superseded" in path.read_text()
    assert f"unknown {kind.label}" in fails(kind.cmd, "x", "--title", "x", "--amends", "nope", cwd=repo)
    assert "already exists" in fails("rule" if kind.cmd == "adr" else "adr", "limits", "--title", "x", cwd=repo)

    out = run(*kind.listing, cwd=repo).stdout
    assert f"{old}\tsuperseded\t0\tbackend/rate-limiting\tLimits in memory" in out
    assert run(*kind.listing, "--area", "backend", cwd=repo).stdout.count("\n") == 2
    assert run("areas", cwd=repo).stdout == "2\tbackend/rate-limiting\n"


def test_rules_lists_the_rules_in_force(repo):
    old = record(repo, KINDS[1], "cap", "--title", "At most 3 pictures a day")
    new = record(repo, KINDS[1], "cap-five", "--title", "At most 5 pictures a day", "--supersedes", old)
    assert [line.split("\t")[0] for line in run("rules", cwd=repo).stdout.splitlines()] == [new]


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


def test_context_finds_the_adrs_cited_in_the_code_a_feature_touches(repo, tmp_path):
    cited = adr(repo, "ttl", "--title", "Keys expire", "--areas", "backend")
    other = adr(repo, "unrelated", "--title", "Unrelated", "--areas", "backend")
    src = repo / "src/store"
    src.mkdir(parents=True)
    (src / "cache.py").write_text(f"TTL = 60  # every key expires (adr: {cited})\n# stale (adr: 2020-01-01-gone)\n")
    (repo / ".gitignore").write_text("build/\n")
    (repo / "src/build").mkdir()
    (repo / "src/build/x.py").write_text(f"# adr: {other}\n")

    for path in ("src", "src/store/cache.py"):
        out = run("context", "--path", path, cwd=repo).stdout
        matching = out.split("matching ADRs:")[1].split("matching business rules:")[0]
        assert f"  {cited}\tproposed\t0 refs\tKeys expire (cited in the code)" in matching
        assert other not in matching
        assert "cited in the code but unknown (renamed or never written?): adr: 2020-01-01-gone" in out
    assert "no such file or directory" in fails("context", "--path", "nope", cwd=repo)

    outside = tmp_path / "outside"  # not a git repo: the files are walked, binaries skipped
    (outside / ".hidden").mkdir(parents=True)
    (outside / "a.py").write_text(f"# adr: {cited}\n")
    (outside / "b.bin").write_bytes(f"\0adr: {other}\n".encode())
    (outside / ".hidden/c.py").write_text(f"# adr: {other}\n")
    matching = run("context", "--path", outside, cwd=repo).stdout.split("matching ADRs:")[1].split("matching business rules:")[0]
    assert cited in matching and other not in matching


def test_feature_spec_has_the_planning_sections(repo):
    path = Path(run("spec", "export", "--title", "Export", "--areas", "cli", "--feature", cwd=repo).stdout.strip())
    assert path.read_text().endswith("# Export\n\n## Goal\n\n## How it works\n\n## Shape\n")
    assert "## Goal" not in Path(run("spec", "plain", "--title", "Plain", cwd=repo).stdout.strip()).read_text()


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


def test_repeated_list_flags_accumulate(repo):
    for slug in ("a", "b"):
        run("new", slug, "--title", slug.upper(), cwd=repo)
    x, y = adr(repo, "x", "--title", "X"), adr(repo, "y", "--title", "Y")
    path = Path(run("ask", "q", "--title", "Q", "--task", "a", "--task", "b", "--arch", x, "--arch", y, cwd=repo).stdout.strip())
    assert f"tasks: [a, b]\narch: [{x}, {y}]" in path.read_text()
    run("new", "c", "--title", "C", "--after", "a", "--after", "b", cwd=repo)
    assert "after: [a, b]" in (repo / "docs/tasks/todo/c.md").read_text()


def test_link_edits_questions_and_adrs_too(repo):
    for slug in ("a", "b"):
        run("new", slug, "--title", slug.upper(), cwd=repo)
    old, new = adr(repo, "old", "--title", "Old"), adr(repo, "new", "--title", "New")
    run("accept", old, cwd=repo)
    q = Path(run("ask", "q", "--title", "Q", "--task", "a", cwd=repo).stdout.strip())
    fill_question(q)

    run("link", "q", "--task", "b", "--blocks", "b", "--arch", old, cwd=repo)
    assert f"tasks: [a, b]\narch: [{old}]\nrules: []\nblocks: [b]" in q.read_text()
    assert "ready: no, waiting on question q" in run("show", "b", cwd=repo).stdout

    run("link", new, "--amends", old, cwd=repo)
    assert f"amends: [{old}]" in (repo / f"docs/arch/{new}.md").read_text()
    old_text = (repo / f"docs/arch/{old}.md").read_text()
    assert f"amended-by: [{new}]" in old_text and "status: accepted" in old_text
    run("validate", cwd=repo)  # an accepted ADR takes frontmatter links

    assert "doesn't apply to a question" in fails("link", "q", "--spec", "s", cwd=repo)
    assert "doesn't apply to a task" in fails("link", "a", "--blocks", "b", cwd=repo)
    assert "can't amend itself" in fails("link", new, "--amends", new, cwd=repo)
    assert "unknown task, question, idea, spec, architecture decision or business rule" in fails("link", "zzz", "--arch", old, cwd=repo)
    assert "nothing to link" in fails("link", "a", cwd=repo)
    run("new", "q", "--title", "Task named like the question", cwd=repo)
    assert "pass --as task|question" in fails("link", "q", "--arch", new, cwd=repo)
    run("link", "q", "--as", "task", "--arch", new, cwd=repo)
    assert f"arch: [{new}]" in (repo / "docs/tasks/todo/q.md").read_text()


def test_needs_marks_tasks_an_agent_cannot_do_alone(repo):
    run("new", "smoke", "--title", "Live smoke", "--needs", "user", "secret", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    assert "needs: [user, secret]" in (repo / "docs/tasks/todo/smoke.md").read_text()
    assert run("ready", cwd=repo).stdout == "a\ttodo\tA\t0\t\nsmoke\ttodo\tLive smoke\t0\tuser,secret\n"
    assert "needs: user, secret" in run("show", "smoke", cwd=repo).stdout
    assert "needs:" not in run("show", "a", cwd=repo).stdout


def test_questions_since_lists_what_a_run_raised(shared):
    fill_question(Path(run("ask", "before", "--title", "Before", "--task", "a", cwd=shared).stdout.strip()))
    commit_all(shared, "ask before")
    start = git("rev-parse", "HEAD", cwd=shared)
    fill_question(Path(run("ask", "during", "--title", "During", "--task", "a", cwd=shared).stdout.strip()))
    commit_all(shared, "ask during")
    assert [l.split("\t")[0] for l in run("questions", "--since", start, cwd=shared).stdout.splitlines()] == ["during"]
    assert "bad revision" in fails("questions", "--since", "nope", cwd=shared)


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


# --- ideas ---------------------------------------------------------------------------------


def fill_idea(path, idea="SSO through the identity provider.", context="Came up in login; see auth.py.", outcome=""):
    text = path.read_text().split("\n## Idea")[0]
    path.write_text(f"{text}\n## Idea\n\n{idea}\n\n## Context\n\n{context}\n\n## Outcome\n\n{outcome}\n")


def test_ideas_are_never_startable_and_wait_on_their_prerequisites(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "login", "--title", "Login", cwd=repo)
    path = Path(run("idea", "sso", "--title", "SSO", "--areas", "backend/auth", "--after", "login", "--task", "login", cwd=repo).stdout.strip())
    assert path == tmp_path / "data/ideas/open/sso.md"
    assert "areas: [backend/auth]\nafter: [login]\ntasks: [login]\narch: []\nrules: []\nraised: " in path.read_text()
    fill_idea(path)
    assert "already exists" in fails("idea", "sso", "--title", "x", cwd=repo)
    assert "unknown task" in fails("idea", "other", "--title", "x", "--after", "zzz", cwd=repo)

    assert [line.split("\t")[0] for line in run("ready", cwd=repo).stdout.splitlines()] == ["login"]
    assert run("ideas", cwd=repo).stdout.startswith("sso\twaiting on login\tSSO\tbackend/auth\t20")
    assert run("ideas", "--ready", cwd=repo).stdout == ""

    fill_idea(Path(run("idea", "audit", "--title", "Audit", "--areas", "backend", cwd=repo).stdout.strip()))
    fill_idea(Path(run("idea", "themes", "--title", "Themes", "--areas", "web", cwd=repo).stdout.strip()))
    old = tmp_path / "data/ideas/open/themes.md"
    old.write_text(old.read_text().replace("raised: 20", "raised: 19"))
    assert [line.split("\t")[0] for line in run("ideas", cwd=repo).stdout.splitlines()] == ["themes", "audit", "sso"]
    assert [line.split("\t")[0] for line in run("ideas", "--area", "backend", cwd=repo).stdout.splitlines()] == ["audit", "sso"]

    run("start", "login", cwd=repo)
    run("done", "login", cwd=repo)
    assert run("ideas", "--ready", "--area", "backend/auth", cwd=repo).stdout.startswith("sso\tready\tSSO")


def test_close_idea_needs_an_outcome_and_records_what_it_became(repo):
    run("new", "login", "--title", "Login", cwd=repo)
    path = Path(run("idea", "sso", "--title", "SSO", "--areas", "backend", cwd=repo).stdout.strip())
    fill_idea(path)
    assert "under `## Outcome` first" in fails("close-idea", "sso", cwd=repo)
    assert "unknown task, architecture decision, business rule or spec" in fails("close-idea", "sso", "--into", "zzz", cwd=repo)

    fill_idea(path, outcome="Planned as login.")
    run("close-idea", "sso", "--into", "login", cwd=repo)
    closed = repo / "docs/ideas/closed/sso.md"
    assert not path.exists() and "into: [login]" in closed.read_text() and "closed: " in closed.read_text()
    assert run("ideas", cwd=repo).stdout == ""
    assert run("ideas", "--all", cwd=repo).stdout.startswith("sso\tclosed\tSSO")
    assert "already closed" in fails("close-idea", "sso", cwd=repo)
    assert "is closed" in fails("dep", "add", "sso", "login", cwd=repo)
    run("validate", cwd=repo)


def test_validate_requires_ideas_to_stand_alone(repo):
    shutil.rmtree(repo / "docs/ideas")  # set up before ideas existed: their directories aren't required yet
    run("validate", cwd=repo)

    path = Path(run("idea", "sso", "--title", "SSO", cwd=repo).stdout.strip())
    out = run("validate", cwd=repo, check=False).stdout
    assert "empty `## Idea` section" in out and "empty `## Context` section" in out

    fill_idea(path)
    out = run("validate", cwd=repo).stdout
    assert "no areas, so `sdd context` won't show it" in out and "1 open ideas" in out

    path.write_text("---\ntitle: SSO\nareas: [x]\nafter: [ghost]\ntasks: []\narch: [nope]\ninto: [gone]\n---\n\n## Idea\n\nI\n\n## Context\n\nC\n")
    out = run("validate", cwd=repo, check=False).stdout
    for msg in ("unknown task ghost in after", "unknown architecture decision nope", "unknown task, architecture decision, business rule or spec gone in into"):
        assert msg in out, msg

    (repo / "docs/ideas/closed").mkdir(exist_ok=True)
    path.rename(repo / "docs/ideas/closed/sso.md")
    assert "closed without an `## Outcome`" in run("validate", cwd=repo, check=False).stdout


def test_context_lists_the_ideas_in_the_areas_being_planned(repo):
    auth = adr(repo, "sessions", "--title", "Sessions", "--areas", "backend/auth")
    fill_idea(Path(run("idea", "sso", "--title", "SSO", "--areas", "backend/auth", cwd=repo).stdout.strip()))
    fill_idea(Path(run("idea", "expiry", "--title", "Expiry", "--arch", auth, cwd=repo).stdout.strip()))
    fill_idea(Path(run("idea", "themes", "--title", "Themes", "--areas", "web", cwd=repo).stdout.strip()), idea="Dark mode via redis-backed prefs.")

    ideas = run("context", "--area", "backend", cwd=repo).stdout.split("ideas in these areas")[1]
    assert "  sso\tready\tSSO" in ideas and "  expiry\tready\tExpiry" in ideas and "themes" not in ideas
    assert "  themes\tready" in run("context", "--grep", "redis", cwd=repo).stdout.split("ideas in these areas")[1]


def test_dep_and_link_edit_ideas_and_rm_keeps_their_prerequisites(repo):
    for slug in ("a", "b"):
        run("new", slug, "--title", slug.upper(), cwd=repo)
    x = adr(repo, "x", "--title", "X")
    path = Path(run("idea", "i", "--title", "I", cwd=repo).stdout.strip())

    run("dep", "add", "i", "a", "b", cwd=repo)
    assert "after: [a, b]" in path.read_text()
    run("dep", "rm", "i", "b", cwd=repo)
    assert "after: [a]" in path.read_text()
    assert "unknown task" in fails("dep", "add", "i", "zzz", cwd=repo)
    assert "ideas wait on a: i" in fails("rm", "a", cwd=repo)

    run("link", "i", "--task", "b", "--arch", x, "--areas", "web", cwd=repo)
    text = path.read_text()
    assert "areas: [web]" in text and "tasks: [b]" in text and f"arch: [{x}]" in text
    assert "doesn't apply to an idea" in fails("link", "i", "--blocks", "a", cwd=repo)


def test_validate_flags_adrs_that_read_as_specs(repo):
    a = adr(repo, "big", "--title", "Big", "--areas", "x")
    path = repo / f"docs/arch/{a}.md"
    path.write_text(path.read_text() + "filler\n" * 100)
    out = run("validate", cwd=repo).stdout
    assert "over 100 lines" in out and "no alternatives" not in out
    # Accepted, the body is history: the length can't be fixed any more, so it isn't nagged about.
    path.write_text(path.read_text().replace("status: proposed", "status: accepted"))
    out = run("validate", cwd=repo).stdout
    assert "over 100 lines" not in out and "no alternatives considered" in out
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


@each_kind
def test_validate_refuses_edits_to_accepted_record_bodies(shared, kind):
    a = record(shared, kind, "fixed", "--title", "Fixed", "--areas", "x")
    path = shared / f"docs/{kind.dir}/{a}.md"
    path.write_text(path.read_text().replace("status: proposed", "status: accepted")
                    .replace("## Alternatives considered\n", "## Alternatives considered\n\nnone really\n")
                    .replace("## Rule\n", "## Rule\n\nA user posts at most 3 pictures a day.\n"))
    commit_all(shared, "accept")
    git("push", "-q", cwd=shared)
    assert "body changed" not in run("validate", cwd=shared).stdout

    path.write_text(path.read_text() + "\n## Errata\n\n- 2026-10-30: the variable is TURNOS_ENV.\n")
    path.write_text(path.read_text().replace("areas: [x]", "areas: [x, y]"))
    path.write_text(path.read_text() + "\n## Review checks\n\n- The variable is read once at startup.\n")
    assert "body changed" not in run("validate", cwd=shared).stdout

    path.write_text(path.read_text().replace(f"## {kind.frozen}\n", f"## {kind.frozen}\n\nchanged my mind\n"))
    assert "body changed since origin/main" in run("validate", cwd=shared, check=False).stdout


# --- business rules ------------------------------------------------------------------------


def fill_rule(repo, name, text="A user posts at most 3 pictures a day."):
    path = repo / f"docs/rules/{name}.md"
    path.write_text(path.read_text().replace("## Rule\n", f"## Rule\n\n{text}\n"))
    return path


def test_rules_link_like_adrs_and_reach_workers(repo):
    cap = record(repo, KINDS[1], "cap", "--title", "At most 3 pictures a day", "--areas", "posting")
    path = fill_rule(repo, cap)
    path.write_text(path.read_text() + "\n## Review checks\n\n- Every path that creates a post goes through the cap.\n")
    run("new", "upload", "--title", "Upload", "--rule", cap, cwd=repo)
    assert f"rules: [{cap}]" in (repo / "docs/tasks/todo/upload.md").read_text()
    assert "unknown business rule" in fails("new", "x", "--title", "X", "--rule", "nope", cwd=repo)
    assert "unknown business rule" in fails("new", "x", "--title", "X", "--rule", adr(repo, "a", "--title", "A"), cwd=repo)

    out = run("brief", "upload", cwd=repo).stdout
    assert f"rules:\n  {path}" in out and f"=== business rule: rules/{cap}.md" in out
    assert out.rstrip().endswith(f"{cap}\tposting\tAt most 3 pictures a day\n  - Every path that creates a post goes through the cap.")

    run("new", "scheduler", "--title", "Scheduler", cwd=repo)
    run("ask", "q", "--title", "Q", "--task", "scheduler", cwd=repo)
    fill_idea(Path(run("idea", "auto", "--title", "Auto-post", "--areas", "scheduler", cwd=repo).stdout.strip()))
    run("spec", "auto", "--title", "Auto-post", "--areas", "scheduler", "--feature", cwd=repo)
    for slug, as_ in (("scheduler", "task"), ("q", "question"), ("auto", "idea"), ("auto", "spec")):
        run("link", slug, "--as", as_, "--rule", cap, cwd=repo)
    for f in ("tasks/todo/scheduler.md", "questions/open/q.md", "ideas/open/auto.md", "specs/auto.md"):
        assert f"rules: [{cap}]" in (repo / "docs" / f).read_text(), f
    assert "doesn't apply to a rule" in fails("link", cap, "--rule", cap, cwd=repo)
    assert "q\topen\tQ" in run("questions", "--rule", cap, cwd=repo).stdout
    assert run("checks", "--task", "scheduler", cwd=repo).stdout.startswith(f"{cap}\tposting\t")


def test_context_lists_business_rules_from_any_area(repo):
    cap = record(repo, KINDS[1], "cap", "--title", "At most 3 pictures a day", "--areas", "posting")
    fill_rule(repo, cap)
    other = record(repo, KINDS[1], "names", "--title", "Display names are unique", "--areas", "accounts")
    run("new", "upload", "--title", "Upload", "--rule", cap, cwd=repo)
    (repo / "src").mkdir()
    (repo / "src/posts.py").write_text(f"def create(): ...  # at most 3 a day (rule: {cap})\n")

    out = run("context", "--area", "scheduler", cwd=repo).stdout
    assert f"other business rules (a feature in any area may have to respect them):\n  {cap}\t" in out
    assert f"  {other}\t" in out.split("other business rules")[1]

    out = run("context", "--path", "src", cwd=repo).stdout
    matching = out.split("matching business rules:")[1].split("other business rules")[0]
    assert f"  {cap}\tproposed\t1 refs\tAt most 3 pictures a day (cited in the code)" in matching
    assert "  upload\ttodo\tUpload" in out.split("tasks referencing")[1]

    five = record(repo, KINDS[1], "cap-five", "--title", "At most 5 pictures a day", "--areas", "posting", "--supersedes", cap)
    matching = run("context", "--path", "src", cwd=repo).stdout.split("matching business rules:")[1].split("other business rules")[0]
    assert f"  {cap}\tsuperseded\t1 refs\tAt most 3 pictures a day (superseded-by {five}) (cited in the code)" in matching

    for i in range(15):
        record(repo, KINDS[1], f"r{i}", "--title", f"R{i}", "--areas", "billing")
    out = run("context", "--area", "posting", cwd=repo).stdout
    assert f"  {five}\t" in out.split("matching business rules:")[1].split("other business rules")[0]
    assert "  16 more, by area (`sdd rules --area <area>`): accounts 1, billing 15" in out


def test_validate_checks_rules_and_the_code_citing_records(repo):
    cap = record(repo, KINDS[1], "cap", "--title", "Cap", "--areas", "posting")
    assert "empty `## Rule` section" in run("validate", cwd=repo).stdout
    path = repo / f"docs/rules/{cap}.md"
    path.write_text(path.read_text().replace("status: proposed", "status: accepted"))
    assert f"error: {path}: empty `## Rule` section" in run("validate", cwd=repo, check=False).stdout
    fill_rule(repo, cap)
    new = record(repo, KINDS[1], "cap-five", "--title", "Cap of five", "--areas", "posting", "--supersedes", cap)
    fill_rule(repo, new, "A user posts at most 5 pictures a day.")

    (repo / "src").mkdir()
    (repo / "src/posts.py").write_text(f"# rule: {cap}\n# rule: 2020-01-01-gone\n# adr: {new}\n")
    (repo / "docs/notes.md").write_text("# rule: 2020-01-01-in-the-data-root\n")
    (repo / "src/cache.pyc").write_bytes(b"\0\0rule: 2020-01-01-in-a-binary\n")
    out = run("validate", cwd=repo).stdout
    assert f"src/posts.py:1: cites rule: {cap}, superseded by {new}" in out
    assert "src/posts.py:2: cites rule: 2020-01-01-gone, which doesn't exist" in out
    assert f"src/posts.py:3: cites adr: {new}, which is a business rule; cite it as `rule: {new}`" in out
    assert "in-the-data-root" not in out and "in-a-binary" not in out

    (repo / "docs/tasks/todo/t.md").write_text("---\ntitle: T\nafter: []\narch: []\nrules: [ghost]\n---\n")
    (repo / "docs/tasks/todo/u.md").write_text(f"---\ntitle: U\nafter: []\narch: [{cap}]\nrules: []\n---\n")
    (repo / "docs/arch").mkdir(exist_ok=True)
    (repo / f"docs/arch/{new}.md").write_text((repo / f"docs/rules/{new}.md").read_text())
    out = run("validate", cwd=repo, check=False).stdout
    assert "unknown business rule ghost" in out and "names are unique across ADRs and business rules" in out
    assert f"u.md: unknown architecture decision {cap}" in out


def test_validate_warns_about_empty_feature_specs(repo):
    path = Path(run("spec", "export", "--title", "Export", "--areas", "cli", "--feature", cwd=repo).stdout.strip())
    out = run("validate", cwd=repo).stdout
    assert "empty `## Goal` section" in out and "empty `## How it works` section" in out
    path.write_text(path.read_text().replace("## Goal\n", "## Goal\n\nG\n").replace("## How it works\n", "## How it works\n\nH\n"))
    assert "empty `## Goal`" not in run("validate", cwd=repo).stdout


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
    assert run("ready", cwd=shared).stdout == "b\ttodo\tB\t0\t\n"


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


def test_start_branch_fails_instead_of_branching_from_a_stale_main(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    run("new", "a", "--title", "A", cwd=repo)
    run("new", "b", "--title", "B", cwd=repo)
    git("remote", "add", "origin", str(tmp_path / "missing.git"), cwd=repo)
    err = fails("start", "a", "--branch", cwd=repo)
    assert "could not fetch origin/main" in err and "stale main" in err
    assert git("branch", "--show-current", cwd=repo) == "main"
    assert states(repo)["a"] == "in-progress"  # the claim stands; only the branch is missing

    git("remote", "remove", "origin", cwd=repo)
    add_remote(repo, tmp_path / "remote.git")
    assert run("start", "b", "--branch", cwd=repo).stdout == "claimed b\non branch b from origin/main\n"


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


def test_blockers_include_claimed_tasks_held_for_an_answer(repo, tmp_path):
    run("init", "--local", tmp_path / "data", cwd=repo)
    for slug, after in (("a", []), ("b", ["a"]), ("c", [])):
        run("new", slug, "--title", slug.upper(), *(["--after", *after] if after else []), cwd=repo)
    run("start", "a", cwd=repo)
    # The worker built `a` and found a decision only the user can make: the PR waits, and so does b.
    fill_question(Path(run("ask", "shape", "--title", "Shape?", "--blocks", "a", "--task", "a", cwd=repo).stdout.strip()))
    fill_question(Path(run("ask", "later", "--title", "Later?", "--blocks", "b", "--task", "b", cwd=repo).stdout.strip()))  # b waits on a anyway
    out = run("blockers", cwd=repo).stdout.splitlines()
    assert out == ["open: 2", "shape\tShape?\ta (in-progress)\t2\t" + out[1].split("\t")[-1]]
    import json
    row = json.loads(run("blockers", "--json", cwd=repo).stdout)["blockers"][0]
    assert (row["blocks"], row["held"], row["downstream"]) == (["a"], ["a"], 2)
    fill_question(tmp_path / "data/questions/open/shape.md", answer="Round.")
    run("answer", "shape", cwd=repo)
    assert run("blockers", cwd=repo).stdout == "no question alone blocks a task (1 open)\n"


def test_blockers_main_reads_the_remote_branch_not_the_checkout(shared):
    # On the remote: `a` is ready and nothing blocks it. Locally, an unpushed question blocks it.
    fill_question(Path(run("ask", "q", "--title", "Q?", "--blocks", "a", "--task", "a", cwd=shared).stdout.strip()))
    assert run("blockers", cwd=shared).stdout == "open: 1\nq\tQ?\ta\t2\t" + run("blockers", cwd=shared).stdout.split("\t")[-1]
    assert run("blockers", "--main", cwd=shared).stdout == "no question alone blocks a task (0 open)\n"
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
