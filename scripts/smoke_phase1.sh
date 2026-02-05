#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=. python scripts/seed_demo_data.py
PYTHONPATH=. pytest -m phase1_ready -q
