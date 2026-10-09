#!/usr/bin/env bash
# Renders AGENTS.md (resolving its {{AI_WORKFLOW_DOCS_DIR}} placeholder to this checkout's
# docs/ dir) and symlinks the result, plus docs/ itself, into each selected tool's config dir.
# Also adds bin/ to PATH in the shell rc files, so docs can reference its commands by name.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENDERED_DIR="$REPO_DIR/.rendered"
RENDERED_AGENTS_MD="$RENDERED_DIR/AGENTS.md"

# tool_name:target_dir:target_filename
TOOLS=(
  "claude:$HOME/.claude:CLAUDE.md"
  "codex:$HOME/.codex:AGENTS.md"
)

render() {
  mkdir -p "$RENDERED_DIR"
  sed "s#{{AI_WORKFLOW_DOCS_DIR}}#$REPO_DIR/docs#g" "$REPO_DIR/AGENTS.md" > "$RENDERED_AGENTS_MD"
}

usage() {
  echo "Usage: $0 [tool...]"
  echo "  Available tools: $(for t in "${TOOLS[@]}"; do echo -n "${t%%:*} "; done)"
  echo "  With no arguments, installs all of the above."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -eq 0 ]]; then
  selected=($(for t in "${TOOLS[@]}"; do echo "${t%%:*}"; done))
else
  selected=("$@")
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

render
add_bin_to_path

for tool in "${selected[@]}"; do
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
    fi
  done
  if [[ -z "$found" ]]; then
    echo "Unknown tool: $tool" >&2
    usage >&2
    exit 1
  fi
done
