import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "pull-pr-description"

# Stands in for the few gh calls the script makes, over PRs kept in a JSON file. `pr edit` resolves
# --attach paths from its working directory and rewrites the body's references to them, as gh does.
FAKE_GH = r'''
import json, os, sys
path = os.environ["FAKE_GH_STATE"]
state = json.load(open(path))
args = sys.argv[1:]

def find(ref):
    for n, pr in state["prs"].items():
        if ref in (n, pr["branch"], f"{state['repo']}/pull/{n}"):
            return n, pr
    return None, None

if args[:2] == ["pr", "view"]:
    n, pr = find(args[2])
    if pr is None:
        sys.exit(print(f'no pull requests found for branch "{args[2]}"', file=sys.stderr) or 1)
    sys.stdout.write(f"{state['repo']}/pull/{n}\n{pr['branch']}\n{pr['body']}")
elif args[:2] == ["repo", "view"]:
    print(state["repo"])
elif args[:2] == ["pr", "edit"]:
    n, pr = find(args[2])
    body = open(args[args.index("--body-file") + 1]).read()
    for i, a in enumerate(args):
        if a == "--attach":
            f = args[i + 1]
            if not os.path.isfile(f):
                sys.exit(print(f"no such file: {f}", file=sys.stderr) or 1)
            body = body.replace(f"({f})", f"(https://assets/{os.path.basename(f)})")
    pr["body"] = body
    state["edits"].append({"cwd": os.getcwd(), "args": args})
    json.dump(state, open(path, "w"))
else:
    sys.exit(f"unexpected gh call: {args}")
'''


@pytest.fixture
def gh(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(f"#!{sys.executable}\n{FAKE_GH}")
    (bin_dir / "gh").chmod(0o755)
    state_file = tmp_path / "gh-state.json"
    (tmp_path / "tmp").mkdir()

    class Gh:
        def __init__(self):
            self.save({"repo": "https://github.com/o/r", "prs": {}, "edits": []})

        def state(self):
            return json.loads(state_file.read_text())

        def save(self, state):
            state_file.write_text(json.dumps(state))

        def set_pr(self, number, branch, body):
            state = self.state()
            state["prs"][str(number)] = {"branch": branch, "body": body}
            self.save(state)

        def run(self, *args):
            env = {"PATH": f"{bin_dir}:{os.environ['PATH']}", "TMPDIR": str(tmp_path / "tmp"), "FAKE_GH_STATE": str(state_file)}
            r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=30)
            out = dict(line.split(": ", 1) for line in r.stdout.splitlines())
            return r.returncode, out.get("status"), Path(out["path"]) if "path" in out else None, r.stderr

    return Gh()


def test_a_body_written_before_the_pr_exists_is_found_on_the_same_file_after(gh, tmp_path):
    code, status, path, _ = gh.run("feat/x")
    assert (code, status) == (0, "none")
    assert path == tmp_path / "tmp/prs/o/r/feat/x/description.md"
    path.write_text("Adds x.\n")
    assert gh.run("feat/x")[1:3] == ("none", path)
    assert path.read_text() == "Adds x.\n"

    gh.set_pr(7, "feat/x", "Adds x.")  # what `gh pr create --body-file <path>` leaves on GitHub
    assert gh.run("7")[1:3] == ("unchanged", path)


def test_parallel_branches_get_their_own_copies(gh):
    gh.set_pr(7, "feat/x", "Adds x.")
    gh.set_pr(8, "feat/y", "Adds y.")
    _, _, x, _ = gh.run("7")
    _, _, y, _ = gh.run("8")
    assert x.parent != y.parent
    assert (x.read_text(), y.read_text()) == ("Adds x.", "Adds y.")


def test_a_github_change_replaces_an_unedited_copy_and_conflicts_with_an_edited_one(gh):
    gh.set_pr(7, "feat/x", "One.")
    _, _, path, _ = gh.run("7")
    gh.set_pr(7, "feat/x", "Two.")
    assert gh.run("7")[1] == "updated"
    assert path.read_text() == "Two."

    path.write_text("Local.")
    gh.set_pr(7, "feat/x", "Three.")
    assert gh.run("7")[1] == "conflict"
    assert path.read_text() == "Local."


def test_push_sends_edits_from_the_files_folder_and_keeps_githubs_rewritten_version(gh):
    gh.set_pr(7, "feat/x", "Adds x.")
    _, _, path, _ = gh.run("7")
    path.write_text("Adds x.\n\n![The page](./shot.png)\n")
    (path.parent / "shot.png").write_bytes(b"png")

    code, status, _, err = gh.run("--push", "7", "--attach", "./shot.png")
    assert (code, status) == (0, "pushed"), err
    assert gh.state()["edits"][0]["cwd"] == str(path.parent)
    assert "(https://assets/shot.png)" in gh.state()["prs"]["7"]["body"]
    assert "(https://assets/shot.png)" in path.read_text()
    assert gh.run("7")[1] == "unchanged"


def test_push_refuses_a_conflict_until_the_file_is_edited(gh, tmp_path):
    gh.set_pr(7, "feat/x", "One.")
    _, _, path, _ = gh.run("7")
    path.write_text("Local.")
    gh.set_pr(7, "feat/x", "Two.")

    for _ in range(2):
        code, status, _, _ = gh.run("--push", "7")
        assert (code, status) == (1, "conflict")
    assert gh.state()["edits"] == []
    assert gh.state()["prs"]["7"]["body"] == "Two."
    assert (tmp_path / "tmp/prs/o/r/feat/x/description.remote.md").read_text() == "Two."

    path.write_text("Two, and local.")
    assert gh.run("--push", "7")[:2] == (0, "pushed")
    assert gh.state()["prs"]["7"]["body"] == "Two, and local."


def test_push_needs_a_pr(gh):
    code, _, _, err = gh.run("--push", "feat/x")
    assert code == 1
    assert "no pull request found" in err
