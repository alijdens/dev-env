#!/usr/bin/env bash
# Renders the selected features under features/ into .rendered/ and symlinks the results into each
# selected tool's config dir. A feature is a directory whose optional parts are found by name:
# docs/, skills/<skill>/, bin/, shell/*.sh and plugins/claude-code/<plugin>/; `core` (AGENTS.md
# included) is always installed, so features' docs may reference its docs. Core docs render to
# docs/, a feature's to docs/<feature>/, with the {{AI_WORKFLOW_DOCS_DIR}} placeholder resolved to
# the rendered docs/. The selection is kept in .rendered/features, so later runs and the git hooks
# install the same set until `--features` changes it; parts of deselected features are unlinked.
#
# Tools only ever see the rendered copy, so what this checkout has checked out doesn't matter until
# the installer runs again: an agent run that started on one branch keeps its commands, docs,
# skills and plugins while the checkout moves on. Skills and plugins are linked one by one, so ones
# installed from elsewhere coexist with them. The shell rc files source the rendered env.sh, which
# puts the rendered bin/ on PATH (so docs can reference its commands by name) and sources the
# features' shell snippets. Git hooks re-run `--refresh` after pulls and checkouts on the default
# branch, so changes pulled there don't wait for a manual re-install.
#
# AI_WORKFLOW_HOME=<dir> installs into <dir> instead of $HOME (rc files included) and skips the git
# hooks, for trying the installer without touching the real setup; AI_WORKFLOW_RENDERED_DIR moves
# the rendered copy.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FEATURES_DIR="$REPO_DIR/features"
INSTALL_HOME="${AI_WORKFLOW_HOME:-$HOME}"
RENDERED_DIR="${AI_WORKFLOW_RENDERED_DIR:-$REPO_DIR/.rendered}"
RENDERED_AGENTS_MD="$RENDERED_DIR/AGENTS.md"
RENDERED_SKILLS_DIR="$RENDERED_DIR/skills"
RENDERED_DOCS_DIR="$RENDERED_DIR/docs"
RENDERED_BIN_DIR="$RENDERED_DIR/bin"
RENDERED_SHELL_DIR="$RENDERED_DIR/shell"
RENDERED_PLUGINS_DIR="$RENDERED_DIR/plugins/claude-code"
RENDERED_ENV="$RENDERED_DIR/env.sh"
RENDERED_FEATURES="$RENDERED_DIR/features"

# tool_name:target_dir:target_filename
TOOLS=(
  "claude:$INSTALL_HOME/.claude:CLAUDE.md"
  "codex:$INSTALL_HOME/.codex:AGENTS.md"
  "agents:$INSTALL_HOME/.agents:AGENTS.md"
)

available_features() {
  local dir
  for dir in "$FEATURES_DIR"/*/; do
    dir="$(basename "$dir")"
    if [[ "$dir" != core ]]; then echo "$dir"; fi
  done
}

usage() {
  echo "Usage: $0 [--features <name>[,<name>...]|none] [tool...]"
  echo "       $0 --refresh"
  echo "       $0 --list"
  echo "  Available tools: $(for t in "${TOOLS[@]}"; do echo -n "${t%%:*} "; done)"
  echo "  Available features: $(available_features | tr '\n' ' ')(core is always installed)"
  echo "  With no tools, installs for all of them. Without --features, installs the features installed"
  echo "  last time, or all of them on a first install; --features replaces that selection."
  echo "  --refresh re-installs only the tools already installed (used by the git hooks)."
  echo "  --list shows the features and which ones are installed."
}

refresh=0
list=0
features_arg=""
has_features_arg=0
tool_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --refresh) refresh=1 ;;
    --list) list=1 ;;
    --features)
      if [[ $# -lt 2 ]]; then usage >&2; exit 1; fi
      features_arg="$2"; has_features_arg=1; shift ;;
    --features=*) features_arg="${1#*=}"; has_features_arg=1 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    *) tool_args+=("$1") ;;
  esac
  shift
done
if [[ "$refresh" == 1 && ( "$has_features_arg" == 1 || ${#tool_args[@]} -gt 0 ) ]]; then
  echo "--refresh takes no tools or features: it re-installs what is installed." >&2
  exit 1
fi

installed_features=()
if [[ -f "$RENDERED_FEATURES" ]]; then
  while IFS= read -r name; do
    # Kept even when this checkout lacks the feature (e.g. main checked out while it lives on a branch):
    # render skips it, and the selection brings it back once a checkout has it again.
    if [[ -n "$name" && "$name" != */* ]]; then installed_features+=("$name"); fi
  done < "$RENDERED_FEATURES"
