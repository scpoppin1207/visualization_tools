import json
from pathlib import Path


def load_camera_config(config_path, verbose=True):
    """Load camera configuration from JSON file."""
    config_path = Path(config_path)
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        if verbose:
            print(f"[INFO] Loaded camera configuration from {config_path}")
        return config
    except FileNotFoundError:
        if verbose:
            print(f"[WARNING] Config file {config_path} not found, using default settings")
        return None
    except json.JSONDecodeError:
        if verbose:
            print(f"[ERROR] Invalid JSON in {config_path}, using default settings")
        return None


def _default_local_params():
    return {
        "azimuth": 75,
        "elevation": 50,
        "parallel_scale_factor": 0.5,
        "center_offset": [0.0, 0.0, 0.0],
        "image_size": [800, 600],
    }


def _default_global_params():
    return {
        "azimuth": 0,
        "elevation": 0,
        "parallel_scale_factor": 0.6,
        "center_offset": [0.0, 0.0, 0.0],
        "image_size": [800, 800],
    }


def get_camera_params(config, scene_name, pcd_name=None, use_zoom=False, view_mode="local", verbose=True):
    """Get camera parameters for local or global voxel views."""
    if view_mode == "global":
        return _get_global_camera_params(config, scene_name, use_zoom, verbose=verbose)
    return _get_local_camera_params(config, scene_name, pcd_name, use_zoom, verbose=verbose)


def _get_local_camera_params(config, scene_name, pcd_name, use_zoom, verbose=True):
    if config is None:
        return _default_local_params()

    if scene_name in config:
        scene_config = config[scene_name]
        if pcd_name in scene_config:
            base_params = scene_config[pcd_name].copy()

            if use_zoom and "zoom" in base_params:
                if verbose:
                    print(f"[INFO] Using ZOOM config for {scene_name}/{pcd_name}")
                zoom_config = base_params["zoom"]
                return {
                    "azimuth": base_params.get("azimuth", 75),
                    "elevation": base_params.get("elevation", 50),
                    "parallel_scale_factor": zoom_config.get("parallel_scale_factor", 0.25),
                    "center_offset": zoom_config.get("center_offset", [0.0, 0.0, 0.0]),
                    "image_size": zoom_config.get("image_size", [800, 600]),
                }

            if use_zoom:
                if verbose:
                    print(
                        f"[WARNING] Zoom requested but no zoom config found for "
                        f"{scene_name}/{pcd_name}, using normal view"
                    )
            elif verbose:
                print(f"[INFO] Using camera config for {scene_name}/{pcd_name}")

            if "image_size" not in base_params:
                base_params["image_size"] = [800, 600]
            return base_params

    if verbose:
        print(f"[INFO] No specific config for {scene_name}/{pcd_name}, using default")
    default_params = config.get("default", _default_local_params()).copy()
    if "image_size" not in default_params:
        default_params["image_size"] = [800, 600]
    return default_params


def _get_global_camera_params(config, scene_name, use_zoom, verbose=True):
    if config is None:
        return _default_global_params()

    if scene_name in config:
        base_params = config[scene_name].copy()

        if use_zoom and "zoom" in base_params:
            if verbose:
                print(f"[INFO] Using ZOOM config for {scene_name}")
            zoom_config = base_params["zoom"]
            return {
                "azimuth": zoom_config.get("azimuth", base_params.get("azimuth", 0)),
                "elevation": zoom_config.get("elevation", base_params.get("elevation", 0)),
                "parallel_scale_factor": zoom_config.get("parallel_scale_factor", 0.3),
                "center_offset": zoom_config.get("center_offset", [0.0, 0.0, 0.0]),
                "image_size": zoom_config.get("image_size", [1200, 1200]),
            }

        if use_zoom:
            if verbose:
                print(f"[WARNING] Zoom requested but no zoom config found for {scene_name}, using normal view")
        elif verbose:
            print(f"[INFO] Using camera config for {scene_name}")

        if "image_size" not in base_params:
            base_params["image_size"] = [800, 800]
        return base_params

    if verbose:
        print(f"[INFO] No specific config for {scene_name}, using default top-down view")
    default_params = config.get("default", _default_global_params()).copy()
    if "image_size" not in default_params:
        default_params["image_size"] = [800, 800]
    return default_params
