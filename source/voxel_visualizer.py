#!/usr/bin/env python
"""Voxel occupancy visualization using Open3D and Mayavi."""

import os
import sys

import numpy as np
import open3d as o3d
from pathlib import Path

from utils.camera import get_camera_params, load_camera_config
from utils.image import remove_white_background
from utils.paths import config_path

_mlab = None
_OFFSCREEN = False
_HEADLESS_PATCHED = False
_HEADLESS_WINDOW_SIZE = (1, 1)
_HEADLESS_WINDOW_POS = (0, 0)


def get_mlab():
    """Return the Mayavi mlab module (lazy import after env setup)."""
    global _mlab
    if _mlab is None:
        from mayavi import mlab

        _mlab = mlab
    return _mlab


def _shrink_qt_window(control):
    """Keep Mayavi/Qt windows invisible: prefer never showing, else use 1x1 off-screen."""
    if control is None:
        return

    try:
        from pyface.qt import QtCore

        control.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
        control.setWindowFlags(
            control.windowFlags()
            | QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
        )
    except Exception:
        QtCore = None

    width, height = _HEADLESS_WINDOW_SIZE
    x, y = _HEADLESS_WINDOW_POS
    control.setFixedSize(width, height)
    control.move(x, y)
    control.setVisible(False)
    control.hide()


def _install_headless_mayavi():
    """Patch Mayavi viewer creation so batch mode never opens full-size windows."""
    global _HEADLESS_PATCHED
    if _HEADLESS_PATCHED:
        return
    _HEADLESS_PATCHED = True

    import mayavi.core.ui.mayavi_scene as mayavi_scene

    def _silent_open(self):
        if self.control is None:
            self.create()
        _shrink_qt_window(self.control)
        return self.control is not None

    mayavi_scene.MayaviViewer.open = _silent_open

    def _headless_viewer_factory(size=(400, 350)):
        viewer = mayavi_scene.MayaviViewer()
        viewer.menu_bar_manager = None
        viewer.size = _HEADLESS_WINDOW_SIZE
        viewer.position = _HEADLESS_WINDOW_POS
        viewer.visible = False
        viewer.open()
        return viewer

    mayavi_scene.viewer_factory = _headless_viewer_factory

    try:
        import mayavi.core.engine as engine_mod

        engine_mod.viewer_factory = _headless_viewer_factory
    except ImportError:
        pass


def _suppress_mayavi_ui(fig):
    """Hide Mayavi/Qt windows for batch rendering without blocking the desktop."""
    scene = fig.scene
    scene.off_screen_rendering = True
    if scene._renwin is not None:
        scene._renwin.show_window = False

    control = getattr(scene, "control", None)
    _shrink_qt_window(control)

    try:
        from mayavi.core.registry import registry

        engine = registry.find_scene_engine(fig)
        for viewer in engine._viewer_ref.values():
            _shrink_qt_window(getattr(viewer, "control", None))
    except Exception:
        pass


def _create_figure(size, bgcolor=(1.0, 1.0, 1.0)):
    """Create a Mayavi figure, suppressing UI when batch offscreen mode is active."""
    mlab = get_mlab()
    fig = mlab.figure(size=tuple(size), bgcolor=bgcolor)
    if _OFFSCREEN:
        _suppress_mayavi_ui(fig)
    return fig


