#!/usr/bin/env python
"""CLI entry point for global (bird's eye) Gaussian rendering with Mitsuba."""

import argparse
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source.gaussian_visualizer import GaussianVisualizer


def main():
    parser = argparse.ArgumentParser(
        description="Render 3D Gaussians with Mitsuba v3 - Bird's Eye View"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ply_root", type=str, help="Root directory containing PLY files (batch mode)")
    group.add_argument("--input_file", type=str, help="Single PLY file to render")

    parser.add_argument("--ply_fold", type=str, help="Folder name containing Gaussian PLY files (batch mode)")
    parser.add_argument("--output_folder", type=str, help="Output folder for rendered images (batch mode)")
    parser.add_argument("--ply_ext", type=str, default=".ply", help="PLY file extension (batch mode)")
    parser.add_argument("--output_file", type=str, help="Output file path (single file mode)")

    parser.add_argument("--width", type=int, default=512, help="Render width")
    parser.add_argument("--height", type=int, default=512, help="Render height")
    parser.add_argument("--spp", type=int, default=128, help="Samples per pixel")
    parser.add_argument("--max_gaussians", type=int, default=5000, help="Maximum number of gaussians to render")
    parser.add_argument("--camera_distance", type=float, default=None, help="Camera distance from scene center")
    parser.add_argument(
        "--render_mode", type=str, default="enhanced",
        choices=["basic", "enhanced", "volume"],
        help="Rendering mode",
    )
    parser.add_argument("--n_theta", type=int, default=24, help="Longitude divisions for ellipsoid mesh")
    parser.add_argument("--n_phi", type=int, default=16, help="Latitude divisions for ellipsoid mesh")
    parser.add_argument("--ambient_light", type=float, default=0.4, help="Ambient lighting strength")
    parser.add_argument("--main_light", type=float, default=3.0, help="Main directional light strength")
    parser.add_argument("--fill_light", type=float, default=2.0, help="Fill light strength")
    parser.add_argument("--top_light", type=float, default=1.5, help="Top light strength")

    args = parser.parse_args()
    render_params = {"width": args.width, "height": args.height, "spp": args.spp}

    if args.input_file:
        if not args.output_file:
            parser.error("--output_file is required when using --input_file")
        if not os.path.exists(args.input_file):
            print(f"Error: Input file {args.input_file} does not exist!")
            return

        output_dir = os.path.dirname(args.output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        print(f"Rendering single file: {args.input_file}")
        try:
            GaussianVisualizer.render_file(
                args.input_file,
                args.output_file,
                render_params=render_params,
                max_gaussians=args.max_gaussians,
                render_mode=args.render_mode,
                camera_preset="global",
                n_theta=args.n_theta,
                n_phi=args.n_phi,
                ambient_light=args.ambient_light,
                main_light=args.main_light,
                fill_light=args.fill_light,
                top_light=args.top_light,
            )
            print(f"✅ Rendering complete: {args.output_file}")
        except Exception as e:
            print(f"❌ Error rendering {args.input_file}: {e}")
            traceback.print_exc()
    else:
        if not args.ply_fold or not args.output_folder:
            parser.error("--ply_fold and --output_folder are required for batch mode")
        GaussianVisualizer.batch_render(
            args, render_params, camera_preset="global", output_suffix="_mitsuba_glob"
        )


if __name__ == "__main__":
    main()
