#!/bin/zsh
set -eu
cd "$(dirname "$0")/admissions_v2"
exec ./start_demo.command
