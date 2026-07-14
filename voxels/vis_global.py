#!/usr/bin/env python
"""CLI entry point for progressive point cloud concatenation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source.voxel_visualizer import VoxelVisualizer


def main():
    if len(sys.argv) < 8:
        print(
            "Usage: python vis_global.py <pcd_root> <pcd_fold> <pcd_scene> "
            "<output_folder> <pcd_ext> <frame1> <frame2> [...]"
        )
        sys.exit(1)

    pcd_root = sys.argv[1]
    pcd_fold = sys.argv[2]
    pcd_scene = sys.argv[3]
    output_folder = sys.argv[4]
    pcd_ext = sys.argv[5]
    pcd_names = sys.argv[6:]

    if len(pcd_names) < 2:
        print("Error: At least 2 frames are required for concatenation")
        sys.exit(1)

    success = VoxelVisualizer.concatenate_frames(
        pcd_root=pcd_root,
        pcd_fold=pcd_fold,
        pcd_scene=pcd_scene,
        pcd_names=pcd_names,
        pcd_ext=pcd_ext,
        output_folder=output_folder,
    )

    if success:
        print("\n✓ Progressive concatenation completed successfully!")
        sys.exit(0)

    print("\n✗ Progressive concatenation failed!")
    sys.exit(1)


if __name__ == "__main__":
    main()
