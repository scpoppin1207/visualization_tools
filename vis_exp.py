#!/usr/bin/env python
"""Batch visualization for a single experiment epoch directory (vox + gs)."""

import argparse
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        desc = kwargs.get("desc", "")
        unit = kwargs.get("unit", "item")
        total = len(iterable) if hasattr(iterable, "__len__") else None
        for i, item in enumerate(iterable, 1):
            label = f"{desc} " if desc else ""
            count = f"{i}/{total}" if total else str(i)
            print(f"\r{label}{count} {unit}", end="", flush=True)
            yield item
        print()

from utils.paths import ensure_repo_on_path

ensure_repo_on_path()

VOX_GLOBAL_NAMES = ("pred", "gt")
VOX_LOCAL_NAMES = ("pred", "gt")
VOX_DUAL_EXTRA = ("pred_before_dual",)
GS_NAMES = ("gs_pred", "gs_pca", "gs_conf")
GS_DUAL_STAGES = ("before_dual", "after_dual")
GS_DUAL_STREAMS = ("hist_gs", "cur_gs")
MODES = ("embodied", "mono")
RESERVED_SUBDIRS = frozenset({"global", "local"})

BRIGHT_LIGHT = {
    "ambient_light": 0.6,
    "main_light": 4.0,
    "fill_light": 3.0,
    "top_light": 2.0,
}

GS_RENDER_PARAMS = {"width": 1024, "height": 1024, "spp": 128}


@dataclass
class RenderTask:
    ply_path: Path
    output_path: Path
    task_type: str  # "vox" or "gs"
    view_mode: str  # "global" or "local"
    scene: str
    frame: Optional[str] = None


def ply_to_png_path(ply_path: Path, exp_dir: Path, out_dir: Path) -> Path:
    rel = ply_path.relative_to(exp_dir)
    return out_dir / rel.with_suffix(".png")


def _scene_allowed(scene: str, scenes: Optional[Set[str]]) -> bool:
    return scenes is None or scene in scenes


def _is_nonempty_ply(ply_path: Path) -> bool:
    try:
        return ply_path.is_file() and ply_path.stat().st_size > 0
    except OSError:
        return False


def _add_task(
    tasks: List[RenderTask],
    ply_path: Path,
    exp_dir: Path,
    out_dir: Path,
    skipped_empty: List[str],
    **meta,
) -> None:
    if not ply_path.is_file():
        return
    if not _is_nonempty_ply(ply_path):
        skipped_empty.append(str(ply_path))
        return
    tasks.append(
        RenderTask(
            ply_path=ply_path,
            output_path=ply_to_png_path(ply_path, exp_dir, out_dir),
            **meta,
        )
    )


def _collect_vox_frame_tasks(
    tasks: List[RenderTask],
    frame_dir: Path,
    exp_dir: Path,
    out_dir: Path,
    scene: str,
    frame: str,
    vis_dual: bool,
    skipped_empty: List[str],
) -> None:
    for name in VOX_LOCAL_NAMES:
        _add_task(
            tasks,
            frame_dir / f"{name}.ply",
            exp_dir,
            out_dir,
            skipped_empty,
            task_type="vox",
            view_mode="local",
            scene=scene,
            frame=frame,
        )
    if vis_dual:
        _add_task(
            tasks,
            frame_dir / f"{VOX_DUAL_EXTRA[0]}.ply",
            exp_dir,
            out_dir,
            skipped_empty,
            task_type="vox",
            view_mode="local",
            scene=scene,
            frame=frame,
        )


def collect_vox_tasks_embodied(
    exp_dir: Path,
    out_dir: Path,
    vis_dual: bool,
    scenes: Optional[Set[str]],
    skipped_empty: List[str],
) -> List[RenderTask]:
    tasks: List[RenderTask] = []
    vox_root = exp_dir / "vox"
    if not vox_root.is_dir():
        return tasks

    global_root = vox_root / "global"
    if global_root.is_dir():
        for scene_dir in sorted(global_root.iterdir()):
            if not scene_dir.is_dir():
                continue
            scene = scene_dir.name
            if not _scene_allowed(scene, scenes):
                continue
            for name in VOX_GLOBAL_NAMES:
                _add_task(
                    tasks,
                    scene_dir / f"{name}.ply",
                    exp_dir,
                    out_dir,
                    skipped_empty,
                    task_type="vox",
                    view_mode="global",
                    scene=scene,
                )

    local_root = vox_root / "local"
    if local_root.is_dir():
        for scene_dir in sorted(local_root.iterdir()):
            if not scene_dir.is_dir():
                continue
            scene = scene_dir.name
            if not _scene_allowed(scene, scenes):
                continue
            for frame_dir in sorted(scene_dir.iterdir()):
                if not frame_dir.is_dir():
                    continue
                frame = frame_dir.name
                _collect_vox_frame_tasks(
                    tasks, frame_dir, exp_dir, out_dir, scene, frame, vis_dual, skipped_empty
                )

    return tasks


