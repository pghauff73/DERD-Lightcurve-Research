#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
export PYTHONPATH="$ROOT/src"
mkdir -p "$ROOT/artifacts/phase20"
python "$ROOT/experiments/run_phase20_shape_worker.py" \
  --root "$ROOT" --bootstrap-draws 64 \
  --output "$ROOT/artifacts/phase20/phase20_passband_shape_worker.json" &
SHAPE_PID=$!
python "$ROOT/experiments/run_phase20_tournament_worker.py" \
  --cases 30 \
  --output "$ROOT/artifacts/phase20/phase20_mechanism_tournament.json" &
TOURNAMENT_PID=$!
wait "$SHAPE_PID"
wait "$TOURNAMENT_PID"
python "$ROOT/experiments/run_phase20.py" \
  --root "$ROOT" --bootstrap-draws 64 --tournament-cases 30 \
  --invariant-draws 20000 --reuse-workers
