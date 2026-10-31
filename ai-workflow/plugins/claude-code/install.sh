#!/usr/bin/env bash
# Links each plugin in this directory into Claude Code's skills dir, where plugins load at
# session start and reload when their files change. Re-running is safe; links to plugins
# removed from here are cleaned up. `--uninstall` removes the links.
set -euo pipefail

PLUGINS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

usage() {
  echo "Usage: $0 [--uninstall]"
  echo "  Links the plugins under $PLUGINS_DIR into $SKILLS_DIR."
}

remove_stale() {
  local dest
  for dest in "$SKILLS_DIR"/*; do
    if [[ -L "$dest" && "$(readlink "$dest")" == "$PLUGINS_DIR/"* && ! -e "$dest" ]]; then
      rm "$dest"
      echo "  removed stale plugin: $dest"
    fi
  done
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --uninstall)
    for dest in "$SKILLS_DIR"/*; do
      if [[ -L "$dest" && "$(readlink "$dest")" == "$PLUGINS_DIR/"* ]]; then
        rm "$dest"
        echo "  removed: $dest"
      fi
    done
    exit 0 ;;
  "") ;;
  *) usage >&2; exit 1 ;;
esac

mkdir -p "$SKILLS_DIR"
remove_stale
for manifest in "$PLUGINS_DIR"/*/.claude-plugin/plugin.json; do
  [[ -f "$manifest" ]] || continue
  plugin="$(dirname "$(dirname "$manifest")")"
  dest="$SKILLS_DIR/$(basename "$plugin")"
  if [[ -L "$dest" ]]; then
    if [[ "$(readlink "$dest")" == "$plugin" ]]; then
      echo "  already linked: $dest"
      continue
    fi
    rm "$dest"
  elif [[ -e "$dest" ]]; then
    backup="$dest.bak.$(date +%Y%m%d%H%M%S)"
    echo "  backing up existing $dest -> $backup"
    mv "$dest" "$backup"
  fi
  ln -s "$plugin" "$dest"
  echo "  linked: $dest -> $plugin"
done