def collect_vox_tasks_mono(
    exp_dir: Path,
    out_dir: Path,
    vis_dual: bool,
    scenes: Optional[Set[str]],
    skipped_empty: List[str],
) -> List[RenderTask]:
    """Mono layout: vox/{scene}/{frame}/{pred,gt,...}.ply (no global/local level)."""
    tasks: List[RenderTask] = []
    vox_root = exp_dir / "vox"
    if not vox_root.is_dir():
        return tasks

    for scene_dir in sorted(vox_root.iterdir()):
        if not scene_dir.is_dir() or scene_dir.name in RESERVED_SUBDIRS:
            continue
        scene = scene_dir.name
        if not _scene_allowed(scene, scenes):
            continue
        for frame_dir in sorted(scene_dir.iterdir()):
            if not frame_dir.is_dir():
                continue
            _collect_vox_frame_tasks(
                tasks, frame_dir, exp_dir, out_dir, scene, frame_dir.name, vis_dual, skipped_empty
            )

    return tasks


def collect_vox_tasks(
    exp_dir: Path,
    out_dir: Path,
    vis_dual: bool,
    scenes: Optional[Set[str]],
    skipped_empty: List[str],
    mode: str = "embodied",
) -> List[RenderTask]:
    if mode == "mono":
        return collect_vox_tasks_mono(exp_dir, out_dir, vis_dual, scenes, skipped_empty)
    return collect_vox_tasks_embodied(exp_dir, out_dir, vis_dual, scenes, skipped_empty)


def _collect_gs_local_frame_tasks(
    tasks: List[RenderTask],
    frame_dir: Path,
    exp_dir: Path,
    out_dir: Path,
    scene: str,
    frame: str,
    skipped_empty: List[str],
) -> None:
    if (frame_dir / "before_dual").is_dir():
        for stage in GS_DUAL_STAGES:
            for stream in GS_DUAL_STREAMS:
                stream_dir = frame_dir / stage / stream
                if not stream_dir.is_dir():
                    continue
                for name in GS_NAMES:
                    _add_task(
                        tasks,
                        stream_dir / f"{name}.ply",
                        exp_dir,
                        out_dir,
                        skipped_empty,
                        task_type="gs",
                        view_mode="local",
                        scene=scene,
                        frame=frame,
                    )
    else:
        for name in GS_NAMES:
            _add_task(
                tasks,
                frame_dir / f"{name}.ply",
                exp_dir,
                out_dir,
                skipped_empty,
                task_type="gs",
                view_mode="local",
                scene=scene,
                frame=frame,
            )


def collect_gs_tasks_embodied(
    exp_dir: Path,
    out_dir: Path,
    scenes: Optional[Set[str]],
    skipped_empty: List[str],
) -> List[RenderTask]:
    tasks: List[RenderTask] = []
    gs_root = exp_dir / "gs"
    if not gs_root.is_dir():
        return tasks

    global_root = gs_root / "global"
    if global_root.is_dir():
        for scene_dir in sorted(global_root.iterdir()):
            if not scene_dir.is_dir():
                continue
            scene = scene_dir.name
            if not _scene_allowed(scene, scenes):
                continue
            for name in GS_NAMES:
                _add_task(
                    tasks,
                    scene_dir / f"{name}.ply",
                    exp_dir,
                    out_dir,
                    skipped_empty,
                    task_type="gs",
                    view_mode="global",
                    scene=scene,
                )

    local_root = gs_root / "local"
    if local_root.is_dir():
        for scene_dir in sorted(local_root.iterdir()):
            if not scene_dir.is_dir():
                continue
            scene = scene_dir.name
            if not _scene_allowed(scene, scenes):
                continue
            for frame_dir in sorted(scene_dir.iterdir()):
                if not frame_dir.is_dir():
                    continue
                _collect_gs_local_frame_tasks(
                    tasks, frame_dir, exp_dir, out_dir, scene, frame_dir.name, skipped_empty
                )

    return tasks


