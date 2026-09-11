#!/usr/bin/env bash
# Prints the newest cleanrr tag, without the leading "v".
set -euo pipefail

args=(-sfL)
if [[ -n "${TOKEN:-}" ]]; then
  args+=(-H "Authorization: token ${TOKEN}")
fi

curl "${args[@]}" "https://api.github.com/repos/Zariel/cleanrr/tags?per_page=100" \
  | grep -o '"name": *"v[0-9][^"]*"' \
  | sed 's/.*"v//; s/"$//' \
  | sort -V \
  | tail -n1
