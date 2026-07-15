#!/bin/bash
# Batch visualization for a single experiment epoch directory (vox + gs → PNG).
# Edit the configuration variables below, then run: bash vis_exp.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── User configuration ──────────────────────────────────────────────────────
EXP_DIR="./eval/embodied/base/train_embodied_base/epoch_10/vis/epoch_10"        # Single epoch root (contains vox/, gs/)
OUTPUT_DIR="./eval_png/embodied/base/train_embodied_base/epoch_10/"
MODE="embodied"                                  # embodied | mono
VIS_DUAL=false                                   # true if experiment used vis_dual
SCENES=()                                        # Empty = all scenes; e.g. SCENES=("scene0000_00")
SKIP_EXISTING=true

CONDA_ENV_VOX="mayavi_clean"
CONDA_ENV_GS="renderpy"
# ───────────────────────────────────────────────────────────────────────────

echo "Experiment Visualization (vis_exp)"
echo "=================================="
echo "  EXP_DIR:      $EXP_DIR"
echo "  OUTPUT_DIR:   $OUTPUT_DIR"
echo "  MODE:         $MODE"
echo "  VIS_DUAL:     $VIS_DUAL"
echo "  SKIP_EXISTING: $SKIP_EXISTING"
if [ ${#SCENES[@]} -gt 0 ]; then
    echo "  SCENES:       ${SCENES[*]}"
else
    echo "  SCENES:       (all)"
fi
echo ""

if [ ! -d "$EXP_DIR" ]; then
    echo "Error: EXP_DIR does not exist: $EXP_DIR"
    exit 1
fi

if [ ! -d "$EXP_DIR/vox" ] && [ ! -d "$EXP_DIR/gs" ]; then
    echo "Error: EXP_DIR must contain vox/ or gs/: $EXP_DIR"
    exit 1
fi

if [ "$MODE" != "embodied" ] && [ "$MODE" != "mono" ]; then
    echo "Error: MODE must be 'embodied' or 'mono', got: $MODE"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Build optional CLI arguments
PY_ARGS=(--exp-dir "$EXP_DIR" --output-dir "$OUTPUT_DIR" --mode "$MODE")
if [ "$VIS_DUAL" = true ]; then
    PY_ARGS+=(--vis-dual)
fi
if [ "$SKIP_EXISTING" = true ]; then
    PY_ARGS+=(--skip-existing)
fi
if [ ${#SCENES[@]} -gt 0 ]; then
    PY_ARGS+=(--scenes "${SCENES[@]}")
fi

# Initialize conda
if ! command -v conda &>/dev/null; then
    echo "Error: conda not found in PATH"
    exit 1
fi
eval "$(conda shell.bash hook)"

run_vox() {
    echo ""
    echo "=== Phase 1: Voxel visualization ($CONDA_ENV_VOX) ==="
    conda activate "$CONDA_ENV_VOX"

    if [[ "$(uname)" == "Darwin" && -n "${CONDA_PREFIX:-}" ]]; then
        export DYLD_LIBRARY_PATH="$CONDA_PREFIX/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
    fi

    # Offscreen Mayavi: set env before Python starts so Qt never opens interactive windows.
    if [[ "$(uname)" == "Darwin" ]]; then
        export ETS_TOOLKIT=qt
    else
        export ETS_TOOLKIT=qt4
    fi
    export QT_API=pyqt5

    local vox_args=("${PY_ARGS[@]}" --tasks vox)
    if [[ "$(uname)" == "Linux" ]] && command -v xvfb-run &>/dev/null; then
        xvfb-run -a -s "-screen 0 1920x1200x24" python vis_exp.py "${vox_args[@]}"
    else
        python vis_exp.py "${vox_args[@]}"
    fi

    conda deactivate
}

run_gs() {
    echo ""
    echo "=== Phase 2: Gaussian visualization ($CONDA_ENV_GS) ==="
    conda activate "$CONDA_ENV_GS"

    local gs_args=("${PY_ARGS[@]}" --tasks gs)
    python vis_exp.py "${gs_args[@]}"

    conda deactivate
}

if [ -d "$EXP_DIR/vox" ]; then
    run_vox
fi

if [ -d "$EXP_DIR/gs" ]; then
    run_gs
fi

echo ""
echo "Done! PNG outputs saved to: $OUTPUT_DIR"