def collect_gs_tasks_mono(
    exp_dir: Path,
    out_dir: Path,
    scenes: Optional[Set[str]],
    skipped_empty: List[str],
) -> List[RenderTask]:
    """Mono layout: gs/{scene}/{frame}/gs_*.ply (no global/local level)."""
    tasks: List[RenderTask] = []
    gs_root = exp_dir / "gs"
    if not gs_root.is_dir():
        return tasks

    for scene_dir in sorted(gs_root.iterdir()):
        if not scene_dir.is_dir() or scene_dir.name in RESERVED_SUBDIRS:
            continue
        scene = scene_dir.name
        if not _scene_allowed(scene, scenes):
            continue
        for frame_dir in sorted(scene_dir.iterdir()):
            if not frame_dir.is_dir():
                continue
            _collect_gs_local_frame_tasks(
                tasks, frame_dir, exp_dir, out_dir, scene, frame_dir.name, skipped_empty
            )

    return tasks


def collect_gs_tasks(
    exp_dir: Path,
    out_dir: Path,
    scenes: Optional[Set[str]],
    skipped_empty: List[str],
    mode: str = "embodied",
) -> List[RenderTask]:
    if mode == "mono":
        return collect_gs_tasks_mono(exp_dir, out_dir, scenes, skipped_empty)
    return collect_gs_tasks_embodied(exp_dir, out_dir, scenes, skipped_empty)


def collect_tasks(
    exp_dir: Path,
    out_dir: Path,
    task_types: Set[str],
    vis_dual: bool,
    scenes: Optional[Set[str]],
    mode: str = "embodied",
) -> Tuple[List[RenderTask], List[str]]:
    tasks: List[RenderTask] = []
    skipped_empty: List[str] = []
    if "vox" in task_types:
        tasks.extend(collect_vox_tasks(exp_dir, out_dir, vis_dual, scenes, skipped_empty, mode))
    if "gs" in task_types:
        tasks.extend(collect_gs_tasks(exp_dir, out_dir, scenes, skipped_empty, mode))
    return tasks, skipped_empty


def group_tasks_by_scene_frame(tasks: List[RenderTask]) -> Dict[str, Dict[Optional[str], List[RenderTask]]]:
    grouped: Dict[str, Dict[Optional[str], List[RenderTask]]] = defaultdict(lambda: defaultdict(list))
    for task in tasks:
        grouped[task.scene][task.frame].append(task)
    return grouped


def run_vox_tasks(tasks: List[RenderTask], skip_existing: bool) -> List[str]:
    from source.voxel_visualizer import VoxelVisualizer, get_mlab

    VoxelVisualizer.setup_mayavi_env(offscreen=True)
    mlab = get_mlab()
    failures: List[str] = []
    visualizers = {
        VoxelVisualizer.VIEW_GLOBAL: VoxelVisualizer(view_mode=VoxelVisualizer.VIEW_GLOBAL),
        VoxelVisualizer.VIEW_LOCAL: VoxelVisualizer(view_mode=VoxelVisualizer.VIEW_LOCAL),
    }

    grouped = group_tasks_by_scene_frame(tasks)
    for scene in sorted(grouped):
        scene_tasks = grouped[scene]
        global_tasks = scene_tasks.pop(None, [])
        if global_tasks:
            print(f"\n[VOX] Scene {scene} (global)")
            for task in global_tasks:
                if _run_single_vox_task(task, visualizers, skip_existing, failures):
                    pass
                mlab.close(all=True)

        frames = sorted(k for k in scene_tasks if k is not None)
        if not frames:
            continue

        print(f"\n[VOX] Scene {scene} ({len(frames)} frames)")
        for frame in tqdm(frames, desc=scene, unit="frame"):
            for task in scene_tasks[frame]:
                _run_single_vox_task(task, visualizers, skip_existing, failures)
            mlab.close(all=True)

    return failures


def _run_single_vox_task(
    task: RenderTask,
    visualizers: dict,
    skip_existing: bool,
    failures: List[str],
) -> bool:
    if skip_existing and task.output_path.is_file():
        return True

    visualizer = visualizers[task.view_mode]
    try:
        task.output_path.parent.mkdir(parents=True, exist_ok=True)
        if task.view_mode == "global":
            camera_params = visualizer.resolve_camera_params(task.scene, use_zoom=False)
        else:
            camera_params = visualizer.resolve_camera_params(
                task.scene, task.frame, use_zoom=False
            )
        image_size = camera_params.get("image_size", visualizer._default_image_size())

        visualizer.visualize(
            task.ply_path,
            show_3d=False,
            save_image=True,
            output_path=task.output_path,
            camera_params=camera_params,
            image_size=image_size,
            remove_background=False,
        )
        return True
    except Exception as exc:
        failures.append(f"{task.ply_path}: {exc}")
        traceback.print_exc()
        return False


