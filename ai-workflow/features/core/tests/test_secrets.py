import base64
import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

SECRETS = Path(__file__).resolve().parent.parent / "bin" / "secrets"


@pytest.fixture
def run(tmp_path):
    def _run(*args, env=None, stdin="", cwd=None, timeout=None):
        # A minimal environment, so the developer's own variables and config never leak into a test.
        full_env = {"PATH": os.environ["PATH"], "XDG_CONFIG_HOME": str(tmp_path / "xdg"), **(env or {})}
        return subprocess.run(
            [sys.executable, str(SECRETS), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=full_env,
            cwd=cwd or tmp_path,
            timeout=timeout,
        )

    return _run


def write(tmp_path, name, text):
    (tmp_path / name).write_text(text)


def key_file(kind, width, last):
    """A key file shaped like a generated one: full-width base64 lines, then a short padded one."""
    body = base64.b64encode(hashlib.sha256(kind.encode()).digest() * 40).decode()
    lines = [body[i:i + width] for i in range(0, 20 * width, width)]
    return "\n".join([f"-----BEGIN {kind}-----", *lines, last, f"-----END {kind}-----"]) + "\n"


def sections(out):
    """Parses the markdown `has` and `list` print into {source: [lines]}."""
    result, current = {}, None
    for line in out.splitlines():
        if line.startswith("## "):
            current = result.setdefault(line[3:], [])
        elif line and current is not None:
            current.append(line)
    return result


class TestHelp:
    # What an agent reading `secrets --help` has no use for: it only needs to know how to call the tool.
    INTERNALS = ["minLength", "excludeNames", "urlPasswords", "SECRETS_CONFIG", "SECRETS_REDACT_FILES", "XDG_CONFIG_HOME", "PEM", "REDACTED", "redact.", "secrets redact", "1 MiB", "10,000", "git root", "Configuration", "50 files", "placeholders", "--help-all"]

    def test_the_help_is_only_how_to_call_the_tool(self, run):
        r = run("--help")
        assert r.returncode == 0
        for word in self.INTERNALS:
            assert word not in r.stdout, word
        assert len(r.stdout.splitlines()) < 40 and len(r.stdout) < 2500
        for command in ("has", "list", "get"):
            assert f"secrets {command}" in r.stdout

    def test_redact_says_what_it_does_without_listing_what_it_redacts(self, run):
        r = run("redact", "--help")
        assert r.returncode == 0
        assert "Reads text on stdin and writes it with secret values replaced by [REDACTED:NAME]." in " ".join(r.stdout.split())
        assert len(r.stdout.splitlines()) < 10
        for word in ("minLength", "excludeNames", "urlPasswords", "SECRETS_CONFIG", "SECRETS_REDACT_FILES", "PEM", "redact.", "1 MiB", "10,000", "git root", "Configuration", "KEY", "TOKEN", "PASSWORD"):
            assert word not in r.stdout, word

    def test_the_help_of_a_command_is_short_too(self, run):
        for command in ("has", "list", "get"):
            r = run(command, "--help")
            assert r.returncode == 0 and len(r.stdout.splitlines()) < 15
            assert "--file" in r.stdout


class TestHas:
    def test_lists_the_places_it_is_set_and_only_those(self, run, tmp_path):
        write(tmp_path, ".env", "A=1\nB=1\n")
        write(tmp_path, ".env.development.local", "A=2\n")
        write(tmp_path, ".secrets", "C=1\n")
        write(tmp_path, ".env.example", "D=placeholder\n")
        write(tmp_path, "notes.env", "E=1\n")
        r = run("has", "A", "B", "C", "E", env={"A": "x"})
        assert r.stdout == (
            "A: set in env, .env, .env.development.local\n"
            "B: set in .env\n"
            "C: set in .secrets\n"
            "E: not set (checked env, .env, .env.development.local, .secrets)\n"
        )
        assert r.returncode == 1  # E is set nowhere

    def test_a_placeholder_file_is_not_a_place(self, run, tmp_path):
        write(tmp_path, ".env.example", "D=placeholder\n")
        write(tmp_path, ".env", "OTHER=1\n")
        assert run("has", "D").stdout == "D: not set (checked env, .env)\n"

    def test_says_so_when_there_are_no_env_files(self, run):
        r = run("has", "A", env={"A": "x"})
        assert r.stdout == (
            "A: set in env\n"
            "(No env files in the current directory (looked for .env, .env.*, .secrets))\n"
        )
        assert r.returncode == 0

    def test_exits_0_when_every_name_is_set_in_some_source(self, run, tmp_path):
        write(tmp_path, ".env", "A=1\n")
        assert run("has", "A", "B", env={"B": "x"}).returncode == 0
        assert run("has", "A", "B").returncode == 1

    def test_env_flag_ignores_files(self, run, tmp_path):
        write(tmp_path, ".env", "ONLY_IN_FILE=abc\n")
        r = run("has", "--env", "ONLY_IN_FILE")
        assert r.returncode == 1
        assert r.stdout == "ONLY_IN_FILE: not set (checked env)\n"

    def test_file_flag_ignores_env_and_the_other_files_and_takes_any_path(self, run, tmp_path):
        write(tmp_path, "prod.env", "TOKEN=abc\n")
        write(tmp_path, ".env", "TOKEN=abc\n")
        r = run("has", "--file", "prod.env", "TOKEN", env={"TOKEN": "x"})
        assert r.returncode == 0
        assert r.stdout == "TOKEN: set in prod.env\n"

    def test_env_and_file_flags_combine(self, run, tmp_path):
        write(tmp_path, "a.env", "X=1\n")
        r = run("has", "--env", "--file", "a.env", "X", env={"X": "y"})
        assert r.stdout == "X: set in env, a.env\n"

    def test_an_empty_value_is_not_set_and_says_where_it_is_empty(self, run, tmp_path):
        write(tmp_path, ".env", "EMPTY=\nQUOTED=''\n")
        r = run("has", "EMPTY", "QUOTED", "--file", ".env")
        assert r.returncode == 1
        assert r.stdout == (
            "EMPTY: not set (checked .env; empty in .env)\n"
            "QUOTED: not set (checked .env; empty in .env)\n"
        )

    def test_a_missing_file_is_reported_after_the_names_not_fatal(self, run):
        r = run("has", "--file", "nope.env", "A")
        assert r.returncode == 1
        assert r.stdout == "A: not set (checked nope.env)\n(file not found: nope.env)\n"

    def test_an_unreadable_explicit_file_fails_even_when_the_name_is_set_elsewhere(self, run):
        r = run("has", "--env", "--file", "nope.env", "A", env={"A": "x"})
        assert r.returncode == 1
        assert r.stdout == "A: set in env\n(file not found: nope.env)\n"

    def test_a_byte_order_mark_does_not_hide_the_first_variable(self, run, tmp_path):
        write(tmp_path, ".env", "\ufeffAPI_KEY=supersecret123\nB=1\n")
        assert run("has", "API_KEY", "--file", ".env").stdout == "API_KEY: set in .env\n"
        assert run("list", "--file", ".env").stdout == "## .env\n- API_KEY\n- B\n"

    def test_a_comment_after_the_blanks_of_an_empty_value_is_not_its_value(self, run, tmp_path):
        write(tmp_path, ".env", (
            "OPENAI_API_KEY= # required, get one at platform.openai.com\n"
            "STRIPE_KEY=   # optional\n"
            "DB_PASSWORD=\t# fill me\n"
        ))
        r = run("has", "OPENAI_API_KEY", "STRIPE_KEY", "DB_PASSWORD", "--file", ".env")
        assert r.returncode == 1
        assert r.stdout == "".join(f"{name}: not set (checked .env; empty in .env)\n" for name in ("OPENAI_API_KEY", "STRIPE_KEY", "DB_PASSWORD"))
        assert run("list", "--file", ".env").stdout == "## .env\n- OPENAI_API_KEY\n- STRIPE_KEY\n- DB_PASSWORD\n"
        get = run("get", "STRIPE_KEY")
        assert get.returncode == 1 and get.stdout == "" and "STRIPE_KEY is empty" in get.stderr
        assert run("redact", stdin="see the # optional flag").stdout == "see the # optional flag"

    def test_an_envrc_is_not_read_by_default_since_its_values_are_often_shell_expressions(self, run, tmp_path):
        write(tmp_path, ".envrc", "export GITHUB_TOKEN=$(gh auth token)\n")
        r = run("has", "GITHUB_TOKEN")
        assert r.stdout.startswith("GITHUB_TOKEN: not set (checked env)")
        assert run("redact", stdin="GITHUB_TOKEN=$(gh auth token) ./deploy.sh").stdout == "GITHUB_TOKEN=$(gh auth token) ./deploy.sh"

    def test_an_envrc_added_to_the_patterns_reads_its_export_lines_and_ignores_its_shell_code(self, run, tmp_path):
        write(tmp_path, ".envrc", (
            "use nix\nsource_up\nPATH_add bin\nif has op; then\n  export API_TOKEN=tok-abcdefghij\nfi\n"
            "export DB_HOST=localhost\ndotenv_if_exists .env.local\n"
        ))
        env = config(tmp_path, {"files": {"include": [".env", ".env.*", ".envrc"]}})
        assert run("has", "API_TOKEN", env=env).stdout == "API_TOKEN: set in .envrc\n"
        assert sections(run("list", env=env).stdout)[".envrc"] == ["- API_TOKEN", "- DB_HOST"]
        assert run("redact", env=env, stdin="use tok-abcdefghij").stdout == "use [REDACTED:API_TOKEN]"

    def test_looks_at_no_more_than_50_env_files(self, run, tmp_path):
        for i in range(60):
            write(tmp_path, f".env.{i:03d}", f"V{i:03d}=1\n")
        found = [label for label in sections(run("list").stdout) if label.startswith(".env.")]
        assert found == [f".env.{i:03d}" for i in range(50)]
        assert "V049: set in .env.049" in run("has", "V049").stdout
        assert run("has", "V050").stdout.startswith("V050: not set")

    def test_never_prints_the_value(self, run, tmp_path):
        write(tmp_path, ".env", "API_KEY=s3cr3t-value-123\n")
        r = run("has", "API_KEY", env={"API_KEY": "s3cr3t-value-123"})
        assert "s3cr3t" not in r.stdout + r.stderr


class TestList:
    def test_default_prints_a_section_per_source_with_names_only(self, run, tmp_path):
        write(tmp_path, ".env", "# comment\nB=2\nexport A=1\n\nnot a var\nC=\n")
        write(tmp_path, ".env.local", "D=secret-value\n")
        r = run("list", env={"FROM_ENV": "secret-value"})
        found = sections(r.stdout)
        assert list(found) == ["env", ".env", ".env.local"]
        assert found[".env"] == ["- B", "- A", "- C"]
        assert found[".env.local"] == ["- D"]
        assert "- FROM_ENV" in found["env"]
        assert "secret-value" not in r.stdout
        assert r.returncode == 0

    def test_an_unquoted_pem_block_is_one_value_not_variables(self, run, tmp_path):
        pem = "PRIV=-----BEGIN RSA PRIVATE KEY-----\nAbCdEf0123456789xyzQWERTY==\nMoreBase64Lines=\n-----END RSA PRIVATE KEY-----\n"
        write(tmp_path, ".env", f"BEFORE=1\n{pem}AFTER=1\n")
        assert run("list", "--file", ".env").stdout == "## .env\n- BEFORE\n- PRIV\n- AFTER\n"

    def test_a_pem_value_on_one_line_does_not_swallow_the_variables_up_to_a_later_end(self, run, tmp_path):
        write(tmp_path, ".env", (
            "JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0B\\n-----END PRIVATE KEY-----\n"
            "DB_PASSWORD=hunter2hunter2\n"
            "API_TOKEN=tok-abcdefghij\n"
            "OTHER_PRIVATE_KEY=-----BEGIN X\nAbCdEf0123456789xyzQWERTY==\n-----END X\n"
            "LAST=1\n"
        ))
        assert run("list", "--file", ".env").stdout == "## .env\n- JWT_PRIVATE_KEY\n- DB_PASSWORD\n- API_TOKEN\n- OTHER_PRIVATE_KEY\n- LAST\n"
        assert run("has", "DB_PASSWORD", "API_TOKEN", "--file", ".env").returncode == 0
        assert run("redact", stdin="hunter2hunter2 tok-abcdefghij").stdout == "[REDACTED:DB_PASSWORD] [REDACTED:API_TOKEN]"

    def test_a_pem_value_whose_end_is_too_far_is_its_own_line(self, run, tmp_path):
        between = "".join(f"V{i}=1\n" for i in range(250))
        write(tmp_path, ".env", f"PRIV=-----BEGIN X\n{between}-----END X\n")
        names = sections(run("list", "--file", ".env").stdout)[".env"]
        assert names == ["- PRIV", *(f"- V{i}" for i in range(250))]
        assert run("get", "PRIV").stdout == "-----BEGIN X"

    def test_many_pem_values_without_an_end_parse_in_linear_time(self, run, tmp_path):
        # Unbounded, 50k of them took about 25s; the timeout fails that fast.
        write(tmp_path, ".env", "".join(f"K{i}=-----BEGIN X\n" for i in range(50_000)))
        r = run("list", "--file", ".env", timeout=10)
        assert r.returncode == 0 and len(sections(r.stdout)[".env"]) == 50_000

    def test_many_key_blocks_without_an_end_parse_in_linear_time(self, run, tmp_path):
        # Looking up to 200 lines ahead from each BEGIN line took about 20s for 1M of them. A file has at most 1 MiB,
        # which bounds that to about 2s, too little for a timeout to catch: this checks the result, the cap the time.
        write(tmp_path, ".env", "-----BEGIN\n" * 95_000 + "A=1\n")
        assert run("list", "--file", ".env", timeout=10).stdout == "## .env\n- A\n"

    def test_the_base64_lines_of_a_key_file_are_not_variables(self, run, tmp_path):
        body = "".join(f"b3BlbnNzaC1rZXktdjE{i:02d}".ljust(68, "A") + "==\n" for i in range(3))
        write(tmp_path, "id_rsa", f"-----BEGIN OPENSSH PRIVATE KEY-----\n{body}-----END OPENSSH PRIVATE KEY-----\n")
        assert run("list", "--file", "id_rsa").stdout == "## id_rsa\n(no variables)\n"
        # Without the marker lines (a body pasted on its own) only the name length tells them apart.
        write(tmp_path, "body", body)
        assert run("list", "--file", "body").stdout == "## body\n(no variables)\n"
        name = "N" * 63
        write(tmp_path, ".env", f"{name}=1\n")
        assert run("list", "--file", ".env").stdout == f"## .env\n- {name}\n"

    @pytest.mark.parametrize(
        "kind, width, last",
        [
            ("PRIVATE KEY", 64, "Gzmb26SBI18AYQHLJzOpba4="),
            ("PRIVATE KEY", 64, "ZtvRT54bJm468n5ryAmxwg=="),
            ("OPENSSH PRIVATE KEY", 70, "b3BlbnNzaC1rZXktdjEAAAAABG5vbmU="),
        ],
    )
    def test_the_short_padded_last_line_of_a_key_file_is_not_a_variable(self, run, tmp_path, kind, width, last):
        write(tmp_path, "key", key_file(kind, width, last))
        name = last.rstrip("=")
        assert run("list", "--file", "key").stdout == "## key\n(no variables)\n"
        assert run("has", name, "--file", "key").stdout == f"{name}: not set (checked key)\n"
        assert f"{name} is not set in key" in run("get", name, "--file", "key").stderr

    def test_a_base64_key_without_markers_is_not_a_variable(self, run, tmp_path):
        # Fernet keys and `openssl rand -base64 32` (WireGuard) keys end in `=` and read as `NAME=`: without the
        # name's case check, most of these list.
        rng = random.Random(0)
        keys = [encode(rng.randbytes(32)).decode() for encode in (base64.urlsafe_b64encode, base64.b64encode) for _ in range(200)]
        write(tmp_path, ".secrets", "\n".join(keys) + "\n")
        names = [key.rstrip("=") for key in keys]
        assert sections(run("list").stdout)[".secrets"] == ["(no variables)"]
        assert run("has", "--file", ".secrets", "--", *names).stdout =="".join(f"{name}: not set (checked .secrets)\n" for name in names)
        for name in (names[0], names[-1]):
            r = run("get", "--file", ".secrets", "--", name)
            assert r.stdout == "" and f"{name} is not set in .secrets" in r.stderr

    def test_a_declared_variable_without_a_value_is_still_one(self, run, tmp_path):
        write(tmp_path, ".env", "FOO=\nfoo_bar=\nFOO_BAR=\nfoo.bar-2 = \nMixedCase=value\n")
        assert run("list", "--file", ".env").stdout == "## .env\n- FOO\n- foo_bar\n- FOO_BAR\n- foo.bar-2\n- MixedCase\n"

    def test_a_key_block_between_variables_hides_none_of_them(self, run, tmp_path):
        write(tmp_path, ".env", "A=1\n" + key_file("PRIVATE KEY", 64, "Gzmb26SBI18AYQHLJzOpba4=") + "B=2\n")
        assert run("list", "--file", ".env").stdout == "## .env\n- A\n- B\n"

    def test_a_pem_value_without_its_end_stops_at_the_next_variable(self, run, tmp_path):
        write(tmp_path, ".env", "A_KEY=-----BEGIN X\nB_TOKEN=bbbb-bbbbbbbb\n-----END X\nC=1\n")
        assert run("list", "--file", ".env").stdout == "## .env\n- A_KEY\n- B_TOKEN\n- C\n"
        assert run("get", "A_KEY").stdout == "-----BEGIN X"
        assert run("redact", stdin="bbbb-bbbbbbbb").stdout == "[REDACTED:B_TOKEN]"

    def test_padded_base64_lines_do_not_end_a_pem_value(self, run, tmp_path):
        pem = "-----BEGIN X-----\nMIIEvQIBADANBgkqhkiG9w0B\nQWERTYUIOP=\nASDFGHJK==\nAB=\n-----END X-----"
        write(tmp_path, ".env", f"PRIV={pem}\nAFTER=1\n")
        assert run("list", "--file", ".env").stdout == "## .env\n- PRIV\n- AFTER\n"
        assert run("get", "PRIV").stdout == pem

    def test_takes_paths_and_env(self, run, tmp_path):
        write(tmp_path, "x.env", "ONLY=1\n")
        write(tmp_path, ".env", "IGNORED=1\n")
        assert run("list", "--file", "x.env").stdout == "## x.env\n- ONLY\n"
        assert list(sections(run("list", "--env").stdout)) == ["env"]

    def test_an_empty_file_says_so(self, run, tmp_path):
        write(tmp_path, "x.env", "# nothing\n")
        assert run("list", "--file", "x.env").stdout == "## x.env\n(no variables)\n"

    def test_an_unreadable_explicit_file_fails_in_its_section(self, run):
        r = run("list", "--file", "nope.env")
        assert r.returncode == 1
        assert sections(r.stdout) == {"nope.env": ["(file not found: nope.env)"]}

    def test_a_file_over_1_mib_is_an_error_and_one_of_1_mib_is_read(self, run, tmp_path):
        write(tmp_path, "big.env", "A=1\n" + "#" * ((1 << 20) - 3))
        write(tmp_path, "fits.env", "A=1\n" + "#" * ((1 << 20) - 4))
        message = "file too large to read as an env file (over 1 MiB): big.env"
        has = run("has", "A", "--file", "big.env")
        assert has.returncode == 1 and has.stdout == f"A: not set (checked big.env)\n({message})\n"
        assert sections(run("list", "--file", "big.env").stdout) == {"big.env": [f"({message})"]}
        assert message in run("get", "A", "--file", "big.env").stderr
        assert run("has", "A", "--file", "fits.env").stdout == "A: set in fits.env\n"

    def test_a_device_that_never_ends_is_too_large_not_read_forever(self, run):
        # Without the cap this reads until memory runs out; the timeout fails that fast.
        r = run("list", "--file", "/dev/zero", timeout=20)
        assert r.returncode == 1 and "file too large to read as an env file" in r.stdout

    def test_a_fifo_without_a_writer_is_read_as_empty_not_waited_on(self, run, tmp_path):
        # Opening it for reading waits for a writer; the timeout fails that fast.
        os.mkfifo(tmp_path / "fifo")
        assert run("list", "--file", "fifo", timeout=10).stdout == "## fifo\n(no variables)\n"

    def test_no_env_files_is_not_an_error(self, run):
        r = run("list")
        assert r.returncode == 0
        assert "_No env files in the current directory" in r.stdout


class TestGet:
    def test_prints_only_the_value_without_a_trailing_newline_when_piped(self, run, tmp_path):
        write(tmp_path, ".env", "K=value\n")
        assert run("get", "K").stdout == "value"

    def test_finds_it_in_the_env_or_any_common_file(self, run, tmp_path):
        write(tmp_path, ".env.local", "FROM_FILE=file-value\n")
        assert run("get", "FROM_FILE").stdout == "file-value"
        assert run("get", "FROM_ENV", env={"FROM_ENV": "env-value"}).stdout == "env-value"

    def test_the_same_value_in_several_sources_is_fine(self, run, tmp_path):
        write(tmp_path, ".env", "K=same\n")
        assert run("get", "K", env={"K": "same"}).stdout == "same"

    def test_different_values_pick_none_and_name_the_sources(self, run, tmp_path):
        write(tmp_path, ".env", "K=from-file\n")
        r = run("get", "K", env={"K": "from-env"})
        assert r.returncode == 1 and r.stdout == ""
        assert "K has different values in env, .env" in r.stderr
        assert "from-" not in r.stderr

    def test_env_and_file_flags_choose_the_source(self, run, tmp_path):
        write(tmp_path, ".env", "K=from-file\n")
        assert run("get", "K", "--env", env={"K": "from-env"}).stdout == "from-env"
        assert run("get", "K", "--file", ".env", env={"K": "from-env"}).stdout == "from-file"

    def test_missing_or_empty_fails_without_output(self, run, tmp_path):
        write(tmp_path, ".env", "EMPTY=\n")
        missing, empty = run("get", "NOPE"), run("get", "EMPTY")
        for r in (missing, empty):
            assert r.returncode == 1 and r.stdout == ""
        assert "NOPE is not set in env, .env" in missing.stderr
        assert "EMPTY is empty in env, .env" in empty.stderr

    def test_an_unreadable_explicit_file_fails(self, run):
        r = run("get", "K", "--file", "nope.env")
        assert r.returncode == 1 and r.stdout == ""
        assert "file not found: nope.env" in r.stderr

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("K=plain", "plain"),
            ("export K=plain", "plain"),
            ("K = spaced", "spaced"),
            ("K=value # a comment", "value"),
            ("K=a#b", "a#b"),
            ('K="quoted # kept"', "quoted # kept"),
            ("K='single $x \\n'", "single $x \\n"),
            ('K="esc\\nnl \\"q\\""', 'esc\nnl "q"'),
            ('K="multi\nline"', "multi\nline"),
            ('K="unterminated', "unterminated"),
            ("K=#x", "#x"),
            ("K= value # c", "value"),
            ('K= "x"', "x"),
            ("K=  'x # y'", "x # y"),
        ],
    )
    def test_parses_env_file_syntax(self, run, tmp_path, line, expected):
        write(tmp_path, ".env", line + "\nOTHER=1\n")
        assert run("get", "K").stdout == expected

    def test_last_assignment_wins(self, run, tmp_path):
        write(tmp_path, ".env", "K=first\nK=second\n")
        assert run("get", "K").stdout == "second"

    def test_a_commented_out_assignment_is_not_a_variable(self, run, tmp_path):
        write(tmp_path, ".env", "# OLD_TOKEN=tok-0123456789\n#export K=commented\nK=live\n## K=commented-again\n")
        assert run("list", "--file", ".env").stdout == "## .env\n- K\n"
        assert run("has", "OLD_TOKEN", "--file", ".env").stdout == "OLD_TOKEN: not set (checked .env)\n"
        assert run("get", "K").stdout == "live"

    def test_an_unterminated_quote_does_not_swallow_the_variables_below(self, run, tmp_path):
        write(tmp_path, ".env", 'A="never closed\nB=after\n')
        assert run("list", "--file", ".env").stdout == "## .env\n- A\n- B\n"
        assert run("get", "B").stdout == "after"

    def test_a_multiline_value_does_not_swallow_the_next_variable(self, run, tmp_path):
        write(tmp_path, ".env", 'A="l1\nl2"\nB=after\n')
        assert run("get", "B").stdout == "after"


