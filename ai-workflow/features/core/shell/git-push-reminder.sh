# Aliases can't match multi-word commands like `git push`, so wrap `git` instead.
git() {
  command git "$@" || return
  if [ "$1" = push ]; then
    echo "<reminder>Read and update the PR description to reflect the changes pushed, if not done already.</reminder>" >&2
  fi
}
