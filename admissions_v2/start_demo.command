#!/bin/zsh
set -eu
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "First install the local dependencies described in docs/LOCAL_DEMO.md."
  read -r "?Press Enter to close."
  exit 1
fi
.venv/bin/python -m scripts.local_demo
