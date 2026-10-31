#!/usr/bin/env bash
# Renders AGENTS.md and skills/ (resolving their {{AI_WORKFLOW_DOCS_DIR}} placeholder to this
# checkout's docs/ dir) and symlinks the results, plus docs/ itself, into each selected tool's
# config dir. Skills are linked one by one, so skills installed from elsewhere coexist with them.
# Also adds bin/ to PATH in the shell rc files, so docs can reference its commands by name, and
# installs git hooks that re-run `--refresh` after pulls and checkouts, so new or changed skills
# don't wait for a manual re-install. For Claude Code it also offers to link the plugins under
# plugins/claude-code/ (yes by default; `--no-plugins` skips the question).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENDERED_DIR="$REPO_DIR/.rendered"
RENDERED_AGENTS_MD="$RENDERED_DIR/AGENTS.md"
RENDERED_SKILLS_DIR="$RENDERED_DIR/skills"
CLAUDE_PLUGINS_INSTALL="$REPO_DIR/plugins/claude-code/install.sh"
CLAUDE_PLUGINS_DIR="$REPO_DIR/plugins/claude-code"

# tool_name:target_dir:target_filename
TOOLS=(
  "claude:$HOME/.claude:CLAUDE.md"
  "codex:$HOME/.codex:AGENTS.md"
  "agents:$HOME/.agents:AGENTS.md"
)

render() {
  local tmp file docs_dir
  # Escape sed's replacement specials, so a checkout path with `#`, `&` or `\` renders verbatim.
  docs_dir="$(printf '%s' "$REPO_DIR/docs" | sed 's/[&#\\]/\\&/g')"
  mkdir -p "$RENDERED_DIR"
  sed "s#{{AI_WORKFLOW_DOCS_DIR}}#$docs_dir#g" "$REPO_DIR/AGENTS.md" > "$RENDERED_AGENTS_MD"

  rm -rf "$RENDERED_SKILLS_DIR"
  cp -r "$REPO_DIR/skills" "$RENDERED_SKILLS_DIR"
  while IFS= read -r -d '' file; do
    tmp="$(mktemp)"
    sed "s#{{AI_WORKFLOW_DOCS_DIR}}#$docs_dir#g" "$file" > "$tmp"
    mv "$tmp" "$file"
  done < <(find "$RENDERED_SKILLS_DIR" -type f -name "*.md" -print0)
}

