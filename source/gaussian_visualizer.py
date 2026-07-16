#!/usr/bin/env python
"""3D Gaussian Splatting visualization using Mitsuba v3 and Matplotlib."""

import os
import tempfile

import numpy as np

from utils.colors import enhance_colors_hsv
from utils.geometry import create_ellipsoid_mesh, create_ply_string, quaternion_to_matrix
from utils.image import center_crop_by_ratio


def _progress(iterable, desc="", disable=False):
    if disable:
        return iterable
    try:
        from tqdm import tqdm

        return tqdm(iterable, desc=desc)
    except ImportError:
        return iterable


class GaussianVisualizer:
    """Gaussian splatting renderer and visualizer."""

    def __init__(self, ply_file_path=None, color_norm_factor=4, verbose=True):
        self.ply_file_path = ply_file_path
        self.color_norm_factor = color_norm_factor
        self.verbose = verbose
        self.xyz = None
        self.colors = None
        self.scales = None
        self.rotations = None
        self.opacity = None
        self._mitsuba_initialized = False

    def _log(self, message):
        if self.verbose:
            print(message)

    def _ensure_mitsuba(self):
        if not self._mitsuba_initialized:
            from utils.mitsuba_init import init_mitsuba

            init_mitsuba()
            self._mitsuba_initialized = True

    @staticmethod
    def _read_gaussian_arrays(ply_file_path):
        """Read raw Gaussian attributes from a 3DGS-style PLY file."""
        try:
            from plyfile import PlyData

            plydata = PlyData.read(str(ply_file_path))
            vertex = plydata["vertex"]
            xyz = np.column_stack([vertex["x"], vertex["y"], vertex["z"]]).astype(np.float64)
            opacity = np.asarray(vertex["opacity"], dtype=np.float64)
            colors = np.column_stack(
                [vertex["f_dc_0"], vertex["f_dc_1"], vertex["f_dc_2"]]
            ).astype(np.float64)
            scales = np.column_stack(
                [vertex["scale_0"], vertex["scale_1"], vertex["scale_2"]]
            ).astype(np.float64)
            rotations = np.column_stack(
                [vertex["rot_0"], vertex["rot_1"], vertex["rot_2"], vertex["rot_3"]]
            ).astype(np.float64)
            return xyz, opacity, colors, scales, rotations
        except ImportError:
            import open3d as o3d

            cloud = o3d.t.io.read_point_cloud(str(ply_file_path))
            required = (
                "positions",
                "opacity",
                "f_dc_0",
                "f_dc_1",
                "f_dc_2",
                "scale_0",
                "scale_1",
                "scale_2",
                "rot_0",
                "rot_1",
                "rot_2",
                "rot_3",
            )
            missing = [name for name in required if name not in cloud.point]
            if missing:
                raise ValueError(
                    f"PLY is missing Gaussian attributes: {', '.join(missing)}"
                ) from None

            xyz = cloud.point["positions"].numpy().astype(np.float64)
            opacity = cloud.point["opacity"].numpy().reshape(-1).astype(np.float64)
            colors = np.column_stack(
                [
                    cloud.point["f_dc_0"].numpy().reshape(-1),
                    cloud.point["f_dc_1"].numpy().reshape(-1),
                    cloud.point["f_dc_2"].numpy().reshape(-1),
                ]
            ).astype(np.float64)
            scales = np.column_stack(
                [
                    cloud.point["scale_0"].numpy().reshape(-1),
                    cloud.point["scale_1"].numpy().reshape(-1),
                    cloud.point["scale_2"].numpy().reshape(-1),
                ]
            ).astype(np.float64)
            rotations = np.column_stack(
                [
                    cloud.point["rot_0"].numpy().reshape(-1),
                    cloud.point["rot_1"].numpy().reshape(-1),
                    cloud.point["rot_2"].numpy().reshape(-1),
                    cloud.point["rot_3"].numpy().reshape(-1),
                ]
            ).astype(np.float64)
            return xyz, opacity, colors, scales, rotations

    def load_ply_data(self, ply_file_path=None):
        """Load Gaussian ellipsoid data from a PLY file."""
        if ply_file_path is not None:
            self.ply_file_path = ply_file_path

        self._log(f"Loading PLY file: {self.ply_file_path}")
        xyz, opacity, colors, scales, rotations = self._read_gaussian_arrays(self.ply_file_path)

        self.xyz = xyz[:, [0, 2, 1]] * -1
        self.opacity = 1 / (1 + np.exp(-opacity))
        self.scales = np.exp(scales)
        self.rotations = rotations

        norm = np.sqrt(self.color_norm_factor * np.pi)
        self.colors = np.abs(colors) / norm
        self.colors = np.clip(self.colors, 0, 1)
        self.colors = enhance_colors_hsv(self.colors, brightness_factor=1.5, saturation_factor=1.5)
        self.colors = np.clip(self.colors, 0.0, 1.0)

        self._log(f"Successfully loaded {len(self.xyz)} Gaussian ellipsoids")
        self._log(
            f"Position range: X[{self.xyz[:, 0].min():.2f}, {self.xyz[:, 0].max():.2f}], "
            f"Y[{self.xyz[:, 1].min():.2f}, {self.xyz[:, 1].max():.2f}], "
            f"Z[{self.xyz[:, 2].min():.2f}, {self.xyz[:, 2].max():.2f}]"
        )

    def select_for_display(
        self,
        max_gaussians=2000,
        opacity_threshold=0.05,
        min_scale=0.005,
    ):
        """Pick the most opaque Gaussians for interactive display."""
        if self.xyz is None:
            raise RuntimeError("Call load_ply_data() before select_for_display()")

        opacity = np.asarray(self.opacity).reshape(-1)
        scales = np.asarray(self.scales)
        valid = (opacity >= opacity_threshold) & (np.max(scales, axis=1) >= min_scale)
        indices = np.flatnonzero(valid)
        if len(indices) == 0:
            return (
                np.empty((0, 3)),
                np.empty((0, 3)),
                np.empty((0, 3)),
                np.empty((0, 4)),
                np.empty((0,)),
            )

        order = indices[np.argsort(-opacity[indices])]
        selected = order[: min(max_gaussians, len(order))]
        return (
            self.xyz[selected],
            self.colors[selected],
            self.scales[selected],
            self.rotations[selected],
            opacity[selected],
        )

    @staticmethod
    def build_combined_ellipsoid_mesh(
        xyz,
        colors,
        scales,
        rotations,
        opacity,
        scale_multiplier=1.0,
        n_theta=8,
        n_phi=4,
    ):
        """Build one triangle mesh for Mayavi from selected ellipsoids."""
        unit_vertices, _, faces = create_ellipsoid_mesh(n_theta=n_theta, n_phi=n_phi)
        unit_vertices = np.asarray(unit_vertices, dtype=np.float64)
        faces = np.asarray(faces, dtype=np.int64)
        verts_per = len(unit_vertices)
        faces_per = len(faces)
        count = len(xyz)
        if count == 0:
            return (
                np.empty((0, 3)),
                np.empty((0, 3), dtype=np.int64),
                np.empty((0, 3)),
                np.empty((0,)),
            )

        all_vertices = np.empty((count * verts_per, 3), dtype=np.float64)
        all_faces = np.empty((count * faces_per, 3), dtype=np.int64)
        all_colors = np.empty((count * verts_per, 3), dtype=np.float64)
        all_opacity = np.empty(count * verts_per, dtype=np.float64)

        for i in range(count):
            scale = np.asarray(scales[i], dtype=np.float64) * float(scale_multiplier)
            rot = quaternion_to_matrix(rotations[i])[:3, :3]
            scaled = unit_vertices * scale[np.newaxis, :]
            world = (rot @ scaled.T).T + xyz[i]
            start = i * verts_per
            stop = start + verts_per
            all_vertices[start:stop] = world
            all_faces[i * faces_per : (i + 1) * faces_per] = faces + start
            all_colors[start:stop] = colors[i]
            all_opacity[start:stop] = opacity[i]

        return all_vertices, all_faces, all_colors, all_opacity

    def _default_camera_params(self, camera_preset="local"):
        bbox_min = self.xyz.min(axis=0)
        bbox_max = self.xyz.max(axis=0)
        bbox_center = (bbox_min + bbox_max) / 2
        bbox_size = np.linalg.norm(bbox_max - bbox_min)

        if camera_preset == "global":
            self._log("[INFO] Bird's Eye View Camera:")
            camera_params = {
                "origin": bbox_center + np.array([0, -bbox_size * 1.5, 0]),
                "target": bbox_center,
                "up": [0.0, 0.0, -1.0],
                "fov": 45.0,
            }
        else:
            camera_params = {
                "origin": bbox_center + np.array([0, bbox_size * 2, bbox_size * 0.6]) * 0.50,
                "target": bbox_center,
                "up": [0.0, 0.0, 1.0],
                "fov": 45.0,
            }

        self._log(f"  Origin: {camera_params['origin']}")
        self._log(f"  Target: {camera_params['target']}")
        return camera_params

    def create_mitsuba_scene(
        self,
        max_gaussians=5000,
        camera_params=None,
        render_params=None,
        render_mode="enhanced",
        camera_preset="local",
        n_theta=24,
        n_phi=16,
        ambient_light=0.4,
        main_light=3.0,
        fill_light=2.0,
        top_light=1.5,
    ):
        """Create a Mitsuba scene with Gaussian ellipsoids."""
        self._ensure_mitsuba()
        import mitsuba as mi

        if camera_params is None:
            camera_params = self._default_camera_params(camera_preset)

        if render_params is None:
            render_params = {"width": 512, "height": 512, "spp": 128}

        scene_dict = {
            "type": "scene",
            "integrator": {"type": "path", "max_depth": 8, "hide_emitters": True},
            "sensor": {
                "type": "perspective",
                "fov": camera_params["fov"],
                "to_world": mi.ScalarTransform4f().look_at(
                    origin=camera_params["origin"],
                    target=camera_params["target"],
                    up=camera_params["up"],
                ),
                "film": {
                    "type": "hdrfilm",
                    "width": render_params["width"],
                    "height": render_params["height"],
                    "pixel_format": "rgba",
                    "component_format": "float32",
                },
                "sampler": {"type": "independent", "sample_count": render_params["spp"]},
            },
        }

        scene_dict["env"] = {
            "type": "constant",
            "radiance": {"type": "rgb", "value": [ambient_light] * 3},
        }
        scene_dict["light1"] = {
            "type": "directional",
            "direction": [1, 1, -1],
            "irradiance": {"type": "rgb", "value": [main_light] * 3},
        }
        scene_dict["light2"] = {
            "type": "directional",
            "direction": [-1, -1, -1],
            "irradiance": {"type": "rgb", "value": [fill_light] * 3},
        }
        scene_dict["light3"] = {
            "type": "directional",
            "direction": [0, 0, -1],
            "irradiance": {"type": "rgb", "value": [top_light] * 3},
        }

        opacity_indices = np.argsort(-self.opacity)
        num_gaussians = min(max_gaussians, len(self.xyz))
        selected_indices = opacity_indices[:num_gaussians]

        self._log(f"Rendering {num_gaussians} gaussians (sorted by opacity)")

        for i, idx in enumerate(
            _progress(selected_indices, desc="Creating ellipsoids", disable=not self.verbose)
        ):
            pos = self.xyz[idx]
            scale = self.scales[idx]
            rot = self.rotations[idx]
            opacity = self.opacity[idx]
            color = np.clip(self.colors[idx], 0.0, 1.0)

            if opacity < 0.05 or np.max(scale) < 0.005:
                continue

            base_color = [float(np.clip(c, 0.0, 1.0)) for c in color]
            if opacity < 0.95:
                material = {
                    "type": "mask",
                    "opacity": {"type": "rgb", "value": [float(opacity)] * 3},
                    "bsdf": {
                        "type": "diffuse",
                        "reflectance": {"type": "rgb", "value": base_color},
                    },
                }
            else:
                material = {
                    "type": "diffuse",
                    "reflectance": {"type": "rgb", "value": base_color},
                }

            vertices, normals, faces = create_ellipsoid_mesh(n_theta=n_theta, n_phi=n_phi)
            scaled_vertices = vertices * scale[np.newaxis, :]

            scale_matrix = np.diag(1.0 / scale)
            transformed_normals = (scale_matrix @ normals.T).T
            norm_lengths = np.linalg.norm(transformed_normals, axis=1, keepdims=True)
            transformed_normals = transformed_normals / (norm_lengths + 1e-8)

            rot_matrix_4x4 = quaternion_to_matrix(rot)
            rot_matrix_3x3 = rot_matrix_4x4[:3, :3]

            rotated_vertices = (rot_matrix_3x3 @ scaled_vertices.T).T
            rotated_normals = (rot_matrix_3x3 @ transformed_normals.T).T
            final_vertices = rotated_vertices + pos[np.newaxis, :]

            temp_ply_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ply", delete=False)
            ply_content = create_ply_string(final_vertices, rotated_normals, faces)
            temp_ply_file.write(ply_content)
            temp_ply_file.flush()
            temp_ply_file.close()

            scene_dict[f"gaussian_{i}"] = {
                "type": "ply",
                "filename": temp_ply_file.name,
                "bsdf": material,
            }

        return mi.load_dict(scene_dict)

    def render_mitsuba(
        self,
        output_path,
        render_params=None,
        camera_params=None,
        max_gaussians=5000,
        render_mode="enhanced",
        camera_preset="local",
        n_theta=24,
        n_phi=16,
        ambient_light=0.4,
        main_light=3.0,
        fill_light=2.0,
        top_light=1.5,
    ):
        """Render the loaded Gaussian data to an EXR file."""
        self._ensure_mitsuba()

        if render_params is None:
            render_params = {"width": 512, "height": 512, "spp": 128}

        preset_label = "Bird's Eye View" if camera_preset == "global" else "Local"
        self._log(f"Creating Mitsuba scene ({preset_label})...")
        scene = self.create_mitsuba_scene(
            max_gaussians=max_gaussians,
            camera_params=camera_params,
            render_params=render_params,
            render_mode=render_mode,
            camera_preset=camera_preset,
            n_theta=n_theta,
            n_phi=n_phi,
            ambient_light=ambient_light,
            main_light=main_light,
            fill_light=fill_light,
            top_light=top_light,
        )

        import mitsuba as mi

        self._log("Rendering...")
        image = mi.render(scene, spp=render_params["spp"])
        mi.util.write_bitmap(output_path, image)
        self._log(f"Saved EXR: {output_path}")

    @classmethod
    def render_file(
        cls,
        ply_path,
        output_path,
        render_params=None,
        camera_params=None,
        max_gaussians=5000,
        render_mode="enhanced",
        camera_preset="local",
        n_theta=24,
        n_phi=16,
        ambient_light=0.4,
        main_light=3.0,
        fill_light=2.0,
        top_light=1.5,
        verbose=True,
    ):
        """Load a PLY file and render it with Mitsuba."""
        if verbose:
            print(f"Processing: {os.path.basename(ply_path)}")
        visualizer = cls(ply_path, verbose=verbose)
        visualizer.load_ply_data()
        visualizer.render_mitsuba(
            output_path,
            render_params=render_params,
            camera_params=camera_params,
            max_gaussians=max_gaussians,
            render_mode=render_mode,
            camera_preset=camera_preset,
            n_theta=n_theta,
            n_phi=n_phi,
            ambient_light=ambient_light,
            main_light=main_light,
            fill_light=fill_light,
            top_light=top_light,
        )

    @classmethod
    def batch_render(cls, args, render_params, camera_preset="local", output_suffix="_mitsuba"):
        """Process multiple PLY files in batch mode."""
        input_folder = os.path.join(args.ply_root, args.ply_fold)
        output_folder = os.path.join(args.ply_root, args.output_folder)
        os.makedirs(output_folder, exist_ok=True)

        if not os.path.exists(input_folder):
            print(f"Error: Input folder {input_folder} does not exist!")
            return

        ply_files = sorted(f for f in os.listdir(input_folder) if f.endswith(args.ply_ext))
        if not ply_files:
            print(f"No PLY files found in {input_folder}")
            return

        print(f"Found {len(ply_files)} PLY files in {input_folder}")

        for ply_file in ply_files:
            ply_path = os.path.join(input_folder, ply_file)
            base_name = os.path.splitext(ply_file)[0]
            output_path = os.path.join(output_folder, f"{base_name}{output_suffix}.exr")

            if os.path.exists(output_path):
                print(f"Skipping {ply_file} (output already exists)")
                continue

            try:
                cls.render_file(
                    ply_path,
                    output_path,
                    render_params=render_params,
                    max_gaussians=args.max_gaussians,
                    render_mode=args.render_mode,
                    camera_preset=camera_preset,
                    n_theta=args.n_theta,
                    n_phi=args.n_phi,
                    ambient_light=args.ambient_light,
                    main_light=args.main_light,
                    fill_light=args.fill_light,
                    top_light=args.top_light,
                )
            except Exception as e:
                print(f"Error processing {ply_file}: {e}")
                import traceback
                traceback.print_exc()

        print(f"\nBatch rendering complete! Images saved to: {output_folder}")

    def filter_and_sample(self, max_points, alpha_threshold=0.01):
        """Filter and sample data for Matplotlib visualization."""
        valid_mask = self.opacity.flatten() > alpha_threshold

        xyz_filtered = self.xyz[valid_mask]
        colors_filtered = self.colors[valid_mask]
        scales_filtered = self.scales[valid_mask]
        rotations_filtered = self.rotations[valid_mask]
        opacity_filtered = self.opacity[valid_mask]

        print(
            f"After filtering: {len(xyz_filtered)} ellipsoids remaining "
            f"(opacity threshold: {alpha_threshold})"
        )

        if len(xyz_filtered) > max_points:
            indices = np.random.choice(len(xyz_filtered), max_points, replace=False)
            xyz_filtered = xyz_filtered[indices]
            colors_filtered = colors_filtered[indices]
            scales_filtered = scales_filtered[indices]
            rotations_filtered = rotations_filtered[indices]
            opacity_filtered = opacity_filtered[indices]
            print(f"Randomly sampled to {max_points} ellipsoids")

        return xyz_filtered, colors_filtered, scales_filtered, rotations_filtered, opacity_filtered

    def create_ellipsoid_surface(self, center, scale, rotation, resolution=12):
        """Create ellipsoid surface points for Matplotlib."""
        from scipy.spatial.transform import Rotation as SciPyRotation

        u = np.linspace(0, 2 * np.pi, resolution)
        v = np.linspace(0, np.pi, resolution)
        x_sphere = np.outer(np.cos(u), np.sin(v))
        y_sphere = np.outer(np.sin(u), np.sin(v))
        z_sphere = np.outer(np.ones(np.size(u)), np.cos(v))

        x_ellipsoid = x_sphere * scale[0]
        y_ellipsoid = y_sphere * scale[1]
        z_ellipsoid = z_sphere * scale[2]

        rot_matrix = SciPyRotation.from_quat(rotation).as_matrix()
        points = np.stack([
            x_ellipsoid.flatten(),
            y_ellipsoid.flatten(),
            z_ellipsoid.flatten(),
        ], axis=0)
        rotated_points = rot_matrix @ points

        x_final = rotated_points[0].reshape(x_ellipsoid.shape) + center[0]
        y_final = rotated_points[1].reshape(y_ellipsoid.shape) + center[1]
        z_final = rotated_points[2].reshape(z_ellipsoid.shape) + center[2]

        return x_final, y_final, z_final

    def visualize_matplotlib_3d(
        self,
        max_ellipsoids=1000,
        alpha_threshold=0.01,
        use_wireframe=False,
        ellipsoid_resolution=12,
        figsize=(15, 15),
        output_path=None,
        crop_ratio=0.7,
    ):
        """Render 3D ellipsoid visualization with Matplotlib."""
        import matplotlib.pyplot as plt
        from matplotlib.colors import LightSource

        print("Starting 3D ellipsoid visualization...")

        xyz, colors, scales, rotations, opacity = self.filter_and_sample(
            max_ellipsoids, alpha_threshold
        )

        fig = plt.figure(figsize=figsize, dpi=300)
        ax = fig.add_subplot(111, projection="3d")
        light_source = LightSource(azdeg=315, altdeg=45)

        print(f"Rendering {len(xyz)} ellipsoids...")
        for i in range(len(xyz)):
            if i % 100 == 0:
                print(f"Progress: {i}/{len(xyz)}")

            center = xyz[i]
            scale = scales[i]
            rotation = rotations[i]
            alpha_val = np.clip(opacity[i], alpha_threshold * 1, 1)
            color = colors[i]

            x_ellipsoid, y_ellipsoid, z_ellipsoid = self.create_ellipsoid_surface(
                center, scale, rotation, ellipsoid_resolution
            )

            if use_wireframe:
                ax.plot_wireframe(
                    x_ellipsoid, y_ellipsoid, z_ellipsoid,
                    alpha=alpha_val, color=color, linewidth=0.5,
                )

            ax.plot_surface(
                x_ellipsoid, y_ellipsoid, z_ellipsoid,
                color=color, alpha=alpha_val,
                shade=True, antialiased=True, lightsource=light_source,
                rcount=ellipsoid_resolution, ccount=ellipsoid_resolution,
            )

        margin_factor = 0.05
        for axis_idx, setter in enumerate([ax.set_xlim, ax.set_ylim, ax.set_zlim]):
            data_min = xyz[:, axis_idx].min()
            data_max = xyz[:, axis_idx].max()
            data_range = data_max - data_min
            setter(
                data_min - data_range * margin_factor,
                data_max + data_range * margin_factor,
            )

        origin = np.array([2.8, 3.0, 3.5])
        target = np.array([1.2, -1.0, 1.8])
        camera_vec = origin - target
        azimuth_deg = np.rad2deg(np.arctan2(camera_vec[1], camera_vec[0]))
        dist_xy = np.sqrt(camera_vec[0] ** 2 + camera_vec[1] ** 2)
        elevation_deg = np.rad2deg(np.arctan2(camera_vec[2], dist_xy))
        ax.view_init(elev=elevation_deg, azim=azimuth_deg)

        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_zlabel("")
        ax.axis("off")
        ax.grid(False)

        for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
            pane.fill = True
            pane.set_alpha(0.0)

        fig.tight_layout(pad=0)

        if output_path:
            print(f"Saving 3D visualization to: {output_path}")
            plt.savefig(
                output_path, dpi=300, pad_inches=0,
                facecolor="none", edgecolor="none",
                format="png", pil_kwargs={"optimize": True},
                transparent=True,
            )
            center_crop_by_ratio(output_path, ratio=crop_ratio)
        else:
            plt.show()

        plt.close()
        print("3D visualization completed")