def run_gs_tasks(tasks: List[RenderTask], skip_existing: bool) -> List[str]:
    from source.gaussian_visualizer import GaussianVisualizer

    failures: List[str] = []
    grouped = group_tasks_by_scene_frame(tasks)

    for scene in sorted(grouped):
        scene_tasks = grouped[scene]
        global_tasks = scene_tasks.pop(None, [])
        if global_tasks:
            print(f"\n[GS] Scene {scene} (global)")
            for task in global_tasks:
                _run_single_gs_task(task, skip_existing, failures)

        frames = sorted(k for k in scene_tasks if k is not None)
        if not frames:
            continue

        print(f"\n[GS] Scene {scene} ({len(frames)} frames)")
        for frame in tqdm(frames, desc=scene, unit="frame"):
            for task in scene_tasks[frame]:
                _run_single_gs_task(task, skip_existing, failures)

    return failures


def _run_single_gs_task(task: RenderTask, skip_existing: bool, failures: List[str]) -> bool:
    if skip_existing and task.output_path.is_file():
        return True

    try:
        task.output_path.parent.mkdir(parents=True, exist_ok=True)
        GaussianVisualizer.render_file(
            str(task.ply_path),
            str(task.output_path),
            render_params=GS_RENDER_PARAMS,
            max_gaussians=5000,
            render_mode="enhanced",
            camera_preset=task.view_mode,
            **BRIGHT_LIGHT,
        )
        return True
    except Exception as exc:
        failures.append(f"{task.ply_path}: {exc}")
        traceback.print_exc()
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch visualize experiment epoch directory (vox + gs → PNG)"
    )
    parser.add_argument("--exp-dir", type=Path, required=True, help="Single epoch root directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for PNGs")
    parser.add_argument(
        "--tasks",
        type=str,
        default="vox,gs",
        help="Comma-separated task types: vox, gs",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=MODES,
        default="embodied",
        help="Directory layout: embodied (vox/global|local/...) or mono (vox/scene/frame/...)",
    )
    parser.add_argument("--vis-dual", action="store_true", help="Include dual-mode vox/gs paths")
    parser.add_argument(
        "--scenes",
        nargs="*",
        default=None,
        help="Optional scene names to process (default: all)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip rendering if output PNG already exists",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exp_dir = args.exp_dir.resolve()
    out_dir = args.output_dir.resolve()

    if not exp_dir.is_dir():
        print(f"Error: exp-dir does not exist: {exp_dir}")
        return 1

    if not (exp_dir / "vox").is_dir() and not (exp_dir / "gs").is_dir():
        print(f"Error: exp-dir must contain vox/ or gs/: {exp_dir}")
        return 1

    task_types = {t.strip() for t in args.tasks.split(",") if t.strip()}
    invalid = task_types - {"vox", "gs"}
    if invalid:
        print(f"Error: unsupported task types: {invalid}")
        return 1
    if not task_types:
        print("Error: no tasks specified")
        return 1

    scenes = set(args.scenes) if args.scenes else None
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks, skipped_empty = collect_tasks(
        exp_dir, out_dir, task_types, args.vis_dual, scenes, args.mode
    )
    if skipped_empty:
        print(f"Skipped {len(skipped_empty)} empty PLY file(s).")
    if not tasks:
        print("No PLY files found to visualize.")
        return 0

    scene_count = len({t.scene for t in tasks})
    frame_count = len({(t.scene, t.frame) for t in tasks if t.frame})
    print(
        f"Mode: {args.mode} | Found {len(tasks)} PLY files across {scene_count} scene(s), "
        f"{frame_count} frame(s). Output: {out_dir}"
    )

    failures: List[str] = []

    if "vox" in task_types:
        vox_tasks = [t for t in tasks if t.task_type == "vox"]
        if vox_tasks:
            print(f"\n=== Voxel rendering ({len(vox_tasks)} files) ===")
            failures.extend(run_vox_tasks(vox_tasks, args.skip_existing))

    if "gs" in task_types:
        gs_tasks = [t for t in tasks if t.task_type == "gs"]
        if gs_tasks:
            print(f"\n=== Gaussian rendering ({len(gs_tasks)} files) ===")
            failures.extend(run_gs_tasks(gs_tasks, args.skip_existing))

    if failures:
        print(f"\nCompleted with {len(failures)} failure(s):")
        for msg in failures:
            print(f"  - {msg}")
        return 1

    if skipped_empty:
        print(f"\nNote: {len(skipped_empty)} empty PLY file(s) were skipped (0 bytes).")

    print("\nAll visualizations completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