class VoxelVisualizer:
    """Voxel occupancy renderer and preprocessing utilities."""

    VIEW_LOCAL = "local"
    VIEW_GLOBAL = "global"

    def __init__(self, view_mode=VIEW_LOCAL, camera_config_path=None, voxel_size=0.08):
        self.view_mode = view_mode
        self.voxel_size = voxel_size
        self.camera_config_path = camera_config_path or self._default_camera_config_path()
        self.camera_config = None

    def _default_camera_config_path(self):
        filename = "global.json" if self.view_mode == self.VIEW_GLOBAL else "local.json"
        return config_path("camera", filename)

    @staticmethod
    def setup_mayavi_env(offscreen=False):
        """Configure Mayavi/Qt environment."""
        global _OFFSCREEN
        _OFFSCREEN = offscreen
        os.environ["QT_API"] = "pyqt5"
        if offscreen:
            _install_headless_mayavi()
            # macOS segfaults with mlab.options.offscreen; hide Qt windows instead.
            if sys.platform == "darwin":
                os.environ["ETS_TOOLKIT"] = "qt"
            else:
                os.environ["ETS_TOOLKIT"] = "qt4"
                get_mlab().options.offscreen = True
        else:
            os.environ["ETS_TOOLKIT"] = "qt"

    def load_camera_config(self, config_path=None):
        """Load camera configuration from JSON."""
        path = config_path or self.camera_config_path
        self.camera_config = load_camera_config(path)
        return self.camera_config

    def resolve_camera_params(self, scene_name, pcd_name=None, use_zoom=False):
        """Resolve camera parameters for the current view mode."""
        if self.camera_config is None:
            self.load_camera_config()
        return get_camera_params(
            self.camera_config,
            scene_name,
            pcd_name=pcd_name,
            use_zoom=use_zoom,
            view_mode=self.view_mode,
        )

    def setup_camera_view(self, voxel_centers, camera_params, azimuth=None):
        """Setup Mayavi camera view for static rendering."""
        mlab = get_mlab()
        min_bounds = np.min(voxel_centers, axis=0)
        max_bounds = np.max(voxel_centers, axis=0)
        center = (min_bounds + max_bounds) / 2
        scene_size = np.max(max_bounds - min_bounds)

        center_offset = camera_params.get("center_offset", [0.0, 0.0, 0.0])
        center = center + np.array(center_offset)

        print(f"[INFO] Scene center: [{center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f}]")
        print(f"[INFO] Scene size: {scene_size:.2f}")
        print(
            f"[INFO] Scene bounds: X=[{min_bounds[0]:.2f}, {max_bounds[0]:.2f}], "
            f"Y=[{min_bounds[1]:.2f}, {max_bounds[1]:.2f}], "
            f"Z=[{min_bounds[2]:.2f}, {max_bounds[2]:.2f}]"
        )

        mlab.gcf().scene.camera.parallel_projection = True
        view_label = "top-down view" if self.view_mode == self.VIEW_GLOBAL else "parallel"
        print(f"[INFO] Parallel projection enabled ({view_label})")

        if azimuth is None:
            azimuth = camera_params.get("azimuth", 0 if self.view_mode == self.VIEW_GLOBAL else 75)
        elevation = camera_params.get("elevation", 0 if self.view_mode == self.VIEW_GLOBAL else 50)
        parallel_scale_factor = camera_params.get(
            "parallel_scale_factor",
            0.6 if self.view_mode == self.VIEW_GLOBAL else 0.5,
        )

        mlab.view(azimuth=azimuth, elevation=elevation, focalpoint=center)
        parallel_scale = scene_size * parallel_scale_factor
        mlab.gcf().scene.camera.parallel_scale = parallel_scale

        print(
            f"[INFO] Camera view: azimuth={azimuth}, elevation={elevation}, "
            f"parallel_scale={parallel_scale:.2f}"
        )

    def _load_and_voxelize(self, pcd_path):
        """Load point cloud and build voxel color groups."""
        pcd = o3d.io.read_point_cloud(str(pcd_path))
        points = np.asarray(pcd.points)
        colors = np.asarray(pcd.colors)

        print(f"[INFO] Loaded {points.shape[0]} points from {pcd_path}")

        if points.size == 0:
            raise ValueError(f"Empty or unreadable point cloud: {pcd_path}")

        if colors.size == 0:
            colors = np.zeros((points.shape[0], 3), dtype=np.float64)
        elif colors.ndim == 1:
            colors = np.tile(colors.reshape(1, -1), (points.shape[0], 1))

        colors = (colors * 255).astype(np.uint8)
        voxel_coords = np.floor(points / self.voxel_size).astype(int)

        voxel_dict = {}
        for idx, voxel in enumerate(voxel_coords):
            key = tuple(voxel)
            if key not in voxel_dict:
                voxel_dict[key] = {"colors": [colors[idx]], "count": 1}
            else:
                voxel_dict[key]["colors"].append(colors[idx])
                voxel_dict[key]["count"] += 1

        color_groups = {}
        all_voxel_centers = []

        for voxel_idx, data in voxel_dict.items():
            avg_color = np.mean(data["colors"], axis=0).astype(int)
            color_key = tuple(avg_color)

            if color_key not in color_groups:
                color_groups[color_key] = []

            center = np.array(voxel_idx) * self.voxel_size + self.voxel_size / 2
            color_groups[color_key].append(center)
            all_voxel_centers.append(center)

        all_voxel_centers = np.array(all_voxel_centers)
        if all_voxel_centers.size == 0:
            raise ValueError(f"No voxels produced from point cloud: {pcd_path}")

        actual_center = np.mean(all_voxel_centers, axis=0)
        print(
            f"[INFO] Actual voxel center: "
            f"[{actual_center[0]:.2f}, {actual_center[1]:.2f}, {actual_center[2]:.2f}]"
        )

        return color_groups, all_voxel_centers

    def _render_voxel_groups(self, color_groups, all_voxel_centers):
        """Draw grouped voxels in the current Mayavi figure."""
        mlab = get_mlab()
        for color_rgb, centers in color_groups.items():
            centers = np.array(centers)
            color_normalized = np.array(color_rgb) / 255.0

            mlab.points3d(
                centers[:, 0],
                centers[:, 1],
                centers[:, 2],
                scale_factor=self.voxel_size * 1.0,
                mode="cube",
                color=tuple(color_normalized),
                opacity=1.0,
                resolution=8,
            )

        print(
            f"[INFO] Rendered {len(all_voxel_centers)} voxels "
            f"in {len(color_groups)} color groups"
        )

    def _default_image_size(self):
        return [1600, 1600] if self.view_mode == self.VIEW_GLOBAL else [1600, 1200]

    def _default_camera_params(self):
        if self.view_mode == self.VIEW_GLOBAL:
            return {
                "azimuth": 0,
                "elevation": 0,
                "parallel_scale_factor": 0.6,
                "center_offset": [0.0, 0.0, 0.0],
                "image_size": [1600, 1600],
            }
        return {
            "azimuth": 75,
            "elevation": 50,
            "parallel_scale_factor": 0.5,
            "center_offset": [0.0, 0.0, 0.0],
            "image_size": [1600, 1200],
        }

    def visualize(
        self,
        pcd_path,
        show_3d=True,
        save_image=False,
        output_path=None,
        camera_params=None,
        image_size=None,
        remove_background=True,
    ):
        """Visualize voxelized point cloud with original colors."""
        mlab = get_mlab()
        color_groups, all_voxel_centers = self._load_and_voxelize(pcd_path)

        if image_size is None:
            image_size = self._default_image_size()

        _create_figure(image_size, bgcolor=(1.0, 1.0, 1.0))
        print(f"[INFO] Figure size: {image_size[0]}x{image_size[1]}")

        self._render_voxel_groups(color_groups, all_voxel_centers)

        if camera_params is None:
            camera_params = self._default_camera_params()
        self.setup_camera_view(all_voxel_centers, camera_params)

        if save_image and output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mlab.savefig(str(output_path), size=tuple(image_size))
            if remove_background:
                remove_white_background(str(output_path))
            print(f"[INFO] Image saved to: {output_path}")

        if show_3d:
            print("[INFO] Showing 3D interactive interface...")
            mlab.show()
        else:
            print("[INFO] Skipping 3D interface, only saving image...")

    def visualize_rotation(
        self,
        pcd_path,
        output_dir,
        camera_params=None,
        image_size=None,
        num_frames=36,
        start_angle=0,
        end_angle=360,
    ):
        """Generate rotating visualization frames."""
        mlab = get_mlab()
        color_groups, all_voxel_centers = self._load_and_voxelize(pcd_path)

        if image_size is None:
            image_size = self._default_image_size()

        if camera_params is None:
            camera_params = self._default_camera_params()

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"[INFO] Total voxels: {len(all_voxel_centers)}, "
            f"Color groups: {len(color_groups)}"
        )
        print(f"[INFO] Generating {num_frames} rotation frames from {start_angle}° to {end_angle}°")

        angles = np.linspace(start_angle, end_angle, num_frames, endpoint=False)

        for frame_idx, azimuth in enumerate(angles):
            _create_figure(image_size, bgcolor=(1.0, 1.0, 1.0))
            self._render_voxel_groups(color_groups, all_voxel_centers)
            self.setup_camera_view(all_voxel_centers, camera_params, azimuth=azimuth)

            output_path = output_dir / f"frame_{frame_idx:04d}.png"
            mlab.savefig(str(output_path), size=tuple(image_size))
            remove_white_background(str(output_path))

            print(
                f"[INFO] Saved frame {frame_idx + 1}/{num_frames}: "
                f"{output_path.name} (azimuth={azimuth:.1f}°)"
            )
            mlab.close(all=True)

        print(f"[INFO] ✅ All {num_frames} frames saved to {output_dir}")

    @staticmethod
    def load_point_cloud(pcd_path):
        """Load point cloud and return points and colors."""
        try:
            pcd = o3d.io.read_point_cloud(str(pcd_path))
            points = np.asarray(pcd.points)
            colors = np.asarray(pcd.colors)

            if len(points) == 0:
                print(f"Warning: Empty point cloud: {pcd_path}")
                return None, None

            print(f"Loaded {len(points)} points from {Path(pcd_path).name}")
            return points, colors
        except Exception as e:
            print(f"Error loading {pcd_path}: {e}")
            return None, None

    @staticmethod
    def save_point_cloud(points, colors, output_path):
        """Save concatenated points and colors to a PLY file."""
        try:
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(points)
            pcd.colors = o3d.utility.Vector3dVector(colors)

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            o3d.io.write_point_cloud(str(output_path), pcd)
            print(f"Saved concatenated point cloud ({len(points)} points) to: {output_path}")
            return True
        except Exception as e:
            print(f"Error saving to {output_path}: {e}")
            return False

    @classmethod
    def concatenate_frames(cls, pcd_root, pcd_fold, pcd_scene, pcd_names, pcd_ext, output_folder):
        """Progressively concatenate point cloud frames."""
        print("=== Progressive Point Cloud Concatenation ===")
        print(f"Scene: {pcd_scene}")
        print(f"Input folder: {pcd_fold}")
        print(f"Output folder: {output_folder}")
        print(f"Frames to process: {pcd_names}")
        print("=" * 50)

        input_dir = Path(pcd_root) / pcd_fold / pcd_scene
        output_dir = Path(pcd_root) / output_folder / pcd_scene

        if not input_dir.exists():
            print(f"Error: Input directory does not exist: {input_dir}")
            return False

        accumulated_points = None
        accumulated_colors = None
        successful_frames = []

        for i, frame_name in enumerate(pcd_names):
            frame_path = input_dir / (frame_name + pcd_ext)
            print(f"\nProcessing frame {i + 1}/{len(pcd_names)}: {frame_name}")

            if not frame_path.exists():
                print(f"Warning: Frame file does not exist: {frame_path}")
                continue

            points, colors = cls.load_point_cloud(frame_path)
            if points is None or colors is None:
                print(f"Warning: Failed to load frame: {frame_name}")
                continue

            if accumulated_points is None:
                accumulated_points = points.copy()
                accumulated_colors = colors.copy()
            else:
                accumulated_points = np.concatenate([accumulated_points, points], axis=0)
                accumulated_colors = np.concatenate([accumulated_colors, colors], axis=0)

            successful_frames.append(frame_name)
            output_path = output_dir / (frame_name + pcd_ext)
            success = cls.save_point_cloud(accumulated_points, accumulated_colors, output_path)

            if success:
                print(f"✓ Accumulated {len(successful_frames)} frames -> {frame_name}{pcd_ext}")
                print(f"  Total points: {len(accumulated_points)}")
                print(f"  Frames included: {successful_frames}")
            else:
                print(f"✗ Failed to save accumulated result: {frame_name}{pcd_ext}")

        print("\n=== Concatenation Complete ===")
        print(f"Successfully processed: {len(successful_frames)}/{len(pcd_names)} frames")
        print(f"Output directory: {output_dir}")
        print(f"Generated files: {[frame + pcd_ext for frame in successful_frames]}")

        return len(successful_frames) > 0

    @staticmethod
    def build_output_path(pcd_root, output_folder, scene, pcd_name, view_mode="local", use_zoom=False):
        """Build output image path based on view mode."""
        output_dir = Path(pcd_root) / output_folder / scene
        if view_mode == VoxelVisualizer.VIEW_GLOBAL:
            if use_zoom:
                return output_dir / f"{pcd_name}_global_zoom.png"
            return output_dir / f"{pcd_name}_global.png"
        if use_zoom:
            return output_dir / f"{pcd_name}_zoom.png"
        return output_dir / f"{pcd_name}.png"
