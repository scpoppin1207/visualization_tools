#!/usr/bin/env python
"""Launch the Vox Viewer desktop application."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

# These variables must be set before importing TraitsUI/Mayavi/Qt.
os.environ.setdefault("ETS_TOOLKIT", "qt")
os.environ.setdefault("QT_API", "pyqt5")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_installation() -> int:
    """Run a non-GUI dependency and sample-data check."""
    import open3d as o3d
    import vtk
    from PyQt5 import QtCore
    from mayavi import __version__ as mayavi_version

    from source.voxel_visualizer import VoxelVisualizer

    sample = APP_DIR / "examples" / "sample_voxels.ply"
    points, colors = VoxelVisualizer.load_point_cloud(sample)
    if points is None or colors is None:
        raise RuntimeError(f"Unable to read bundled sample: {sample}")

    print("Vox Viewer environment OK")
    print(f"  Qt: {QtCore.QT_VERSION_STR}")
    print(f"  VTK: {vtk.vtkVersion.GetVTKVersion()}")
    print(f"  Mayavi: {mayavi_version}")
    print(f"  Open3D: {o3d.__version__}")
    print(f"  Sample points: {len(points)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive voxel PLY viewer")
    parser.add_argument(
        "files",
        nargs="*",
        help="PLY files to open when the application starts",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check dependencies and bundled sample without opening the GUI",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        return check_installation()

    from vox_viewer.app import run

    return run([Path(path) for path in args.files])


if __name__ == "__main__":
    raise SystemExit(main())