class TestRedact:
    def test_replaces_secret_values_from_env_and_dotenv(self, run, tmp_path):
        write(tmp_path, ".env", "DB_PASSWORD=hunter2hunter2\n")
        r = run(
            "redact",
            env={"GITHUB_TOKEN": "ghp_abcdefghij"},
            stdin="a ghp_abcdefghij b hunter2hunter2 c",
        )
        assert r.stdout == "a [REDACTED:GITHUB_TOKEN] b [REDACTED:DB_PASSWORD] c"

    def test_takes_extra_files_from_args_and_the_env_var(self, run, tmp_path):
        write(tmp_path, "a.env", "A_SECRET=aaaa-aaaaaa\n")
        write(tmp_path, "b.env", "B_SECRET=bbbb-bbbbbb\n")
        r = run(
            "redact",
            "--file", "a.env",
            env={"SECRETS_REDACT_FILES": f"{tmp_path / 'b.env'}:/does/not/exist"},
            stdin="aaaa-aaaaaa bbbb-bbbbbb",
        )
        assert r.stdout == "[REDACTED:A_SECRET] [REDACTED:B_SECRET]"

    def test_covers_the_common_env_files_but_not_placeholders(self, run, tmp_path):
        write(tmp_path, ".env.local", "A_TOKEN=local-value\n")
        write(tmp_path, ".env.example", "B_TOKEN=your-token-here\n")
        r = run("redact", stdin="local-value your-token-here")
        assert r.stdout == "[REDACTED:A_TOKEN] your-token-here"

    def test_leaves_names_that_are_not_secret_alone(self, run, tmp_path):
        write(tmp_path, ".env", "GIT_AUTHOR_NAME=Some Person\nSSH_AUTH_SOCK=/tmp/agent.sock\nPORT=3000000000\n")
        text = "Some Person /tmp/agent.sock 3000000000 /work/dir/long"
        assert run("redact", env={"PWD": "/work/dir/long"}, stdin=text).stdout == text

    def test_redacts_from_6_characters_by_default(self, run, tmp_path):
        write(tmp_path, ".env", "FIVE_TOKEN=1a345\nSIX_TOKEN=1a3456\n")
        assert run("redact", stdin="1a345 1a3456").stdout == "1a345 [REDACTED:SIX_TOKEN]"

    @pytest.mark.parametrize("name", ["SECRET", "MY_SECRET_X", "GH_TOKEN", "tokens", "DB_PASSWORD", "DB_PASSWD", "SSH_PASSPHRASE", "KEY", "API_KEY", "KEY_ID", "AWS_KEY_ID", "PASS", "DB_PASS", "GOOGLE_CREDENTIALS", "OPENAIAPIKEY", "lower_token"])
    def test_default_names_that_are_redacted(self, run, tmp_path, name):
        write(tmp_path, ".env", f"{name}=value-0123456789\n")
        assert run("redact", stdin="value-0123456789").stdout == f"[REDACTED:{name}]"

    @pytest.mark.parametrize("name", ["MONKEY", "KEYBOARD_LAYOUT", "KEYCHAIN_X", "PASSENGER", "PASSTHROUGH", "HTTP_PORT", "GIT_AUTHOR_NAME", "SSH_AUTH_SOCK", "TOKEN_TTL", "SECRET_FILE", "GOOGLE_CREDENTIALS_PATH", "KEY_PREFIX", "API_KEY_LENGTH", "GOOGLE_APPLICATION_CREDENTIALS"])
    def test_default_names_that_are_left_alone(self, run, tmp_path, name):
        write(tmp_path, ".env", f"{name}=value-0123456789\n")
        assert run("redact", stdin="value-0123456789").stdout == "value-0123456789"

    def test_replaces_the_longer_value_whole(self, run, tmp_path):
        write(tmp_path, ".env", "A_TOKEN=abcdefghij\nB_TOKEN=abcdefghij-longer\n")
        assert run("redact", stdin="abcdefghij-longer").stdout == "[REDACTED:B_TOKEN]"

    def test_text_without_secrets_passes_through_byte_for_byte(self, run):
        text = "plain\nünïcode ✓\n"
        assert run("redact", stdin=text).stdout == text

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("postgres://postgres:postgres@localhost:5432/db", "postgres://postgres:[REDACTED:url-password]@localhost:5432/db"),
            ("redis://:s3cr3t@cache:6379/0", "redis://:[REDACTED:url-password]@cache:6379/0"),
            ("amqp+ssl://u:p%40ss%2Fw@b/v", "amqp+ssl://u:[REDACTED:url-password]@b/v"),
            ("postgres://u:p@ssw0rd@db/x", "postgres://u:[REDACTED:url-password]@db/x"),
            ("a https://u:one@x and https://v:two@y.", "a https://u:[REDACTED:url-password]@x and https://v:[REDACTED:url-password]@y."),
            ("DATABASE_URL=mysql://root:hunter2@db\nnext line", "DATABASE_URL=mysql://root:[REDACTED:url-password]@db\nnext line"),
            ("\033[1mpostgres://u:s3cretpw@h/db\033[0m", "\033[1mpostgres://u:[REDACTED:url-password]@h/db\033[0m"),
            ("1https://u:pw@h/", "1https://u:[REDACTED:url-password]@h/"),
            ('{"url": "https:\\/\\/u:pw123456@h\\/x"}', '{"url": "https:\\/\\/u:[REDACTED:url-password]@h\\/x"}'),
        ],
    )
    def test_masks_only_the_password_of_a_url_wherever_it_comes_from(self, run, text, expected):
        assert run("redact", stdin=text).stdout == expected

    @pytest.mark.parametrize(
        "text",
        [
            "https://example.com:8080/path",
            "ssh://git@github.com/org/repo.git",
            "http://localhost:3000/user@example.com",
            "git@github.com:org/repo.git",
            "https://user@host:8080",
            "https://h:8080/x@y.com?a=b",
            "12:34:56@ not a url",
            "https:\\/\\/h:8080\\/x@y.com",
        ],
    )
    def test_leaves_urls_without_a_password_alone(self, run, text):
        assert run("redact", stdin=text).stdout == text

    def test_a_password_already_redacted_by_name_keeps_that_label(self, run, tmp_path):
        write(tmp_path, ".env", "DB_PASSWORD=hunter2hunter2\n")
        r = run("redact", stdin="postgres://app:hunter2hunter2@db/main")
        assert r.stdout == "postgres://app:[REDACTED:DB_PASSWORD]@db/main"

    def test_url_passwords_can_be_turned_off(self, run, tmp_path):
        env = config(tmp_path, {"redact": {"urlPasswords": False}})
        text = "postgres://app:secret@db/main"
        assert run("redact", env=env, stdin=text).stdout == text

    def test_a_double_quoted_value_is_redacted_as_written_in_the_file_too(self, run, tmp_path):
        write(tmp_path, ".env", 'API_TOKEN="abc\\"defghij"\nFIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkq\\n-----END PRIVATE KEY-----\\n"\n')
        catted = (tmp_path / ".env").read_text()
        out = run("redact", stdin=catted).stdout
        assert out == 'API_TOKEN="[REDACTED:API_TOKEN]"\nFIREBASE_PRIVATE_KEY="[REDACTED:FIREBASE_PRIVATE_KEY]"\n'

    def test_each_line_of_a_multi_line_value_is_redacted_for_numbered_listings(self, run, tmp_path):
        body = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj"
        write(tmp_path, ".env", f'K_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n{body}\nzzzzzzzzzzzzzzzz+/==\n-----END PRIVATE KEY-----"\n')
        numbered = f"     1\tK_PRIVATE_KEY=\"-----BEGIN PRIVATE KEY-----\n     2\t{body}\n     3\tzzzzzzzzzzzzzzzz+/==\n"
        out = run("redact", stdin=numbered).stdout
        assert body not in out and "zzzzzzzz" not in out

    def test_marker_and_spaced_lines_of_a_multi_line_value_are_left_alone_elsewhere(self, run, tmp_path):
        write(tmp_path, ".env", (
            'K_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n-----END PRIVATE KEY-----"\n'
            'GOOGLE_CREDENTIALS="{\n  \\"type\\": \\"service_account\\",\n  \\"project_id\\": \\"my-project-123456\\"\n}"\n'
        ))
        write(tmp_path, ".env.local", 'BACKUP_SECRET="--------------------------------\nrecovery-0123456789\n"\n')
        code = 'if pem.startswith("-----BEGIN PRIVATE KEY-----"):\n  "type": "service_account",\n  "project_id": "my-project-123456"\n--------------------------------\n'
        assert run("redact", stdin=code).stdout == code

    def test_the_key_material_of_a_multi_line_json_credential_is_redacted_in_any_listing(self, run, tmp_path):
        pem = subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"],
            capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL,
        ).stdout
        account = {
            "type": "service_account",
            "project_id": "my-project-123456",
            "private_key_id": hashlib.sha1(pem.encode()).hexdigest(),
            "private_key": pem,
            "client_email": "deployer@my-project-123456.iam.gserviceaccount.com",
            "client_id": "112233445566778899001",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        text = f"A=1\nGOOGLE_APPLICATION_CREDENTIALS_JSON='{json.dumps(account, indent=2)}'\nB=2\n"
        write(tmp_path, ".env", text)
        key_material = [account["private_key_id"], *pem.splitlines()[1:-1]]
        numbered = "".join(f"{i:6}\t{line}\n" for i, line in enumerate(text.splitlines(), 1))
        grepped = "".join(line + "\n" for line in text.splitlines() if "private_key" in line)
        for listing in (numbered, grepped, text):
            out = run("redact", stdin=listing).stdout
            assert [part for part in key_material if part in out] == []
        lines = text.splitlines()
        unrelated = [line for line in lines if any(k in line for k in ('"type"', '"client_email"', '"auth_uri"', '"token_uri"'))]
        assert len(unrelated) == 4
        unrelated.append('if line.startswith("-----BEGIN PRIVATE KEY-----"):')
        assert run("redact", stdin="\n".join(unrelated)).stdout == "\n".join(unrelated)

    def test_a_long_dash_run_in_a_multi_line_value_is_not_key_material(self, run, tmp_path):
        write(tmp_path, ".env", 'RECOVERY_SECRET="codes\n-------------------------------- 1111-2222 --------------------------------\n"\n')
        line = "| -------------------------------- | -------------------------------- |"
        assert run("redact", stdin=line).stdout == line

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("image: postgres:16", "image: postgres:16"),
            ("POSTGRES_USER: postgres", "POSTGRES_USER: postgres"),
            ("DATABASE_URL=postgres://postgres:postgres@db/app", "DATABASE_URL=postgres://postgres:[REDACTED:url-password]@db/app"),
            ("POSTGRES_PASSWORD=postgres", "POSTGRES_PASSWORD=[REDACTED:POSTGRES_PASSWORD]"),
            ("  POSTGRES_PASSWORD: postgres", "  POSTGRES_PASSWORD: [REDACTED:POSTGRES_PASSWORD]"),
            ('"POSTGRES_PASSWORD": "postgres",', '"POSTGRES_PASSWORD": "[REDACTED:POSTGRES_PASSWORD]",'),
            ("export POSTGRES_PASSWORD='postgres'", "export POSTGRES_PASSWORD='[REDACTED:POSTGRES_PASSWORD]'"),
            ("POSTGRES_PASSWORD=postgresql", "POSTGRES_PASSWORD=postgresql"),
            ("OLD_POSTGRES_PASSWORD=postgres", "OLD_POSTGRES_PASSWORD=postgres"),
        ],
    )
    def test_a_letters_only_value_is_redacted_only_next_to_its_own_variable_name(self, run, tmp_path, text, expected):
        write(tmp_path, ".env", "POSTGRES_PASSWORD=postgres\n")
        assert run("redact", stdin=text).stdout == expected

    def test_digits_only_values_are_redacted_only_next_to_their_name(self, run, tmp_path):
        write(tmp_path, ".env", "PIN_TOKEN=123456\n")
        assert run("redact", stdin="at 123456 PIN_TOKEN=123456").stdout == "at 123456 PIN_TOKEN=[REDACTED:PIN_TOKEN]"

    def test_a_long_letters_only_value_is_redacted_anywhere(self, run, tmp_path):
        write(tmp_path, ".env", "K_TOKEN=abcdefghijklmnop\n")
        assert run("redact", stdin="x abcdefghijklmnop y").stdout == "x [REDACTED:K_TOKEN] y"

    def test_the_same_rule_applies_to_the_environment(self, run):
        out = run("redact", env={"DB_PASSWORD": "changeme"}, stdin="changeme\nDB_PASSWORD=changeme").stdout
        assert out == "changeme\nDB_PASSWORD=[REDACTED:DB_PASSWORD]"

    def test_a_reference_to_another_variable_is_not_a_value(self, run, tmp_path):
        write(tmp_path, ".env", "SERVICE_TOKEN=${API_TOKEN}\nSERVICE_KEY=$OTHER_KEY_VALUE\n")
        text = "${API_TOKEN} $OTHER_KEY_VALUE"
        assert run("redact", stdin=text).stdout == text

    def test_a_value_that_starts_with_a_dollar_is_still_a_value(self, run, tmp_path):
        write(tmp_path, ".env", "DB_PASSWORD='$uperS3cret!xyz'\n")
        assert run("redact", stdin="pw $uperS3cret!xyz").stdout == "pw [REDACTED:DB_PASSWORD]"

    def test_an_unquoted_dollar_value_that_is_no_env_var_name_is_a_value(self, run, tmp_path):
        write(tmp_path, ".env", "DB_PASSWORD=$ecretPassw0rd\n")
        assert run("redact", stdin="pw $ecretPassw0rd").stdout == "pw [REDACTED:DB_PASSWORD]"

    def test_the_settings_of_this_cli_are_never_secrets(self, run, tmp_path):
        write(tmp_path, "extra.env", "X_TOKEN=tok-abcdefghij\n")
        env = {**config(tmp_path, {}), "SECRETS_REDACT_FILES": str(tmp_path / "extra.env")}
        paths = f"cat {env['SECRETS_CONFIG']} {env['SECRETS_REDACT_FILES']}\n"
        assert run("redact", env=env, stdin=paths + "tok-abcdefghij").stdout == paths + "[REDACTED:X_TOKEN]"

    def test_the_environment_holds_values_never_references(self, run):
        env = {"DB_PASSWORD": "$uperS3cret!xyz", "API_TOKEN": "$AbcdefghXyz"}
        assert run("redact", env=env, stdin="$uperS3cret!xyz $AbcdefghXyz").stdout == "[REDACTED:DB_PASSWORD] [REDACTED:API_TOKEN]"

    def test_env_files_of_the_parent_directories_up_to_the_git_root_are_covered(self, run, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "apps" / "api").mkdir(parents=True)
        write(tmp_path, ".env", "ROOT_TOKEN=root-value-123\n")
        write(tmp_path, "apps/.env.local", "MID_TOKEN=mid-value-123\n")
        r = run("redact", cwd=tmp_path / "apps" / "api", stdin="root-value-123 mid-value-123")
        assert r.stdout == "[REDACTED:ROOT_TOKEN] [REDACTED:MID_TOKEN]"

    def test_a_parent_directory_name_with_glob_characters_is_taken_literally(self, run, tmp_path):
        (tmp_path / "a[1]" / "sub").mkdir(parents=True)
        (tmp_path / "a[1]" / ".git").mkdir()
        write(tmp_path, "a[1]/.env", "ROOT_TOKEN=root-value-123\n")
        assert run("redact", cwd=tmp_path / "a[1]" / "sub", stdin="root-value-123").stdout == "[REDACTED:ROOT_TOKEN]"

    def test_parents_are_not_read_outside_a_repository(self, run, tmp_path):
        (tmp_path / "sub").mkdir()
        write(tmp_path, ".env", "ROOT_TOKEN=root-value-123\n")
        assert run("redact", cwd=tmp_path / "sub", stdin="root-value-123").stdout == "root-value-123"

    def test_parents_stop_at_the_git_root(self, run, tmp_path):
        (tmp_path / "repo" / "sub").mkdir(parents=True)
        (tmp_path / "repo" / ".git").mkdir()
        write(tmp_path, ".env", "ABOVE_TOKEN=above-value-123\n")
        assert run("redact", cwd=tmp_path / "repo" / "sub", stdin="above-value-123").stdout == "above-value-123"

    def test_overlapping_values_are_replaced_as_one(self, run, tmp_path):
        write(tmp_path, ".env", "A_TOKEN=abcd1234efgh\nB_TOKEN=1234efghijkl\n")
        assert run("redact", stdin="abcd1234efghijkl!").stdout == "[REDACTED:A_TOKEN]!"

    def test_of_two_values_starting_at_the_same_place_the_longer_names_the_span(self, run, tmp_path):
        write(tmp_path, ".env", "A_TOKEN=abcd-efghij\nB_TOKEN=abcd-efghij-longer\n")
        assert run("redact", stdin="abcd-efghij-longer!").stdout == "[REDACTED:B_TOKEN]!"

    def test_a_named_secret_names_the_span_before_a_url_password_that_starts_with_it(self, run, tmp_path):
        write(tmp_path, ".env", "DB_PASSWORD=hunter2hunter2\n")
        r = run("redact", stdin="postgres://app:hunter2hunter2-old@db/main")
        assert r.stdout == "postgres://app:[REDACTED:DB_PASSWORD]@db/main"

    def test_a_value_inside_a_marker_is_not_matched(self, run, tmp_path):
        write(tmp_path, ".env", "A_TOKEN=aaaa-aaaaaa\nB_TOKEN=REDACTED:A_TOKEN\n")
        assert run("redact", stdin="x aaaa-aaaaaa y").stdout == "x [REDACTED:A_TOKEN] y"

    def test_a_long_run_of_letters_is_not_quadratic(self, run):
        # A URL pattern that starts at a scheme's letters retries the run from each letter: 300k letters took
        # minutes. The timeout fails it fast.
        r = run("redact", stdin="a" * 300_000, timeout=20)
        assert r.returncode == 0 and r.stdout == "a" * 300_000

    def test_a_long_run_of_whitespace_in_an_env_file_is_not_quadratic(self, run, tmp_path):
        # A comment split on `\s+#` rescanned the run from each space: 200k took about a minute, past the plugin's
        # timeout, so every result went unredacted. The timeout fails that fast.
        write(tmp_path, ".env.development", "A=x" + " \t" * 100_000 + "y\nAPI_TOKEN=tok-abcdefghij\n")
        assert run("redact", stdin="tok-abcdefghij", timeout=10).stdout == "[REDACTED:API_TOKEN]"

    def test_a_long_run_of_whitespace_right_after_the_equals_sign_is_not_quadratic(self, run, tmp_path):
        # Matching the `=` padding of a key line across the run tried every split of it: these 200k spaces took over a
        # minute. The timeout fails that fast.
        write(tmp_path, ".env", "A=" + " " * 200_000 + "x\nAPI_TOKEN=tok-abcdefghij\n")
        assert run("redact", stdin="tok-abcdefghij", timeout=10).stdout == "[REDACTED:API_TOKEN]"

    def test_a_symlinked_env_file_is_read_and_one_over_1_mib_is_skipped(self, run, tmp_path):
        (tmp_path / "shared").mkdir()
        write(tmp_path, "shared/.env", "SHARED_TOKEN=shared-value-123\n")
        (tmp_path / ".env").symlink_to("shared/.env")
        big = tmp_path / "shared" / "big"
        big.write_text("BIG_TOKEN=big-value-123\n")
        os.truncate(big, (1 << 20) + 1)
        (tmp_path / ".env.big").symlink_to(big)
        r = run("redact", stdin="shared-value-123 big-value-123")
        assert (r.returncode, r.stdout, r.stderr) == (0, "[REDACTED:SHARED_TOKEN] big-value-123", "")

    def test_reads_at_most_4_mib_of_env_files_in_all(self, run, tmp_path):
        for i in range(1, 5):
            line = f"T{i}_TOKEN=value-{i}-123456\n"
            write(tmp_path, f".env.{i}", line + "#" * ((1 << 20) - len(line)))
        write(tmp_path, ".env.5", "T5_TOKEN=value-5-123456\n")
        text = " ".join(f"value-{i}-123456" for i in range(1, 6))
        assert run("redact", stdin=text).stdout == " ".join(f"[REDACTED:T{i}_TOKEN]" for i in range(1, 5)) + " value-5-123456"

    def test_looks_for_at_most_10000_values_the_environments_first(self, run, tmp_path):
        write(tmp_path, ".env", "".join(f"K{i}_TOKEN=tok-{i:06d}-abcdef\n" for i in range(10_000)))
        r = run("redact", env={"ENV_TOKEN": "env-value-123"}, stdin="env-value-123 tok-009998-abcdef tok-009999-abcdef")
        assert r.stdout == "[REDACTED:ENV_TOKEN] [REDACTED:K9998_TOKEN] tok-009999-abcdef"

    def test_many_letters_only_values_are_found_in_one_pass(self, run, tmp_path):
        # A regex per name took 3s to compile for 50k of them, and 45s to scan 100k characters with; the timeout
        # fails that fast. 10k names, the most that are looked for, over 300k characters.
        write(tmp_path, ".env", "".join(f"K{i}_PASSWORD=abcdefgh\n" for i in range(10_000)))
        text = "x" * 300_000 + " K9999_PASSWORD=abcdefgh"
        assert run("redact", stdin=text, timeout=10).stdout == "x" * 300_000 + " K9999_PASSWORD=[REDACTED:K9999_PASSWORD]"

    def test_many_url_like_fragments_without_a_password_are_not_quadratic(self, run):
        # Scheme separators with colons and no `@`: a password pattern that ran past the next `/` would rescan
        # the rest of the text from each one. The timeout fails that fast.
        text = "://u:p" * 60_000 + " ://u:" + ":" * 300_000
        r = run("redact", stdin=text, timeout=20)
        assert r.returncode == 0 and r.stdout == text

    def test_commented_out_and_overridden_assignments_are_redacted(self, run, tmp_path):
        text = "# STRIPE_SECRET_KEY=sk_live_PRODabc123456\nSTRIPE_SECRET_KEY=sk_test_DEVxyz987654\nAPI_TOKEN=old-token-111111\nAPI_TOKEN=new-token-222222\n"
        write(tmp_path, ".env", text)
        numbered = "".join(f"{i:6}\t{line}\n" for i, line in enumerate(text.splitlines(), 1))
        assert run("redact", stdin=numbered).stdout == (
            "     1\t# STRIPE_SECRET_KEY=[REDACTED:STRIPE_SECRET_KEY]\n"
            "     2\tSTRIPE_SECRET_KEY=[REDACTED:STRIPE_SECRET_KEY]\n"
            "     3\tAPI_TOKEN=[REDACTED:API_TOKEN]\n"
            "     4\tAPI_TOKEN=[REDACTED:API_TOKEN]\n"
        )
        assert run("redact", stdin="sk_live_PRODabc123456 old-token-111111").stdout == "[REDACTED:STRIPE_SECRET_KEY] [REDACTED:API_TOKEN]"

    @pytest.mark.parametrize(
        "line, value",
        [
            ("#DB_PASSWORD=pw-0123456789", "pw-0123456789"),
            ("# export DB_PASSWORD=pw-0123456789", "pw-0123456789"),
            ("## DB_PASSWORD=pw-0123456789", "pw-0123456789"),
            ("  #  DB_PASSWORD='pw-0123456789'", "pw-0123456789"),
            ("# DB_PASSWORD=pw-0123456789 # the old one", "pw-0123456789"),
            ('# DB_PASSWORD="pw-01\\"23456789"', 'pw-01"23456789'),
            ('# DB_PASSWORD= "pw-0123456789"', "pw-0123456789"),
        ],
    )
    def test_a_commented_out_value_is_parsed_like_a_live_one(self, run, tmp_path, line, value):
        write(tmp_path, ".env", f"{line}\nOTHER=1\n")
        out = run("redact", stdin=f"{line}\n{value}").stdout
        assert "23456789" not in out and out.count("[REDACTED:DB_PASSWORD]") == 2

    def test_a_commented_out_letters_only_value_is_redacted_only_next_to_its_name(self, run, tmp_path):
        write(tmp_path, ".env", "#POSTGRES_PASSWORD=postgres\n")
        assert run("redact", stdin="image: postgres\nPOSTGRES_PASSWORD=postgres").stdout == "image: postgres\nPOSTGRES_PASSWORD=[REDACTED:POSTGRES_PASSWORD]"

    def test_prose_comments_are_not_assignments(self, run, tmp_path):
        text = (
            "# Set API_KEY to your key from the dashboard\n"
            "# see API_KEY=...docs\n"
            "# API_KEY = the key from the dashboard\n"
            "# Example: API_KEY=abcdef-123456\n"
        )
        write(tmp_path, ".env", text)
        assert run("redact", stdin=text).stdout == text

    def test_an_open_quote_in_a_comment_hides_no_assignment_below_it(self, run, tmp_path):
        write(tmp_path, ".env", '# OLD_TOKEN="never closed\nNEW_TOKEN="tok-0123456789"\n')
        assert run("redact", stdin="tok-0123456789").stdout == "[REDACTED:NEW_TOKEN]"

    def test_an_open_quote_in_a_comment_takes_no_live_line_below_it(self, run, tmp_path):
        write(tmp_path, ".env", '# API_KEY="see vault\nDATABASE_HOST=prod-db.internal.example.com\nAPP_NAME="demo"\n')
        line = "DATABASE_HOST=prod-db.internal.example.com"
        assert run("redact", stdin=line).stdout == line
        assert run("list", "--file", ".env").stdout == "## .env\n- DATABASE_HOST\n- APP_NAME\n"
        assert run("get", "DATABASE_HOST").stdout == "prod-db.internal.example.com"

    def test_the_begin_marker_of_a_commented_out_pem_block_is_not_redacted(self, run, tmp_path):
        body = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7"
        write(tmp_path, ".env", f"# OLD_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n# {body}\n# -----END PRIVATE KEY-----\nA=1\n")
        code = 'if pem.startswith("-----BEGIN PRIVATE KEY-----"):'
        assert run("redact", stdin=code).stdout == code

    @pytest.mark.parametrize("value", ["your-api-key-here", "YOUR_API_KEY", "<your api key>", "xxxxxxxx", "XXXX-XXXX", "********", "........", "changeme"])
    def test_a_commented_out_placeholder_is_not_redacted_but_a_live_one_is(self, run, tmp_path, value):
        write(tmp_path, ".env", f"# OPENAI_API_KEY={value}\n")
        text = f'OPENAI_API_KEY={value} os.getenv("OPENAI_API_KEY", "{value}")'
        assert run("redact", stdin=text).stdout == text
        write(tmp_path, ".env", f"OPENAI_API_KEY={value}\n")
        assert run("redact", stdin=text).stdout.startswith("OPENAI_API_KEY=[REDACTED:OPENAI_API_KEY]")

    def test_a_real_looking_commented_out_value_is_still_redacted(self, run, tmp_path):
        write(tmp_path, ".env", "# STRIPE_SECRET_KEY=sk_live_PRODabc123456\n# API_TOKEN=old-token-111111\n# DB_PASSWORD=yourpass\n")
        r = run("redact", stdin="sk_live_PRODabc123456 old-token-111111 DB_PASSWORD=yourpass")
        assert r.stdout == "[REDACTED:STRIPE_SECRET_KEY] [REDACTED:API_TOKEN] DB_PASSWORD=[REDACTED:DB_PASSWORD]"

    def test_a_commented_line_inside_a_quoted_value_is_part_of_the_value(self, run, tmp_path):
        write(tmp_path, ".env", 'NOTES="first\n# OLD_TOKEN=tok-0123456789\nlast"\nB=1\n')
        assert run("list", "--file", ".env").stdout == "## .env\n- NOTES\n- B\n"
        assert run("redact", stdin="tok-0123456789").stdout == "tok-0123456789"

    def test_redaction_reads_at_most_50_env_files(self, run, tmp_path):
        for i in range(60):
            write(tmp_path, f".env.{i:03d}", f"V{i:03d}_TOKEN=value-{i:03d}-0123456789\n")
        out = run("redact", stdin="value-049-0123456789 value-050-0123456789").stdout
        assert out == "[REDACTED:V049_TOKEN] value-050-0123456789"

    def test_the_50_file_limit_is_shared_by_the_directory_and_its_parents(self, run, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "sub").mkdir()
        for i in range(30):
            write(tmp_path, f"sub/.env.{i:03d}", f"S{i:03d}_TOKEN=sub-value-{i:03d}-0123456789\n")
            write(tmp_path, f".env.{i:03d}", f"R{i:03d}_TOKEN=root-value-{i:03d}-0123456789\n")
        text = "sub-value-029-0123456789 root-value-019-0123456789 root-value-020-0123456789"
        out = run("redact", cwd=tmp_path / "sub", stdin=text).stdout
        assert out == "[REDACTED:S029_TOKEN] [REDACTED:R019_TOKEN] root-value-020-0123456789"

    def test_files_the_person_named_are_read_before_the_repositorys_own(self, run, tmp_path):
        # Five files just under 1 MiB use up the 4 MiB budget; the person's own file must not be what's dropped.
        filler = "X=1\n" * 250_000
        for i in range(5):
            write(tmp_path, f".env.{i}", filler[:1_000_000])
        write(tmp_path, "mine.env", "MY_TOKEN=mine-value-0123456789\n")
        text = "mine-value-0123456789"
        assert run("redact", env={"SECRETS_REDACT_FILES": str(tmp_path / "mine.env")}, stdin=text).stdout == "[REDACTED:MY_TOKEN]"
        assert run("redact", "--file", "mine.env", stdin=text).stdout == "[REDACTED:MY_TOKEN]"

    def test_a_value_the_get_command_prints_is_redacted(self, run, tmp_path):
        write(tmp_path, ".env", "STRIPE_SECRET=sk_live_0123456789\n")
        printed = run("get", "STRIPE_SECRET").stdout
        assert run("redact", stdin=f"out: {printed}\n").stdout == "out: [REDACTED:STRIPE_SECRET]\n"


