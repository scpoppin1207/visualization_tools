# Vox Viewer

基于 PyQt5、Mayavi 和项目现有 `source/voxel_visualizer.py` 的交互式 voxel PLY 查看器。

## 启动

请从项目根目录运行：

```powershell
conda activate mayavi_clean
python -m vox_viewer.main
```

先执行无界面环境检查：

```powershell
python -m vox_viewer.main --check
```

也可以在启动时直接打开文件：

```powershell
python -m vox_viewer.main path\to\a.ply path\to\b.ply
```

## 使用方式

- 将一个或多个 `.ply` 从资源管理器拖进窗口，每个文件会创建独立标签页。
- 在资源管理器复制 `.ply` 后按 `Ctrl+V`，文件会复制到 `vox_viewer/imports/` 并打开。
- “导入副本”同样会复制文件；“打开 PLY”只读取原路径，不复制。
- 每个标签页支持旋转、缩放、平移、调整 voxel size、重置视角和保存截图。
- “打开内置样例”可用于快速确认完整 UI 和渲染流程。

输入 PLY 至少需要 `x/y/z` 顶点属性；推荐包含 `red/green/blue`。Viewer 复用
`VoxelVisualizer._load_and_voxelize`，默认以 `0.08` 为 voxel size 聚合彩色点云。

