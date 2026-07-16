# GS Viewer

基于 PyQt5、Mayavi 和项目现有 `source/gaussian_visualizer.py` 的交互式 3D Gaussian Splatting PLY 查看器。

## 启动

请从项目根目录运行：

```powershell
conda activate mayavi_clean
python -m gs_viewer.main
```

先执行无界面环境检查：

```powershell
python -m gs_viewer.main --check
```

也可以在启动时直接打开文件：

```powershell
python -m gs_viewer.main path\to\a.ply path\to\b.ply
```

## 使用方式

- 将一个或多个 `.ply` 从资源管理器拖进窗口，每个文件会创建独立标签页。
- 在资源管理器复制 `.ply` 后按 `Ctrl+V`，文件会复制到 `gs_viewer/imports/` 并打开。
- “导入副本”同样会复制文件；“打开 PLY”只读取原路径，不复制。
- 每个标签页支持旋转、缩放、平移、调整 Max GS / Opacity / Scale、重置视角和保存截图。
- 默认以彩色球体快速预览（与 Vox Viewer 相同的 Mayavi `points3d` 路径，稳定可见）。勾选“椭球”可改为各向异性网格。
- 打开至少两个 PLY 后可点击“分屏对比”，左右两侧的标签页和 Mayavi 场景可以独立操作。
- 分屏状态下在左侧选择标签，再点击“在右侧打开”即可切换对比对象；右侧使用独立 Mayavi 场景。再次点击“退出分屏”可关闭右侧对比区。
- 拖动中间带抓手标记的蓝灰色分隔条时会显示轻量预览线；松开后应用左右 Viewer 宽度，避免 VTK 场景实时缩放造成卡顿。
- “打开内置样例”会同时打开两个样例，便于立刻试用分屏对比。

## 输入格式

PLY 需要包含标准 3DGS 顶点属性：

- `x / y / z`
- `opacity`
- `f_dc_0 / f_dc_1 / f_dc_2`
- `scale_0 / scale_1 / scale_2`
- `rot_0 / rot_1 / rot_2 / rot_3`

Viewer 复用 `GaussianVisualizer.load_ply_data`：轴重映射、sigmoid opacity、`exp(scale)`、SH DC 颜色增强。交互渲染按不透明度优先选取椭球，默认最多 2000 个。

高质量离线渲染仍请使用 `gaussian/` 下的 Mitsuba 脚本（`renderpy` 环境）。
