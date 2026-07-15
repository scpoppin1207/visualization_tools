#!/bin/bash
# Sync remote eval data to local ./eval (alternative to SFTP extension).
# Usage: bash sync_eval.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REMOTE="suchenpeng@sh.irmv.top"
PORT=6020
REMOTE_PATH="/nas0/codes/suchenpeng/Gaussian-Occ/eval/"
LOCAL_PATH="./eval/"

mkdir -p "$LOCAL_PATH"

echo "Syncing remote eval -> local eval"
echo "  Remote: ${REMOTE}:${REMOTE_PATH}"
echo "  Local:  ${LOCAL_PATH}"
echo ""

rsync -avz --progress \
    -e "ssh -p ${PORT}" \
    "${REMOTE}:${REMOTE_PATH}" \
    "${LOCAL_PATH}"

echo ""
echo "Done."
