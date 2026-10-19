#!/bin/bash
# One-click launcher: activate the conda env and open the interactive Vox Viewer.
# Usage:
#   bash vox_viewer.sh                 # open empty viewer
#   bash vox_viewer.sh a.ply b.ply     # open PLY files on startup
#   bash vox_viewer.sh --check         # dependency check without GUI

set -euo pipefail

CALLER_DIR="$PWD"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── User configuration ──────────────────────────────────────────────────────
CONDA_ENV_VOX="mayavi_clean"
# ───────────────────────────────────────────────────────────────────────────

if ! command -v conda &>/dev/null; then
    echo "Error: conda not found in PATH"
    exit 1
fi
eval "$(conda shell.bash hook)"

if ! conda activate "$CONDA_ENV_VOX"; then
    echo "Error: failed to activate conda env: $CONDA_ENV_VOX"
    exit 1
fi

if [[ "$(uname)" == "Darwin" && -n "${CONDA_PREFIX:-}" ]]; then
    export DYLD_LIBRARY_PATH="$CONDA_PREFIX/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi

export ETS_TOOLKIT=qt
export QT_API=pyqt5

# Resolve relative PLY paths against the caller's cwd, not the repo root.
ARGS=()
for arg in "$@"; do
    if [[ "$arg" != -* && "$arg" != /* && -e "$CALLER_DIR/$arg" ]]; then
        ARGS+=("$CALLER_DIR/$arg")
    else
        ARGS+=("$arg")
    fi
done

echo "Launching Vox Viewer (env: $CONDA_ENV_VOX)"
exec python -m vox_viewer.main ${ARGS[@]+"${ARGS[@]}"}