fi

if [[ "$list" == 1 ]]; then
  echo "core (always installed)"
  for name in $(available_features); do
    mark=""
    for f in ${installed_features[@]+"${installed_features[@]}"}; do
      if [[ "$f" == "$name" ]]; then mark=" (installed)"; fi
    done
    echo "$name$mark"
  done
  for f in ${installed_features[@]+"${installed_features[@]}"}; do
    if [[ ! -d "$FEATURES_DIR/$f" ]]; then echo "$f (installed, not in this checkout)"; fi
  done
  exit 0
fi

features=()
if [[ "$has_features_arg" == 1 ]]; then
  if [[ "$features_arg" != none ]]; then
    IFS=, read -r -a names <<< "$features_arg"
    for name in ${names[@]+"${names[@]}"}; do
      if [[ -z "$name" || "$name" == core || "$name" == */* || ! -d "$FEATURES_DIR/$name" ]]; then
        echo "Unknown feature: $name" >&2
        usage >&2
        exit 1
      fi
      case " ${features[*]-} " in *" $name "*) ;; *) features+=("$name") ;; esac
    done
  fi
elif [[ -f "$RENDERED_FEATURES" ]]; then
  features=(${installed_features[@]+"${installed_features[@]}"})
else
  features=($(available_features))
fi

default_branch() {
  local ref
  if ref="$(git -C "$REPO_DIR" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)"; then
    echo "${ref#origin/}"
  else
    echo main
  fi
}

if [[ "$refresh" == 1 ]]; then
  # Hooks fire on every checkout and pull. Only the default branch refreshes the installed copy:
  # a feature branch of this repo (which may lack a skill or a command) must not change what
  # running agents use. An explicit `install.sh` renders whatever is checked out.
  if [[ "$(git -C "$REPO_DIR" symbolic-ref --short -q HEAD 2>/dev/null || true)" != "$(default_branch)" ]]; then
    exit 0
  fi
  selected=()
  for t in "${TOOLS[@]}"; do
    rest="${t#*:}"
    if [[ "$(readlink "${rest%%:*}/${rest#*:}" 2>/dev/null)" == "$RENDERED_AGENTS_MD" ]]; then
      selected+=("${t%%:*}")
    fi
  done
elif [[ ${#tool_args[@]} -eq 0 ]]; then
  selected=($(for t in "${TOOLS[@]}"; do echo "${t%%:*}"; done))
else
  selected=()
  for arg in "${tool_args[@]}"; do
    case "$arg" in
      .agents|generic) selected+=("agents") ;;
      *) selected+=("$arg") ;;
    esac
  done
fi
for tool in ${selected[@]+"${selected[@]}"}; do
  if ! printf '%s\n' "${TOOLS[@]}" | grep -q "^$tool:"; then
    echo "Unknown tool: $tool" >&2
    usage >&2
    exit 1
  fi
done

# Copies each entry of $1 into $2. Features share the rendered skills/, bin/, shell/ and plugins/,
# so two of them shipping the same name is an error rather than one silently replacing the other.
copy_entries() {
  local src="$1" dest="$2" entry
  [[ -d "$src" ]] || return 0
  mkdir -p "$dest"
  for entry in "$src"/*; do
    [[ -e "$entry" ]] || continue
    if [[ -e "$dest/$(basename "$entry")" ]]; then
      echo "Can't render $entry: another feature already provides ${dest#"$RENDER_NEW/"}/$(basename "$entry")" >&2
      return 1
    fi
    cp -r "$entry" "$dest/"
  done
}

RENDER_NEW="$RENDERED_DIR.new"
RENDER_OLD="$RENDERED_DIR.old"

render() {
  local new="$RENDER_NEW" old="$RENDER_OLD" tmp file docs_dir feature src snippet
  # Escape sed's replacement specials, so a path with `#`, `&` or `\` renders verbatim.
  docs_dir="$(printf '%s' "$RENDERED_DOCS_DIR" | sed 's/[&#\\]/\\&/g')"
  rm -rf "$new" "$old"
  mkdir -p "$new/docs"
  # A failed render leaves the installed copy as it was.
  trap 'rm -rf "$RENDER_NEW"' EXIT
  sed "s#{{AI_WORKFLOW_DOCS_DIR}}#$docs_dir#g" "$FEATURES_DIR/core/AGENTS.md" > "$new/AGENTS.md"
  for feature in core ${features[@]+"${features[@]}"}; do
    src="$FEATURES_DIR/$feature"
    if [[ ! -d "$src" ]]; then
      echo "Skipping $feature: not in this checkout (kept in the selection)"
      continue
    fi
    if [[ "$feature" == core ]]; then
      copy_entries "$src/docs" "$new/docs"
    elif [[ -d "$src/docs" ]]; then
      if [[ -e "$new/docs/$feature" ]]; then
        echo "Can't render $src/docs: core already provides docs/$feature" >&2
        return 1
      fi
      cp -r "$src/docs" "$new/docs/$feature"
    fi
    copy_entries "$src/skills" "$new/skills"
    copy_entries "$src/bin" "$new/bin"
    copy_entries "$src/shell" "$new/shell"
    copy_entries "$src/plugins/claude-code" "$new/plugins/claude-code"
  done
  # Claude Code finds skills and plugins in the same dir, so a plugin can't share a skill's name.
  for src in "$new/plugins/claude-code"/*/; do
    [[ -d "$src" ]] || continue
    src="$(basename "$src")"
    if [[ -e "$new/skills/$src" ]]; then
      echo "Can't render plugin $src: a skill has the same name, and both link into ~/.claude/skills/$src" >&2
      return 1
    fi
  done
  while IFS= read -r -d '' file; do
    tmp="$(mktemp)"
    sed "s#{{AI_WORKFLOW_DOCS_DIR}}#$docs_dir#g" "$file" > "$tmp"
    mv "$tmp" "$file"
  done < <(find "$new/docs" "$new/skills" -type f -name "*.md" -print0 2>/dev/null)
  {
    echo "# Generated by $REPO_DIR/install.sh and sourced from the shell rc files."
    echo "export PATH=\"$RENDERED_BIN_DIR:\$PATH\""
    for snippet in "$new/shell"/*.sh; do
      if [[ -f "$snippet" ]]; then echo ". \"$RENDERED_SHELL_DIR/$(basename "$snippet")\""; fi
    done
  } > "$new/env.sh"
  printf '%s\n' ${features[@]+"${features[@]}"} > "$new/features"
  # Build the whole tree first and swap it in, so a session starting mid-render never sees a
  # half-copied skills dir.
  if [[ -d "$RENDERED_DIR" ]]; then mv "$RENDERED_DIR" "$old"; fi
  mv "$new" "$RENDERED_DIR"
  trap - EXIT
  rm -rf "$old"
}

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
source_env_from_rc() {
  local marker="# dev-env:ai-workflow-env"
  # MIGRATION(feature-dirs): earlier versions added a PATH line with this marker instead of
  # sourcing env.sh. Remove once every install has run this version.
  local old_marker="# dev-env:ai-workflow-bin"
  local source_line="if [ -f \"$RENDERED_ENV\" ]; then . \"$RENDERED_ENV\"; fi $marker"
  local rc_files=() rc tmp
  for rc in "$INSTALL_HOME/.zshrc" "$INSTALL_HOME/.bashrc"; do
    if [[ -f "$rc" ]]; then rc_files+=("$rc"); fi
  done
  if [[ ${#rc_files[@]} -eq 0 ]]; then
    case "$(basename "${SHELL:-}")" in
      zsh) rc_files=("$INSTALL_HOME/.zshrc") ;;
      *) rc_files=("$INSTALL_HOME/.bashrc") ;;
    esac
    mkdir -p "$INSTALL_HOME"
    touch "${rc_files[0]}"
  fi

  echo "Sourcing $RENDERED_ENV from the shell rc files..."
  for rc in "${rc_files[@]}"; do
    tmp="$(mktemp)"
    { grep -vF -e "$marker" -e "$old_marker" "$rc" || true; echo "$source_line"; } > "$tmp"
    if cmp -s "$tmp" "$rc"; then
      echo "  already up to date: $rc"
    else
      # Write through instead of mv so a symlinked rc file stays a symlink.
      cat "$tmp" > "$rc"
      echo "  updated: $rc (open shells keep their old environment until restarted)"
    fi
    rm -f "$tmp"
  done
}

# Links each directory in $1 into $2.
link_entries() {
  local src_dir="$1" dest_dir="$2" entry
  mkdir -p "$dest_dir"
  for entry in "$src_dir"/*/; do
    [[ -d "$entry" ]] || continue
    entry="${entry%/}"
    link "$entry" "$dest_dir/$(basename "$entry")"
  done
}

# Removes links in $1 that point into $2 but no longer resolve: skills and plugins removed from
# the repo or belonging to a deselected feature. Runs for every tool, not only the selected ones,
# since they all share the rendered copy.
remove_stale_links() {
  local dir="$1" target="$2" dest
  [[ -d "$dir" ]] || return 0
  for dest in "$dir"/*; do
    if [[ -L "$dest" && "$(readlink "$dest")" == "$target/"* && ! -e "$dest" ]]; then
      rm "$dest"
      echo "  removed stale link: $dest"
    fi
  done
}

install_git_hooks() {
  local marker="# dev-env:ai-workflow-refresh"
  local hooks_dir hook path
  if [[ -n "${AI_WORKFLOW_HOME:-}" ]]; then
    echo "  skipping git hooks: AI_WORKFLOW_HOME is set (a trial install)"
    return
  fi
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

render
echo "Rendered core${features[@]+ and ${features[*]}} into $RENDERED_DIR"
source_env_from_rc
install_git_hooks

# The `+` expansion keeps an empty selection (e.g. `--refresh` with nothing installed) from
# tripping `set -u` on bash 3.2 (macOS).
for tool in ${selected[@]+"${selected[@]}"}; do
  for entry in "${TOOLS[@]}"; do
    name="${entry%%:*}"
    rest="${entry#*:}"
    dir="${rest%%:*}"
    file="${rest#*:}"
    if [[ "$name" == "$tool" ]]; then
      echo "Installing for $name..."
      mkdir -p "$dir"
      link "$RENDERED_AGENTS_MD" "$dir/$file"
      link "$RENDERED_DOCS_DIR" "$dir/docs"
      # Earlier versions linked the whole skills dir; it holds only our rendered copies, so drop it.
      if [[ -L "$dir/skills" && "$(readlink "$dir/skills")" == "$RENDERED_SKILLS_DIR" ]]; then
        rm "$dir/skills"
      fi
      link_entries "$RENDERED_SKILLS_DIR" "$dir/skills"
      if [[ "$name" == claude ]]; then
        link_entries "$RENDERED_PLUGINS_DIR" "$dir/skills"
      fi
    fi
  done
done

for entry in "${TOOLS[@]}"; do
  rest="${entry#*:}"
  dir="${rest%%:*}"
  remove_stale_links "$dir/skills" "$RENDERED_SKILLS_DIR"
  remove_stale_links "$dir/skills" "$RENDERED_PLUGINS_DIR"
  # MIGRATION(feature-dirs): earlier versions linked plugins straight from plugins/claude-code/,
  # which moved under features/. Remove once every install has run this version.
  remove_stale_links "$dir/skills" "$REPO_DIR/plugins/claude-code"
done