usage() {
  echo "Usage: $0 [--no-plugins] [tool...]"
  echo "       $0 --refresh"
  echo "  Available tools: $(for t in "${TOOLS[@]}"; do echo -n "${t%%:*} "; done)"
  echo "  With no arguments, installs all of the above."
  echo "  --refresh re-installs only the tools already installed (used by the git hooks)."
  echo "  --no-plugins skips the Claude Code plugins question (plugins/claude-code/)."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

plugins_answer=""
if [[ "${1:-}" == "--no-plugins" ]]; then
  plugins_answer="n"
  shift
fi

refresh=0
if [[ "${1:-}" == "--refresh" ]]; then
  refresh=1
  selected=()
  for t in "${TOOLS[@]}"; do
    rest="${t#*:}"
    if [[ "$(readlink "${rest%%:*}/${rest#*:}" 2>/dev/null)" == "$RENDERED_AGENTS_MD" ]]; then
      selected+=("${t%%:*}")
    fi
  done
elif [[ $# -eq 0 ]]; then
  selected=($(for t in "${TOOLS[@]}"; do echo "${t%%:*}"; done))
else
  selected=()
  for arg in "$@"; do
    case "$arg" in
      .agents|generic) selected+=("agents") ;;
      *) selected+=("$arg") ;;
    esac
  done
fi

link() {
  local src="$1" dest="$2"
  if [[ -L "$dest" ]]; then
    if [[ "$(readlink "$dest")" == "$src" ]]; then
      echo "  already linked: $dest"
      return
    fi
    rm "$dest"
  elif [[ -e "$dest" ]]; then
    local backup="$dest.bak.$(date +%Y%m%d%H%M%S)"
    echo "  backing up existing $dest -> $backup"
    mv "$dest" "$backup"
  fi
  ln -s "$src" "$dest"
  echo "  linked: $dest -> $src"
}

# The marker identifies our line on re-runs, so a moved repo updates the path instead of adding a second line.
add_bin_to_path() {
  local marker="# dev-env:ai-workflow-bin"
  local path_line="export PATH=\"$REPO_DIR/bin:\$PATH\" $marker"
  local rc_files=() rc tmp
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [[ -f "$rc" ]]; then rc_files+=("$rc"); fi
  done
  if [[ ${#rc_files[@]} -eq 0 ]]; then
    case "$(basename "${SHELL:-}")" in
      zsh) rc_files=("$HOME/.zshrc") ;;
      *) rc_files=("$HOME/.bashrc") ;;
    esac
    touch "${rc_files[0]}"
  fi

  echo "Adding $REPO_DIR/bin to PATH..."
  for rc in "${rc_files[@]}"; do
    tmp="$(mktemp)"
    { grep -vF "$marker" "$rc" || true; echo "$path_line"; } > "$tmp"
    if cmp -s "$tmp" "$rc"; then
      echo "  already up to date: $rc"
    else
      # Write through instead of mv so a symlinked rc file stays a symlink.
      cat "$tmp" > "$rc"
      echo "  updated: $rc"
    fi
    rm -f "$tmp"
  done
}

link_skills() {
  local dir="$1" skill dest
  # Earlier versions linked the whole skills dir; it holds only our rendered copies, so drop it.
  if [[ -L "$dir" && "$(readlink "$dir")" == "$RENDERED_SKILLS_DIR" ]]; then
    rm "$dir"
  fi
  mkdir -p "$dir"
  for skill in "$RENDERED_SKILLS_DIR"/*/; do
    skill="${skill%/}"
    link "$skill" "$dir/$(basename "$skill")"
  done
  for dest in "$dir"/*; do
    if [[ -L "$dest" && "$(readlink "$dest")" == "$RENDERED_SKILLS_DIR/"* && ! -e "$dest" ]]; then
      rm "$dest"
      echo "  removed stale skill: $dest"
    fi
  done
}

install_git_hooks() {
  local marker="# dev-env:ai-workflow-refresh"
  local hooks_dir hook path
  # Not fatal: a tarball copy or a git too old for --path-format still gets the tools installed.
  if ! hooks_dir="$(git -C "$REPO_DIR" rev-parse --path-format=absolute --git-path hooks 2>/dev/null)"; then
    echo "  skipping git hooks: $REPO_DIR isn't a git checkout git can read" >&2
    return
  fi
  mkdir -p "$hooks_dir"
  # post-rewrite covers `git pull --rebase`, which doesn't run post-merge.
  for hook in post-merge post-checkout post-rewrite; do
    path="$hooks_dir/$hook"
    if [[ -e "$path" ]] && ! grep -qF "$marker" "$path"; then
      echo "  skipping git hook $path: it already exists and isn't ours" >&2
      continue
    fi
    printf '#!/bin/sh\n%s\nexec "%s/install.sh" --refresh >/dev/null\n' "$marker" "$REPO_DIR" > "$path"
    chmod +x "$path"
  done
}

# A plugin is installed when its link in ~/.claude/skills points into plugins/claude-code/.
claude_plugins_installed() {
  local dest
  for dest in "$HOME/.claude/skills"/*; do
    if [[ -L "$dest" && "$(readlink "$dest")" == "$CLAUDE_PLUGINS_DIR/"* ]]; then
      return 0
    fi
  done
  return 1
}

install_claude_plugins() {
  local answer="$plugins_answer"
  if [[ "$refresh" == "1" ]]; then
    # Hooks run unattended: only keep what was already installed up to date.
    claude_plugins_installed && answer="y" || answer="n"
  elif [[ -z "$answer" ]]; then
    if [[ -t 0 ]]; then
      read -r -p "Install the Claude Code plugins in plugins/claude-code (sdd-decisions band)? [Y/n] " answer
    fi
    answer="${answer:-y}"
  fi
  case "$answer" in
    y|Y|yes|YES) echo "Installing Claude Code plugins..."; "$CLAUDE_PLUGINS_INSTALL" ;;
    *) echo "Skipping Claude Code plugins ($CLAUDE_PLUGINS_INSTALL installs them later)." ;;
  esac
}

render
add_bin_to_path
install_git_hooks

# The `+` expansion keeps an empty selection (e.g. `--refresh` with nothing installed) from
# tripping `set -u` on bash 3.2 (macOS).
for tool in ${selected[@]+"${selected[@]}"}; do
  found=""
  for entry in "${TOOLS[@]}"; do
    name="${entry%%:*}"
    rest="${entry#*:}"
    dir="${rest%%:*}"
    file="${rest#*:}"
    if [[ "$name" == "$tool" ]]; then
      found=1
      echo "Installing for $name..."
      mkdir -p "$dir"
      link "$RENDERED_AGENTS_MD" "$dir/$file"
      link "$REPO_DIR/docs" "$dir/docs"
      link_skills "$dir/skills"
      if [[ "$name" == "claude" ]]; then
        install_claude_plugins
      fi
    fi
  done
  if [[ -z "$found" ]]; then
    echo "Unknown tool: $tool" >&2
    usage >&2
    exit 1
  fi
done
