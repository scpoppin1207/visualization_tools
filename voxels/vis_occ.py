#!/usr/bin/env python
"""CLI entry point for local voxel occupancy visualization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source.voxel_visualizer import VoxelVisualizer
from utils.paths import parse_bool


def main():
    if len(sys.argv) != 9:
        print(
            "Usage: python vis_occ.py <pcd_root> <pcd_fold> <pcd_scene> <pcd_name> "
            "<pcd_ext> <output_folder> <show_3d> <use_zoom>"
        )
        sys.exit(1)

    pcd_root = Path(sys.argv[1])
    pcd_fold = sys.argv[2]
    pcd_scene = sys.argv[3]
    pcd_name = sys.argv[4]
    pcd_ext = sys.argv[5]
    output_folder = sys.argv[6]
    show_3d = parse_bool(sys.argv[7])
    use_zoom = parse_bool(sys.argv[8])

    pcd_file = pcd_root / pcd_fold / pcd_scene / (pcd_name + pcd_ext)

    visualizer = VoxelVisualizer(view_mode=VoxelVisualizer.VIEW_LOCAL)
    camera_params = visualizer.resolve_camera_params(pcd_scene, pcd_name, use_zoom)
    image_size = camera_params.get("image_size", [1600, 1200])
    output_path = VoxelVisualizer.build_output_path(
        pcd_root, output_folder, pcd_scene, pcd_name,
        view_mode=VoxelVisualizer.VIEW_LOCAL, use_zoom=use_zoom,
    )

    VoxelVisualizer.setup_mayavi_env(offscreen=False)
    visualizer.visualize(
        pcd_file,
        show_3d=show_3d,
        save_image=True,
        output_path=output_path,
        camera_params=camera_params,
        image_size=image_size,
    )


if __name__ == "__main__":
    main()
