#!/usr/bin/env bash
# Makes ~/.zshrc and/or ~/.bashrc source aliases.sh from this repo. Safe to re-run.
set -euo pipefail

aliases_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/aliases.sh"
# The marker identifies our line on re-runs, so a moved repo updates the path instead of adding a second line.
marker="# dev-env:aliases"
source_line="source \"$aliases_file\" $marker"

rc_files=()
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$rc" ]; then rc_files+=("$rc"); fi
done
if [ ${#rc_files[@]} -eq 0 ]; then
  case "$(basename "${SHELL:-}")" in
    zsh) rc_files=("$HOME/.zshrc") ;;
    *) rc_files=("$HOME/.bashrc") ;;
  esac
  touch "${rc_files[0]}"
fi

for rc in "${rc_files[@]}"; do
  tmp="$(mktemp)"
  # Only exact duplicates of aliases.sh lines are removed; a same-named alias with a different
  # definition is kept (with a warning) so local customizations are never silently lost.
  awk -v aliases_file="$aliases_file" -v marker="$marker" -v source_line="$source_line" -v rc="$rc" '
    function rtrim(s) { sub(/[ \t]+$/, "", s); return s }
    function alias_name(s) { sub(/^[ \t]*alias[ \t]+/, "", s); sub(/=.*/, "", s); return s }
    BEGIN {
      while ((getline line < aliases_file) > 0) {
        if (line ~ /^alias /) { defs[rtrim(line)] = 1; names[alias_name(line)] = 1 }
      }
    }
    index($0, marker) { if (!found) print source_line; found = 1; next }
    rtrim($0) in defs { print rc ": removed duplicate: " $0 > "/dev/stderr"; next }
    /^[ \t]*alias[ \t]+/ && (alias_name($0) in names) {
      print rc ": kept differing definition: " $0 > "/dev/stderr"
    }
    { print }
    END { if (!found) { print ""; print source_line } }
  ' "$rc" > "$tmp"

  if cmp -s "$tmp" "$rc"; then
    echo "$rc: already up to date"
  else
    cp "$rc" "$rc.bak.$(date +%Y%m%d%H%M%S)"
    # Write through instead of mv so a symlinked rc file stays a symlink.
    cat "$tmp" > "$rc"
    echo "$rc: updated (backup saved next to it)"
  fi
  rm -f "$tmp"
done
