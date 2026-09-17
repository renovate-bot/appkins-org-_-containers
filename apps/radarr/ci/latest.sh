#!/usr/bin/env bash
# Prints the newest stable Radarr release tag, without the leading "v".
# GitHub releases are only cut from Radarr's master (stable) branch.
set -euo pipefail

args=(-sfL)
if [[ -n "${TOKEN:-}" ]]; then
  args+=(-H "Authorization: token ${TOKEN}")
fi

curl "${args[@]}" "https://api.github.com/repos/Radarr/Radarr/releases/latest" \
  | grep -o '"tag_name": *"v[0-9][^"]*"' \
  | sed 's/.*"v//; s/"$//'
