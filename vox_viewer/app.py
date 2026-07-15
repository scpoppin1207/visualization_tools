"""PyQt5 user interface with embedded, independent Mayavi scenes."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

os.environ.setdefault("ETS_TOOLKIT", "qt")
os.environ.setdefault("QT_API", "pyqt5")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

import numpy as np
from mayavi.core.ui.api import MayaviScene, MlabSceneModel, SceneEditor
from PyQt5 import QtCore, QtGui, QtWidgets
from traits.api import HasTraits, Instance, on_trait_change
from traitsui.api import Item, View

from source.voxel_visualizer import VoxelVisualizer


APP_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = APP_DIR / "examples" / "sample_voxels.ply"
IMPORT_DIR = APP_DIR / "imports"


class MayaviModel(HasTraits):
    """Traits model that owns one Mayavi scene per viewer tab."""

    scene = Instance(MlabSceneModel, ())

    view = View(
        Item(
            "scene",
            editor=SceneEditor(scene_class=MayaviScene),
            height=500,
            width=700,
            show_label=False,
        ),
        resizable=True,
    )

    def __init__(self, ready_callback=None, **traits):
        super().__init__(**traits)
        self._ready_callback = ready_callback
        self._ready_emitted = False

    @on_trait_change("scene.activated")
    def _scene_activated(self):
        if self._ready_callback is not None and not self._ready_emitted:
            self._ready_emitted = True
            QtCore.QTimer.singleShot(0, self._ready_callback)


class DropPanel(QtWidgets.QFrame):
    """Large drop target shown on the welcome tab."""

    files_dropped = QtCore.pyqtSignal(list)
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropPanel")
        self.setAcceptDrops(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMinimumHeight(225)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 26, 24, 26)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        icon = QtWidgets.QLabel("＋")
        icon.setObjectName("dropIcon")
        icon.setAlignment(QtCore.Qt.AlignCenter)
        title = QtWidgets.QLabel("拖入一个或多个 .ply 文件")
        title.setObjectName("dropTitle")
        title.setAlignment(QtCore.Qt.AlignCenter)
        hint = QtWidgets.QLabel("也可以点击这里浏览文件，或按 Ctrl+V 粘贴资源管理器中复制的 PLY")
        hint.setObjectName("muted")
        hint.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(hint)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if _paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        paths = _paths_from_mime(event.mimeData())
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class ViewerTab(QtWidgets.QWidget):
    """One PLY file and one independent embedded Mayavi scene."""

    message = QtCore.pyqtSignal(str)

    def __init__(self, ply_path: Path, parent=None):
        super().__init__(parent)
        self.ply_path = ply_path.resolve()
        self._centers = None
        self._rendered = False
        self._build_ui()

        self.model = MayaviModel(ready_callback=self.render_voxels)
        self.traits_ui = self.model.edit_traits(parent=self.scene_host, kind="subpanel")
        self.scene_layout.addWidget(self.traits_ui.control)

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        controls = QtWidgets.QHBoxLayout()
        name = QtWidgets.QLabel(self.ply_path.name)
        name.setObjectName("viewerTitle")
        name.setToolTip(str(self.ply_path))
        controls.addWidget(name)
        controls.addStretch(1)

        controls.addWidget(QtWidgets.QLabel("Voxel size"))
        self.voxel_size = QtWidgets.QDoubleSpinBox()
        self.voxel_size.setDecimals(3)
        self.voxel_size.setRange(0.005, 2.0)
        self.voxel_size.setSingleStep(0.01)
        self.voxel_size.setValue(0.08)
        self.voxel_size.setToolTip("修改后点击“重新生成”")
        controls.addWidget(self.voxel_size)

        rerender = QtWidgets.QPushButton("重新生成")
        rerender.clicked.connect(self.render_voxels)
        reset = QtWidgets.QPushButton("重置视角")
        reset.clicked.connect(self.reset_camera)
        save = QtWidgets.QPushButton("保存截图")
        save.clicked.connect(self.save_screenshot)
        controls.addWidget(rerender)
        controls.addWidget(reset)
        controls.addWidget(save)
        layout.addLayout(controls)

        info = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("正在初始化 Mayavi 场景…")
        self.status_label.setObjectName("muted")
        self.path_label = QtWidgets.QLabel(str(self.ply_path))
        self.path_label.setObjectName("pathLabel")
        self.path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        info.addWidget(self.status_label)
        info.addStretch(1)
        info.addWidget(self.path_label, 1)
        layout.addLayout(info)

        self.scene_host = QtWidgets.QFrame()
        self.scene_host.setObjectName("sceneHost")
        self.scene_layout = QtWidgets.QVBoxLayout(self.scene_host)
        self.scene_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scene_host, 1)

    def render_voxels(self):
        if not hasattr(self, "model"):
            return

        app = QtWidgets.QApplication.instance()
        app.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._rendered = False
        self.status_label.setText("正在读取并体素化 PLY…")
        app.processEvents()

        try:
            visualizer = VoxelVisualizer(
                view_mode=VoxelVisualizer.VIEW_LOCAL,
                voxel_size=self.voxel_size.value(),
                verbose=False,
            )
            color_groups, centers = visualizer._load_and_voxelize(self.ply_path)

            scene = self.model.scene
            figure = scene.mayavi_scene
            scene.mlab.clf(figure=figure)
            for color_rgb, group_centers in color_groups.items():
                group_centers = np.asarray(group_centers)
                scene.mlab.points3d(
                    group_centers[:, 0],
                    group_centers[:, 1],
                    group_centers[:, 2],
                    scale_factor=self.voxel_size.value(),
                    mode="cube",
                    color=tuple(np.asarray(color_rgb) / 255.0),
                    opacity=1.0,
                    resolution=8,
                    figure=figure,
                )

            self._centers = centers
            self._apply_default_camera()
            self._tvtk_scene().background = (0.96, 0.97, 0.99)
            scene.mayavi_scene.render()
            self._rendered = True
            self.status_label.setText(
                f"已生成 {len(centers):,} 个体素 · {len(color_groups):,} 个颜色组"
            )
            self.message.emit(f"已打开 {self.ply_path.name}")
        except Exception as exc:
            self.status_label.setText("渲染失败")
            self.message.emit(f"渲染失败：{exc}")
            QtWidgets.QMessageBox.critical(
                self,
                "无法可视化 PLY",
                f"文件：{self.ply_path}\n\n{type(exc).__name__}: {exc}",
            )
        finally:
            app.restoreOverrideCursor()

    def _apply_default_camera(self):
        if self._centers is None or not len(self._centers):
            return
        min_bounds = np.min(self._centers, axis=0)
        max_bounds = np.max(self._centers, axis=0)
        center = (min_bounds + max_bounds) / 2.0
        scene_size = max(float(np.max(max_bounds - min_bounds)), self.voxel_size.value())

        self.model.scene.mlab.view(
            azimuth=75,
            elevation=50,
            focalpoint=center,
            figure=self.model.scene.mayavi_scene,
        )
        camera = self._tvtk_scene().camera
        camera.parallel_projection = True
        camera.parallel_scale = scene_size * 0.58
        camera.compute_view_plane_normal()

    def _tvtk_scene(self):
        """Return the TVTK scene wrapped by Mayavi's core Scene object."""
        mayavi_scene = self.model.scene.mayavi_scene
        tvtk_scene = getattr(mayavi_scene, "scene", None)
        if tvtk_scene is None:
            raise RuntimeError("Mayavi scene is not ready")
        return tvtk_scene

    def reset_camera(self):
        self._apply_default_camera()
        if hasattr(self, "model"):
            self.model.scene.mayavi_scene.render()

    def save_screenshot(self):
        if not self._rendered:
            QtWidgets.QMessageBox.information(self, "尚未渲染", "请等待当前 PLY 完成渲染。")
            return
        default_name = str(self.ply_path.with_name(f"{self.ply_path.stem}_vox.png"))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存 Vox 截图", default_name, "PNG 图像 (*.png)"
        )
        if not path:
            return
        self.model.scene.mlab.savefig(
            path,
            figure=self.model.scene.mayavi_scene,
            size=(1200, 900),
        )
        self.message.emit(f"截图已保存：{path}")

    def dispose(self):
        try:
            self.traits_ui.dispose()
        except Exception:
            pass
        try:
            self.model.scene.close()
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    """Application shell with file actions and multiple viewer tabs."""

    def __init__(self, initial_files: Iterable[Path] = ()): 
        super().__init__()
        self.setWindowTitle("Vox Viewer · Semantic Occupancy PLY")
        self.resize(1240, 820)
        self.setMinimumSize(900, 620)
        self.setAcceptDrops(True)
        self._build_ui()
        self._install_shortcuts()

        initial_files = list(initial_files)
        if initial_files:
            QtCore.QTimer.singleShot(0, lambda: self.open_paths(initial_files))

    def _build_ui(self):
        header = QtWidgets.QToolBar("文件")
        header.setMovable(False)
        header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        header.setIconSize(QtCore.QSize(21, 21))
        self.addToolBar(header)

        open_action = header.addAction("打开 PLY")
        open_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(self.choose_files)
        import_action = header.addAction("导入副本")
        import_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        import_action.triggered.connect(self.choose_and_import)
        sample_action = header.addAction("打开内置样例")
        sample_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        sample_action.triggered.connect(lambda: self.open_paths([SAMPLE_FILE]))
        header.addSeparator()
        home_action = header.addAction("使用说明")
        home_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirHomeIcon))
        home_action.triggered.connect(self.show_welcome)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)
        self.welcome_page = self._welcome_page()
        self.tabs.addTab(self.welcome_page, "开始")
        self.tabs.tabBar().setTabButton(0, QtWidgets.QTabBar.RightSide, None)

        self.statusBar().showMessage("准备就绪 · 拖入 PLY 或点击“打开 PLY”")

    def _welcome_page(self):
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("welcomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        page = QtWidgets.QWidget()
        page.setObjectName("welcomePage")
        outer = QtWidgets.QHBoxLayout(page)
        outer.setContentsMargins(24, 30, 24, 30)
        outer.setSpacing(0)

        content = QtWidgets.QWidget()
        content.setObjectName("welcomeContent")
        content.setMaximumWidth(1180)
        content.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(26, 24, 26, 26)
        layout.setSpacing(20)

        outer.addStretch(1)
        outer.addWidget(content, 12, QtCore.Qt.AlignTop)
        outer.addStretch(1)

        title = QtWidgets.QLabel("Vox Viewer")
        title.setObjectName("heroTitle")
        subtitle = QtWidgets.QLabel(
            "彩色点云 PLY → 体素聚合 → Mayavi 交互场景\n"
            "每个文件拥有独立标签页，可以同时旋转、缩放和比较多个结果。"
        )
        subtitle.setObjectName("heroSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        drop = DropPanel()
        drop.clicked.connect(self.choose_files)
        drop.files_dropped.connect(self.open_paths)
        layout.addWidget(drop)

        actions = QtWidgets.QHBoxLayout()
        open_button = QtWidgets.QPushButton("打开 PLY 文件")
        open_button.setObjectName("primaryButton")
        open_button.clicked.connect(self.choose_files)
        import_button = QtWidgets.QPushButton("复制到 imports 并打开")
        import_button.clicked.connect(self.choose_and_import)
        sample_button = QtWidgets.QPushButton("查看内置彩色体素样例")
        sample_button.clicked.connect(lambda: self.open_paths([SAMPLE_FILE]))
        actions.addWidget(open_button)
        actions.addWidget(import_button)
        actions.addWidget(sample_button)
        actions.addStretch(1)
        actions.setSpacing(12)
        layout.addLayout(actions)

        guide = QtWidgets.QLabel(
            "操作提示\n"
            "① 从资源管理器拖入一个或多个 .ply；或复制文件后在这里按 Ctrl+V。\n"
            "② 左键旋转、滚轮缩放、中键平移；不同文件会分别出现在标签页中。\n"
            "③ PLY 需要包含 x/y/z，建议同时包含 red/green/blue；无颜色时显示为黑色。"
        )
        guide.setObjectName("guideBox")
        guide.setWordWrap(True)
        guide.setMinimumHeight(112)
        layout.addWidget(guide)
        layout.addStretch(1)
        scroll.setWidget(page)
        return scroll

    def _install_shortcuts(self):
        paste = QtWidgets.QShortcut(QtGui.QKeySequence.Paste, self)
        paste.setContext(QtCore.Qt.ApplicationShortcut)
        paste.activated.connect(self.paste_files)

    def show_welcome(self):
        index = self.tabs.indexOf(self.welcome_page)
        if index >= 0:
            self.tabs.setCurrentIndex(index)

    def choose_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择一个或多个 voxel PLY", "", "PLY 点云 (*.ply)"
        )
        self.open_paths([Path(path) for path in paths])

    def choose_and_import(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择要复制到 Vox Viewer 的 PLY", "", "PLY 点云 (*.ply)"
        )
        if paths:
            self.import_copies([Path(path) for path in paths])

    def paste_files(self):
        mime = QtWidgets.QApplication.clipboard().mimeData()
        paths = _paths_from_mime(mime)
        if not paths and mime.hasText():
            candidate = Path(mime.text().strip().strip('"'))
            if candidate.is_file() and candidate.suffix.lower() == ".ply":
                paths = [candidate]
        if not paths:
            self.statusBar().showMessage("剪贴板中没有可用的 .ply 文件", 4000)
            return
        self.import_copies(paths)

    def import_copies(self, paths: Iterable[Path]):
        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        copied = []
        for source in _valid_ply_paths(paths):
            destination = _unique_destination(IMPORT_DIR, source.name)
            shutil.copy2(source, destination)
            copied.append(destination)
        if copied:
            self.statusBar().showMessage(f"已复制 {len(copied)} 个文件到 {IMPORT_DIR}", 5000)
            self.open_paths(copied)

    def open_paths(self, paths: Iterable[Path]):
        paths = list(paths)
        valid = _valid_ply_paths(paths)
        invalid_count = len(paths) - len(valid)
        for path in valid:
            viewer = ViewerTab(path)
            viewer.message.connect(self.statusBar().showMessage)
            index = self.tabs.addTab(viewer, path.stem)
            self.tabs.setTabToolTip(index, str(path))
            self.tabs.setCurrentIndex(index)
        if invalid_count:
            self.statusBar().showMessage(
                f"已忽略 {invalid_count} 个不存在或非 .ply 的文件", 5000
            )

    def close_tab(self, index):
        if self.tabs.widget(index) is self.welcome_page:
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if isinstance(widget, ViewerTab):
            widget.dispose()
        widget.deleteLater()

    def dragEnterEvent(self, event):
        if _paths_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = _paths_from_mime(event.mimeData())
        if paths:
            self.open_paths(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, ViewerTab):
                widget.dispose()
        super().closeEvent(event)


def _valid_ply_paths(paths: Iterable[Path]) -> list[Path]:
    return [
        Path(path).resolve()
        for path in paths
        if Path(path).is_file() and Path(path).suffix.lower() == ".ply"
    ]


def _paths_from_mime(mime: QtCore.QMimeData) -> list[Path]:
    if not mime.hasUrls():
        return []
    return _valid_ply_paths(Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile())


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    counter = 1
    while candidate.exists():
        candidate = directory / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
        counter += 1
    return candidate


STYLE = """
QMainWindow { background: #f4f7fb; }
QWidget { color: #1e293b; font-size: 15px; }
QWidget#welcomePage, QScrollArea#welcomeScroll { background: #f4f7fb; }
QLabel { background: transparent; }
QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #dce3ed; spacing: 9px; padding: 8px 14px; min-height: 46px; }
QToolBar QToolButton { min-width: 34px; min-height: 32px; padding: 5px 10px; }
QToolButton, QPushButton { background: #ffffff; border: 1px solid #c7d2e0; border-radius: 7px; padding: 9px 16px; min-height: 24px; }
QToolButton:hover, QPushButton:hover { background: #eef4ff; border-color: #6d91d8; }
QToolButton:pressed, QPushButton:pressed { background: #dfeaff; }
QPushButton#primaryButton { background: #2563eb; color: white; border-color: #2563eb; font-weight: 600; }
QPushButton#primaryButton:hover { background: #1d4ed8; }
QWidget#welcomeContent { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 14px; }
QLabel#heroTitle { font-size: 38px; font-weight: 700; color: #172554; }
QLabel#heroSubtitle { font-size: 17px; color: #52627a; }
QFrame#dropPanel { background: #f9fbff; border: 2px dashed #8facd4; border-radius: 12px; }
QFrame#dropPanel[dragActive="true"] { background: #eaf2ff; border-color: #2563eb; }
QLabel#dropIcon { color: #2563eb; font-size: 46px; font-weight: 300; }
QLabel#dropTitle { font-size: 21px; font-weight: 600; color: #243b67; }
QLabel#muted { color: #64748b; }
QLabel#guideBox { background: #eef4fc; border: 1px solid #d4e1f2; border-radius: 9px; padding: 18px; color: #334a68; font-size: 15px; }
QLabel#viewerTitle { font-size: 19px; font-weight: 600; color: #1e3a5f; }
QLabel#pathLabel { color: #7b8798; }
QFrame#sceneHost { background: #f5f7fb; border: 1px solid #d7dee9; border-radius: 8px; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #e4eaf2; padding: 12px 20px; min-width: 72px; margin-right: 3px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:hover { background: #edf2f8; }
QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; font-weight: 600; }
QStatusBar { background: #ffffff; border-top: 1px solid #dfe5ee; color: #52627a; min-height: 28px; }
QDoubleSpinBox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 7px; min-height: 24px; min-width: 76px; }
QScrollBar:vertical { background: #edf1f6; width: 12px; margin: 2px; border-radius: 6px; }
QScrollBar::handle:vertical { background: #aebed2; min-height: 36px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def run(initial_files: Iterable[Path] = ()) -> int:
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Vox Viewer")
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 11))
    app.setStyleSheet(STYLE)
    window = MainWindow(initial_files)
    window.show()
    return app.exec_()