def config(tmp_path, content, name="config.json"):
    path = tmp_path / "cfg" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return {"SECRETS_CONFIG": str(path)}


class TestConfig:
    def test_min_length_is_configurable(self, run, tmp_path):
        write(tmp_path, ".env", "SHORT_TOKEN=ab-de\n")
        env = config(tmp_path, {"redact": {"minLength": 5}})
        assert run("redact", env=env, stdin="ab-de").stdout == "[REDACTED:SHORT_TOKEN]"
        assert run("redact", stdin="ab-de").stdout == "ab-de"

    def test_names_and_excluded_names_are_configurable(self, run, tmp_path):
        write(tmp_path, ".env", "MY_SALT=salt-0123456789\nAPI_TOKEN=tok-0123456789\n")
        env = config(tmp_path, {"redact": {"names": ["*SALT*", "*TOKEN*"], "excludeNames": ["API_*"]}})
        assert run("redact", env=env, stdin="salt-0123456789 tok-0123456789").stdout == "[REDACTED:MY_SALT] tok-0123456789"
        assert run("redact", stdin="salt-0123456789 tok-0123456789").stdout == "salt-0123456789 [REDACTED:API_TOKEN]"

    def test_names_are_matched_case_insensitively(self, run, tmp_path):
        write(tmp_path, ".env", "my_salt=salt-0123456789\n")
        env = config(tmp_path, {"redact": {"names": ["*Salt*"]}})
        assert run("redact", env=env, stdin="salt-0123456789").stdout == "[REDACTED:my_salt]"

    def test_zero_means_no_minimum(self, run, tmp_path):
        write(tmp_path, ".env", "TINY_TOKEN=a-\nEMPTY_TOKEN=\n")
        env = config(tmp_path, {"redact": {"minLength": 0}})
        assert run("redact", env=env, stdin="a- ").stdout == "[REDACTED:TINY_TOKEN] "

    def test_file_patterns_are_configurable_for_every_command(self, run, tmp_path):
        write(tmp_path, ".env", "A=1\n")
        write(tmp_path, "app.secrets.env", "B_TOKEN=0123-456789\n")
        write(tmp_path, "app.secrets.env.bak", "C=1\n")
        env = config(tmp_path, {"files": {"include": ["*.env"], "exclude": ["*.bak"]}})
        assert run("has", "B_TOKEN", env=env).stdout == "B_TOKEN: set in app.secrets.env\n"
        assert list(sections(run("list", env=env).stdout)) == ["env", "app.secrets.env"]
        assert run("redact", env=env, stdin="0123-456789").stdout == "[REDACTED:B_TOKEN]"
        assert run("get", "B_TOKEN", env=env).stdout == "0123-456789"

    def test_include_patterns_can_reach_into_a_directory(self, run, tmp_path):
        (tmp_path / "config").mkdir()
        write(tmp_path, "config/.env.prod", "P=1\n")
        env = config(tmp_path, {"files": {"include": ["config/.env*"]}})
        assert run("has", "P", env=env).stdout.startswith("P: set in config/.env.prod\n")

    def test_exclude_applies_to_the_defaults_too(self, run, tmp_path):
        write(tmp_path, ".env.local", "L=1\n")
        env = config(tmp_path, {"files": {"exclude": ["*.local"]}})
        assert run("has", "L", env=env).stdout.startswith("L: not set (checked env)")

    def test_explicit_files_are_never_filtered(self, run, tmp_path):
        write(tmp_path, "x.example", "X=1\n")
        env = config(tmp_path, {})
        assert run("has", "X", "--file", "x.example", env=env).stdout == "X: set in x.example\n"

    def test_the_standard_location_is_read_when_no_override_is_given(self, run, tmp_path):
        write(tmp_path, ".env", "SHORT_TOKEN=ab-de\n")
        (tmp_path / "xdg" / "secrets-cli").mkdir(parents=True)
        (tmp_path / "xdg" / "secrets-cli" / "config.json").write_text('{"redact": {"minLength": 5}}')
        assert run("redact", stdin="ab-de").stdout == "[REDACTED:SHORT_TOKEN]"

    @pytest.mark.parametrize(
        "content, message",
        [
            ("{not json", "can't read config"),
            ('{"redact": {"minLenght": 5}}', "unknown setting redact.minLenght"),
            ('{"colour": 1}', "unknown setting colour"),
            ('{"redact": {"minLength": "5"}}', "redact.minLength must be a non-negative integer"),
            ('{"redact": {"minLength": -1}}', "redact.minLength must be a non-negative integer"),
            ('{"redact": {"minLength": true}}', "redact.minLength must be a non-negative integer"),
            ('{"files": {"include": ".env"}}', "files.include must be a list of strings"),
            ('{"redact": {"names": [1]}}', "redact.names must be a list of strings"),
            ('{"redact": {"urlPasswords": 1}}', "redact.urlPasswords must be true or false"),
            ('{"files": 3}', "files must be an object"),
            ("[]", "the config must be an object"),
        ],
    )
    def test_an_invalid_config_is_an_error_not_ignored(self, run, tmp_path, content, message):
        env = config(tmp_path, content)
        for args in (("has", "A"), ("list",), ("redact",)):
            r = run(*args, env=env, stdin="text")
            assert r.returncode == 1 and r.stdout == ""
            assert message in r.stderr

    def test_an_override_that_does_not_exist_is_an_error(self, run, tmp_path):
        r = run("has", "A", env={"SECRETS_CONFIG": str(tmp_path / "nope.json")})
        assert r.returncode == 1
        assert "SECRETS_CONFIG points to a file that doesn't exist" in r.stderr
