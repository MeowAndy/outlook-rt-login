#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
HOST=${HOST:-0.0.0.0} PORT=${PORT:-8765} python -m outlook_rt_login.web
