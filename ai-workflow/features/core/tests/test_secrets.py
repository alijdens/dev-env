import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SECRETS = Path(__file__).resolve().parent.parent / "bin" / "secrets"


@pytest.fixture
def run(tmp_path):
    def _run(*args, env=None, stdin="", cwd=None):
        # A minimal environment, so the developer's own variables and config never leak into a test.
        full_env = {"PATH": os.environ["PATH"], "XDG_CONFIG_HOME": str(tmp_path / "xdg"), **(env or {})}
        return subprocess.run(
            [sys.executable, str(SECRETS), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=full_env,
            cwd=cwd or tmp_path,
        )

    return _run


def write(tmp_path, name, text):
    (tmp_path / name).write_text(text)


def sections(out):
    """Parses the markdown `has` and `list` print into {source: [lines]}."""
    result, current = {}, None
    for line in out.splitlines():
        if line.startswith("## "):
            current = result.setdefault(line[3:], [])
        elif line and current is not None:
            current.append(line)
    return result


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
        ],
    )
    def test_parses_env_file_syntax(self, run, tmp_path, line, expected):
        write(tmp_path, ".env", line + "\nOTHER=1\n")
        assert run("get", "K").stdout == expected

    def test_last_assignment_wins(self, run, tmp_path):
        write(tmp_path, ".env", "K=first\nK=second\n")
        assert run("get", "K").stdout == "second"

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
        write(tmp_path, "a.env", "A_SECRET=aaaaaaaaaa\n")
        write(tmp_path, "b.env", "B_SECRET=bbbbbbbbbb\n")
        r = run(
            "redact",
            "--file", "a.env",
            env={"SECRETS_REDACT_FILES": f"{tmp_path / 'b.env'}:/does/not/exist"},
            stdin="aaaaaaaaaa bbbbbbbbbb",
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
        write(tmp_path, ".env", "FIVE_TOKEN=12345\nSIX_TOKEN=123456\n")
        assert run("redact", stdin="12345 123456").stdout == "12345 [REDACTED:SIX_TOKEN]"

    @pytest.mark.parametrize("name", ["SECRET", "MY_SECRET_X", "GH_TOKEN", "tokens", "DB_PASSWORD", "DB_PASSWD", "SSH_PASSPHRASE", "KEY", "API_KEY", "KEY_ID", "AWS_KEY_ID", "PASS", "DB_PASS", "GOOGLE_CREDENTIALS", "OPENAIAPIKEY", "lower_token"])
    def test_default_names_that_are_redacted(self, run, tmp_path, name):
        write(tmp_path, ".env", f"{name}=value-0123456789\n")
        assert run("redact", stdin="value-0123456789").stdout == f"[REDACTED:{name}]"

    @pytest.mark.parametrize("name", ["MONKEY", "KEYBOARD_LAYOUT", "KEYCHAIN_X", "PASSENGER", "PASSTHROUGH", "HTTP_PORT", "GIT_AUTHOR_NAME", "SSH_AUTH_SOCK", "TOKEN_TTL", "SECRET_FILE", "GOOGLE_CREDENTIALS_PATH", "KEY_PREFIX", "API_KEY_LENGTH"])
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
            ("a https://u:one@x and https://v:two@y.", "a https://u:[REDACTED:url-password]@x and https://v:[REDACTED:url-password]@y."),
            ("DATABASE_URL=mysql://root:hunter2@db\nnext line", "DATABASE_URL=mysql://root:[REDACTED:url-password]@db\nnext line"),
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
            "12:34:56@ not a url",
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
        write(tmp_path, ".env", "SHORT_TOKEN=abcde\n")
        env = config(tmp_path, {"redact": {"minLength": 5}})
        assert run("redact", env=env, stdin="abcde").stdout == "[REDACTED:SHORT_TOKEN]"
        assert run("redact", stdin="abcde").stdout == "abcde"

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
        write(tmp_path, ".env", "TINY_TOKEN=ab\nEMPTY_TOKEN=\n")
        env = config(tmp_path, {"redact": {"minLength": 0}})
        assert run("redact", env=env, stdin="ab ").stdout == "[REDACTED:TINY_TOKEN] "

    def test_file_patterns_are_configurable_for_every_command(self, run, tmp_path):
        write(tmp_path, ".env", "A=1\n")
        write(tmp_path, "app.secrets.env", "B_TOKEN=0123456789\n")
        write(tmp_path, "app.secrets.env.bak", "C=1\n")
        env = config(tmp_path, {"files": {"include": ["*.env"], "exclude": ["*.bak"]}})
        assert run("has", "B_TOKEN", env=env).stdout == "B_TOKEN: set in app.secrets.env\n"
        assert list(sections(run("list", env=env).stdout)) == ["env", "app.secrets.env"]
        assert run("redact", env=env, stdin="0123456789").stdout == "[REDACTED:B_TOKEN]"
        assert run("get", "B_TOKEN", env=env).stdout == "0123456789"

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
        write(tmp_path, ".env", "SHORT_TOKEN=abcde\n")
        (tmp_path / "xdg" / "secrets-cli").mkdir(parents=True)
        (tmp_path / "xdg" / "secrets-cli" / "config.json").write_text('{"redact": {"minLength": 5}}')
        assert run("redact", stdin="abcde").stdout == "[REDACTED:SHORT_TOKEN]"

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
