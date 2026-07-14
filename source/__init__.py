__all__ = ["GaussianVisualizer", "VoxelVisualizer"]


def __getattr__(name):
    if name == "GaussianVisualizer":
        from source.gaussian_visualizer import GaussianVisualizer
        return GaussianVisualizer
    if name == "VoxelVisualizer":
        from source.voxel_visualizer import VoxelVisualizer
        return VoxelVisualizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
