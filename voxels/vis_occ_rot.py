#!/usr/bin/env python
"""CLI entry point for rotating voxel visualization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source.voxel_visualizer import VoxelVisualizer
from utils.paths import parse_bool


def main():
    if len(sys.argv) != 12:
        print(
            "Usage: python vis_occ_rot.py <pcd_root> <pcd_fold> <pcd_scene> <pcd_name> "
            "<pcd_ext> <output_folder> <num_frames> <start_angle> <end_angle> "
            "<image_size_width> <offscreen>"
        )
        sys.exit(1)

    pcd_root = Path(sys.argv[1])
    pcd_fold = sys.argv[2]
    pcd_scene = sys.argv[3]
    pcd_name = sys.argv[4]
    pcd_ext = sys.argv[5]
    output_folder = sys.argv[6]
    num_frames = int(sys.argv[7])
    start_angle = float(sys.argv[8])
    end_angle = float(sys.argv[9])
    image_width = int(sys.argv[10])
    offscreen = parse_bool(sys.argv[11])

    image_height = int(image_width * 3 / 4)
    image_size = [image_width, image_height]
    pcd_file = pcd_root / pcd_fold / pcd_scene / (pcd_name + pcd_ext)

    VoxelVisualizer.setup_mayavi_env(offscreen=offscreen)
    visualizer = VoxelVisualizer(view_mode=VoxelVisualizer.VIEW_LOCAL)
    camera_params = visualizer.resolve_camera_params(pcd_scene, pcd_name)
    camera_params["image_size"] = image_size

    output_dir = pcd_root / output_folder / pcd_scene / (pcd_name + "_rotation")
    visualizer.visualize_rotation(
        pcd_file,
        output_dir=output_dir,
        camera_params=camera_params,
        image_size=image_size,
        num_frames=num_frames,
        start_angle=start_angle,
        end_angle=end_angle,
    )


if __name__ == "__main__":
    main()
