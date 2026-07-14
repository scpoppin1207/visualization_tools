import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from source.gaussian_visualizer import GaussianVisualizer


def main():
    parser = argparse.ArgumentParser(description="Gaussian Ellipsoids Visualization Tool")
    parser.add_argument("--ply_dir", type=str, required=True, help="PLY file directory")
    parser.add_argument("--ply_name", type=str, required=True, help="PLY file name (without extension)")
    parser.add_argument("--output_dir", type=str, default="./output", help="Output directory")
    parser.add_argument("--max_ellipsoids_3d", type=int, default=1000, help="Maximum ellipsoids for 3D view")
    parser.add_argument("--alpha_threshold", type=float, default=0.01, help="Opacity threshold")
    parser.add_argument("--resolution", type=int, default=12, help="Ellipsoid resolution")
    parser.add_argument("--figsize", type=int, nargs=2, default=[15, 15], help="Figure size")

    args = parser.parse_args()
    ply_file_path = os.path.join(args.ply_dir, f"{args.ply_name}.ply")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        visualizer = GaussianVisualizer(ply_file_path, color_norm_factor=1)
        visualizer.load_ply_data()
        output_3d = output_dir / f"{args.ply_name}_3d.png"
        visualizer.visualize_matplotlib_3d(
            max_ellipsoids=args.max_ellipsoids_3d,
            alpha_threshold=args.alpha_threshold,
            ellipsoid_resolution=args.resolution,
            use_wireframe=False,
            figsize=tuple(args.figsize),
            output_path=str(output_3d),
        )
        print(f"\nAll visualizations completed! Output files saved in: {output_dir}")
    except FileNotFoundError:
        print(f"File not found: {ply_file_path}")
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
