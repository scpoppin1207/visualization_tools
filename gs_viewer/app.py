"""PyQt5 user interface with embedded, independent Mayavi scenes for Gaussians."""

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

from source.gaussian_visualizer import GaussianVisualizer


APP_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = APP_DIR / "examples" / "sample_gaussians.ply"
SAMPLE_FILE_B = APP_DIR / "examples" / "sample_gaussians_b.ply"
IMPORT_DIR = APP_DIR / "imports"


class MayaviModel(HasTraits):
    """Traits model that owns one Mayavi scene per viewer tab."""

    scene = Instance(MlabSceneModel, ())

    view = View(
        Item(
            "scene",
            editor=SceneEditor(scene_class=MayaviScene),
            height=360,
            width=420,
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


class ElidedLabel(QtWidgets.QLabel):
    """Label that keeps long paths/status text from forcing a wide pane."""

    def __init__(self, text="", parent=None, mode=QtCore.Qt.ElideMiddle):
        super().__init__(parent)
        self._full_text = ""
        self._elide_mode = mode
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self._update_elided_text()

    def fullText(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        width = max(self.contentsRect().width(), 20)
        shown = self.fontMetrics().elidedText(self._full_text, self._elide_mode, width)
        QtWidgets.QLabel.setText(self, shown)


class ResponsiveTabWidget(QtWidgets.QTabWidget):
    """Tab widget with a deliberately small splitter constraint."""

    def minimumSizeHint(self):
        return QtCore.QSize(330, 280)

    def sizeHint(self):
        return QtCore.QSize(620, 640)


class ComparisonSplitterHandle(QtWidgets.QSplitterHandle):
    """Visible draggable divider for the comparison panes."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hovered = False
        self._dragging = False
        self._press_offset = 0
        self._pending_position = None
        self.setCursor(QtCore.Qt.SplitHCursor)
        self.setToolTip("拖动预览分隔位置，松开后应用宽度")

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self._dragging = True
        self._press_offset = event.pos().x()
        self._pending_position = self.pos().x()
        self.splitter().setRubberBand(self._pending_position)
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            super().mouseMoveEvent(event)
            return
        splitter = self.splitter()
        handle_index = self._handle_index()
        parent_pos = splitter.mapFromGlobal(event.globalPos())
        requested = parent_pos.x() - self._press_offset
        minimum, maximum = splitter.getRange(handle_index)
        self._pending_position = max(minimum, min(maximum, requested))
        splitter.setRubberBand(self._pending_position)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._dragging:
            self._dragging = False
            self.releaseMouse()
            splitter = self.splitter()
            splitter.setRubberBand(-1)
            if self._pending_position is not None:
                splitter.moveSplitter(self._pending_position, self._handle_index())
            self._pending_position = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _handle_index(self):
        splitter = self.splitter()
        for index in range(1, splitter.count()):
            if splitter.handle(index) is self:
                return index
        return 1

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor("#9eb4d1" if self._hovered else "#c5d1e1"))

        center = self.rect().center()
        painter.setPen(QtGui.QPen(QtGui.QColor("#446b9b"), 1.5))
        painter.drawLine(center.x(), center.y() - 25, center.x(), center.y() + 25)
        painter.setBrush(QtGui.QColor("#446b9b"))
        painter.setPen(QtCore.Qt.NoPen)
        for offset in (-10, 0, 10):
            painter.drawEllipse(QtCore.QPoint(center.x(), center.y() + offset), 2, 2)


class ComparisonSplitter(QtWidgets.QSplitter):
    """Horizontal splitter that resizes both live Mayavi panes continuously."""

    def __init__(self, parent=None):
        super().__init__(QtCore.Qt.Horizontal, parent)
        self.setHandleWidth(11)
        # VTK/OpenGL resizing is expensive. Preview with a rubber band and
        # resize both render windows only once when the mouse is released.
        self.setOpaqueResize(False)

    def createHandle(self):
        return ComparisonSplitterHandle(self.orientation(), self)


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
        title = QtWidgets.QLabel("拖入一个或多个 Gaussian .ply 文件")
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
    """One Gaussian PLY file and one independent embedded Mayavi scene."""

    message = QtCore.pyqtSignal(str)

    def __init__(self, ply_path: Path, parent=None):
        super().__init__(parent)
        self.ply_path = ply_path.resolve()
        self._centers = None
        self._rendered = False
        self._compact = False
        self._visualizer = None
        self._build_ui()

        self.model = MayaviModel(ready_callback=self.render_gaussians)
        self.traits_ui = self.model.edit_traits(parent=self.scene_host, kind="subpanel")
        self.scene_layout.addWidget(self.traits_ui.control)

    def _build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 14)
        self.main_layout.setSpacing(9)

        heading = QtWidgets.QHBoxLayout()
        self.name_label = ElidedLabel(self.ply_path.name, mode=QtCore.Qt.ElideRight)
        self.name_label.setObjectName("viewerTitle")
        self.name_label.setToolTip(str(self.ply_path))
        self.path_label = ElidedLabel(str(self.ply_path))
        self.path_label.setObjectName("pathLabel")
        self.path_label.setToolTip(str(self.ply_path))
        heading.addWidget(self.name_label, 1)
        heading.addWidget(self.path_label, 2)
        self.main_layout.addLayout(heading)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)
        self.status_label = ElidedLabel("正在初始化 Mayavi 场景…", mode=QtCore.Qt.ElideRight)
        self.status_label.setObjectName("muted")
        controls.addWidget(self.status_label, 1)

        self.max_caption = QtWidgets.QLabel("Max GS")
        controls.addWidget(self.max_caption)
        self.max_gaussians = QtWidgets.QSpinBox()
        self.max_gaussians.setRange(50, 20000)
        self.max_gaussians.setSingleStep(100)
        self.max_gaussians.setValue(2000)
        self.max_gaussians.setToolTip("按不透明度优先选取的椭球数量上限")
        controls.addWidget(self.max_gaussians)

        self.opacity_caption = QtWidgets.QLabel("Opacity≥")
        controls.addWidget(self.opacity_caption)
        self.opacity_threshold = QtWidgets.QDoubleSpinBox()
        self.opacity_threshold.setDecimals(3)
        self.opacity_threshold.setRange(0.0, 1.0)
        self.opacity_threshold.setSingleStep(0.01)
        self.opacity_threshold.setValue(0.05)
        self.opacity_threshold.setToolTip("过滤低不透明度高斯")
        controls.addWidget(self.opacity_threshold)

        self.scale_caption = QtWidgets.QLabel("Scale×")
        controls.addWidget(self.scale_caption)
        self.scale_multiplier = QtWidgets.QDoubleSpinBox()
        self.scale_multiplier.setDecimals(2)
        self.scale_multiplier.setRange(0.05, 10.0)
        self.scale_multiplier.setSingleStep(0.1)
        self.scale_multiplier.setValue(1.0)
        self.scale_multiplier.setToolTip("椭球/球体尺度倍率，便于对比观察")
        controls.addWidget(self.scale_multiplier)

        self.ellipsoid_mode = QtWidgets.QCheckBox("椭球")
        self.ellipsoid_mode.setChecked(False)
        self.ellipsoid_mode.setToolTip(
            "关闭：快速球体预览（默认，稳定）\n打开：各向异性椭球网格（更慢）"
        )
        controls.addWidget(self.ellipsoid_mode)

        self.rerender_button = QtWidgets.QPushButton("重新生成")
        self.rerender_button.setObjectName("viewerActionButton")
        self.rerender_button.clicked.connect(self.render_gaussians)
        self.reset_button = QtWidgets.QPushButton("重置视角")
        self.reset_button.setObjectName("viewerActionButton")
        self.reset_button.clicked.connect(self.reset_camera)
        self.save_button = QtWidgets.QPushButton("保存截图")
        self.save_button.setObjectName("viewerActionButton")
        self.save_button.clicked.connect(self.save_screenshot)
        controls.addWidget(self.rerender_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.save_button)
        self.main_layout.addLayout(controls)

        self.scene_host = QtWidgets.QFrame()
        self.scene_host.setObjectName("sceneHost")
        self.scene_layout = QtWidgets.QVBoxLayout(self.scene_host)
        self.scene_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.scene_host, 1)

    def set_compact_mode(self, compact):
        self._compact = bool(compact)
        self.setProperty("compact", self._compact)
        self.max_caption.setText("Max" if compact else "Max GS")
        self.opacity_caption.setText("α≥" if compact else "Opacity≥")
        self.scale_caption.setText("×" if compact else "Scale×")
        self.rerender_button.setText("重绘" if compact else "重新生成")
        self.reset_button.setText("重置" if compact else "重置视角")
        self.save_button.setText("截图" if compact else "保存截图")
        self.path_label.setVisible(not compact)
        margins = (8, 8, 8, 9) if compact else (14, 12, 14, 14)
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(6 if compact else 9)
        self.style().unpolish(self)
        self.style().polish(self)

    def render_gaussians(self):
        if not hasattr(self, "model"):
            return

        app = QtWidgets.QApplication.instance()
        app.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._rendered = False
        self.status_label.setText("正在读取 Gaussian PLY…")
        app.processEvents()

        try:
            if self._visualizer is None:
                self._visualizer = GaussianVisualizer(verbose=False)
                self._visualizer.load_ply_data(self.ply_path)

            xyz, colors, scales, rotations, opacity = self._visualizer.select_for_display(
                max_gaussians=self.max_gaussians.value(),
                opacity_threshold=self.opacity_threshold.value(),
            )

            vertices = faces = vertex_colors = vertex_opacity = None
            if self.ellipsoid_mode.isChecked() and len(xyz):
                self.status_label.setText("正在生成椭球网格…")
                app.processEvents()

            scene = self.model.scene
            figure = scene.mayavi_scene
            scene.mlab.clf(figure=figure)

            if len(xyz):
                if self.ellipsoid_mode.isChecked():
                    try:
                        self._draw_ellipsoids(
                            scene,
                            figure,
                            xyz,
                            colors,
                            scales,
                            rotations,
                            opacity,
                            self.scale_multiplier.value(),
                        )
                    except Exception as mesh_exc:
                        self.message.emit(
                            f"椭球绘制失败，回退球体预览：{mesh_exc}"
                        )
                        self._draw_spheres(
                            scene,
                            figure,
                            xyz,
                            colors,
                            scales,
                            opacity,
                            self.scale_multiplier.value(),
                        )
                else:
                    self._draw_spheres(
                        scene,
                        figure,
                        xyz,
                        colors,
                        scales,
                        opacity,
                        self.scale_multiplier.value(),
                    )

            self._centers = xyz if len(xyz) else None
            self._apply_default_camera()
            self._tvtk_scene().background = (0.96, 0.97, 0.99)
            scene.mayavi_scene.render()
            self._rendered = True
            total = 0 if self._visualizer.xyz is None else len(self._visualizer.xyz)
            mode = "椭球" if self.ellipsoid_mode.isChecked() else "球体"
            self.status_label.setText(
                f"已显示 {len(xyz):,} / {total:,} 个高斯（{mode}）"
            )
            self.message.emit(f"已打开 {self.ply_path.name}")
        except Exception as exc:
            self.status_label.setText("渲染失败")
            self.message.emit(f"渲染失败：{exc}")
            QtWidgets.QMessageBox.critical(
                self,
                "无法可视化 Gaussian PLY",
                f"文件：{self.ply_path}\n\n{type(exc).__name__}: {exc}",
            )
        finally:
            app.restoreOverrideCursor()

    @staticmethod
    def _draw_ellipsoids(
        scene,
        figure,
        xyz,
        colors,
        scales,
        rotations,
        opacity,
        scale_multiplier,
    ):
        """Draw anisotropic ellipsoids with solid Mayavi colors.

        Per-vertex RGB via ``direct_scalars`` is unreliable in this Mayavi/VTK
        stack (meshes come out white). Group by quantized color and use
        ``triangular_mesh(..., color=rgb)`` instead — same approach as the
        sphere preview / vox_viewer.
        """
        xyz = np.asarray(xyz, dtype=np.float64)
        colors = np.clip(np.asarray(colors, dtype=np.float64), 0.0, 1.0)
        scales = np.asarray(scales, dtype=np.float64)
        rotations = np.asarray(rotations, dtype=np.float64)
        opacity = np.clip(np.asarray(opacity, dtype=np.float64).reshape(-1), 0.0, 1.0)

        # 5 bits/channel keeps draw calls low while preserving appearance.
        q = (colors * 31.0).astype(np.int32)
        keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]

        for key in np.unique(keys):
            mask = keys == key
            verts, faces, _, _ = GaussianVisualizer.build_combined_ellipsoid_mesh(
                xyz[mask],
                colors[mask],
                scales[mask],
                rotations[mask],
                opacity[mask],
                scale_multiplier=scale_multiplier,
                n_theta=10,
                n_phi=6,
            )
            if len(verts) == 0:
                continue
            color = tuple((q[mask][0].astype(np.float64) / 31.0).tolist())
            alpha = float(np.clip(np.mean(opacity[mask]), 0.55, 1.0))
            scene.mlab.triangular_mesh(
                verts[:, 0],
                verts[:, 1],
                verts[:, 2],
                faces,
                color=color,
                opacity=alpha,
                figure=figure,
            )

    @staticmethod
    def _draw_spheres(scene, figure, xyz, colors, scales, opacity, scale_multiplier):
        """Reliable Mayavi path used like vox_viewer: colored sphere glyphs."""
        # Use max-axis length so sphere size matches ellipsoid major axis better.
        radii = np.max(np.asarray(scales), axis=1) * float(scale_multiplier) * 2.0
        alphas = np.clip(np.asarray(opacity).reshape(-1), 0.0, 1.0)
        rgb = np.clip(np.asarray(colors), 0.0, 1.0)

        # Quantize colors to keep draw-call count manageable.
        q = (rgb * 15.0).astype(np.int32)
        keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
        for key in np.unique(keys):
            mask = keys == key
            pts = xyz[mask]
            color = tuple((q[mask][0].astype(np.float64) / 15.0).tolist())
            scale_factor = float(max(np.mean(radii[mask]), 1e-5))
            alpha = float(np.clip(np.mean(alphas[mask]), 0.25, 1.0))
            scene.mlab.points3d(
                pts[:, 0],
                pts[:, 1],
                pts[:, 2],
                scale_factor=scale_factor,
                mode="sphere",
                color=color,
                opacity=alpha,
                resolution=12,
                figure=figure,
            )

    def _apply_default_camera(self):
        if self._centers is None or not len(self._centers):
            return
        min_bounds = np.min(self._centers, axis=0)
        max_bounds = np.max(self._centers, axis=0)
        center = (min_bounds + max_bounds) / 2.0
        scene_size = max(float(np.max(max_bounds - min_bounds)), 0.2)

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
        default_name = str(self.ply_path.with_name(f"{self.ply_path.stem}_gs.png"))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存 GS 截图", default_name, "PNG 图像 (*.png)"
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
        self.setWindowTitle("GS Viewer · 3D Gaussian Splatting PLY")
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
        sample_action.triggered.connect(self.open_samples)
        header.addSeparator()
        home_action = header.addAction("使用说明")
        home_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirHomeIcon))
        home_action.triggered.connect(self.show_welcome)
        header.addSeparator()
        self.split_action = header.addAction("分屏对比")
        self.split_action.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton)
        )
        self.split_action.setCheckable(True)
        self.split_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.split_action.toggled.connect(self.set_split_enabled)

        self.splitter = ComparisonSplitter()
        self.splitter.setObjectName("viewerSplitter")
        self.splitter.setChildrenCollapsible(False)

        self.tabs = self._create_tab_widget("leftTabs")
        self.right_tabs = self._create_tab_widget("rightTabs")
        self.right_tabs.hide()
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.right_tabs)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        self.move_right_button = QtWidgets.QPushButton("在右侧打开  →")
        self.move_right_button.setObjectName("paneMoveButton")
        self.move_right_button.clicked.connect(self.open_current_in_right)
        self.move_right_button.hide()
        self.tabs.setCornerWidget(self.move_right_button, QtCore.Qt.TopRightCorner)

        self.right_pane_label = QtWidgets.QLabel("右侧对比区")
        self.right_pane_label.setObjectName("rightPaneLabel")
        self.right_pane_label.hide()
        self.right_tabs.setCornerWidget(self.right_pane_label, QtCore.Qt.TopRightCorner)

        self.welcome_page = self._welcome_page()
        self.tabs.addTab(self.welcome_page, "开始")
        self.tabs.tabBar().setTabButton(0, QtWidgets.QTabBar.RightSide, None)

        self.statusBar().showMessage("准备就绪 · 拖入 Gaussian PLY 或点击“打开 PLY”")

    def _create_tab_widget(self, object_name):
        tabs = ResponsiveTabWidget()
        tabs.setObjectName(object_name)
        tabs.setMinimumWidth(0)
        tabs.setDocumentMode(True)
        tabs.setTabsClosable(True)
        tabs.setMovable(True)
        tabs.tabCloseRequested.connect(lambda index, pane=tabs: self.close_tab(pane, index))
        return tabs

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

        title = QtWidgets.QLabel("GS Viewer")
        title.setObjectName("heroTitle")
        subtitle = QtWidgets.QLabel(
            "3D Gaussian Splatting PLY → 椭球网格 → Mayavi 交互场景\n"
            "每个文件拥有独立标签页，可以同时旋转、缩放和分屏比较多个结果。"
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
        sample_button = QtWidgets.QPushButton("查看内置 Gaussian 样例")
        sample_button.clicked.connect(self.open_samples)
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
            "③ 打开至少两个 PLY 后点击“分屏对比”，可将标签页放在左右两侧。\n"
            "④ PLY 需要包含 x/y/z、opacity、f_dc_*、scale_*、rot_*（标准 3DGS 属性）。\n"
            "⑤ 默认用球体快速预览；勾选“椭球”可切换各向异性网格（更慢）。\n"
            "⑥ 可用 Max GS / Opacity / Scale 控制显示数量与大小，再点“重新生成”。"
        )
        guide.setObjectName("guideBox")
        guide.setWordWrap(True)
        guide.setMinimumHeight(156)
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

    def open_samples(self):
        samples = [SAMPLE_FILE]
        if SAMPLE_FILE_B.is_file():
            samples.append(SAMPLE_FILE_B)
        self.open_paths(samples)

    def set_split_enabled(self, enabled):
        if enabled:
            viewer_indices = self._viewer_indices(self.tabs)
            if len(viewer_indices) < 2:
                self.split_action.blockSignals(True)
                self.split_action.setChecked(False)
                self.split_action.blockSignals(False)
                QtWidgets.QMessageBox.information(
                    self,
                    "需要至少两个 PLY",
                    "请先打开至少两个 Gaussian PLY 标签页，再启用分屏对比。",
                )
                return

            current_index = self.tabs.currentIndex()
            if not isinstance(self.tabs.widget(current_index), ViewerTab):
                current_index = viewer_indices[-1]

            self.right_tabs.show()
            self.move_right_button.show()
            self.right_pane_label.show()

            for index in viewer_indices:
                self.tabs.widget(index).set_compact_mode(True)

            source_viewer = self.tabs.widget(current_index)
            self._add_viewer_tab(source_viewer.ply_path, self.right_tabs)

            remaining = [index for index in viewer_indices if index != current_index]
            if remaining:
                self.tabs.setCurrentIndex(remaining[-1])
            self.split_action.setText("退出分屏")
            QtCore.QTimer.singleShot(
                0,
                lambda: self.splitter.setSizes(
                    [max(self.splitter.width() // 2, 1)] * 2
                ),
            )
            self.statusBar().showMessage(
                "已启用分屏 · 左右标签页中的 Mayavi 场景可独立操作", 5000
            )
            return

        self._merge_right_pane()

    def _merge_right_pane(self):
        while self.right_tabs.count():
            widget = self.right_tabs.widget(0)
            self.right_tabs.removeTab(0)
            if isinstance(widget, ViewerTab):
                widget.dispose()
            widget.deleteLater()
        self.right_tabs.hide()
        self.move_right_button.hide()
        self.right_pane_label.hide()
        for index in self._viewer_indices(self.tabs):
            self.tabs.widget(index).set_compact_mode(False)
        self.split_action.setText("分屏对比")
        self.statusBar().showMessage("已退出分屏，右侧对比区已关闭", 4000)

    def open_current_in_right(self):
        index = self.tabs.currentIndex()
        viewer = self.tabs.widget(index)
        if not isinstance(viewer, ViewerTab):
            self.statusBar().showMessage("请先在左侧选择一个 Gaussian 标签页", 3500)
            return

        for right_index in self._viewer_indices(self.right_tabs):
            right_viewer = self.right_tabs.widget(right_index)
            if right_viewer.ply_path == viewer.ply_path:
                self.right_tabs.setCurrentIndex(right_index)
                self.statusBar().showMessage("该 PLY 已在右侧对比区中", 3000)
                return

        self._add_viewer_tab(viewer.ply_path, self.right_tabs)
        self.statusBar().showMessage(f"已在右侧打开 {viewer.ply_path.name}", 4000)

    @staticmethod
    def _viewer_indices(tabs):
        return [
            index
            for index in range(tabs.count())
            if isinstance(tabs.widget(index), ViewerTab)
        ]

    def choose_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择一个或多个 Gaussian PLY", "", "PLY 高斯点云 (*.ply)"
        )
        self.open_paths([Path(path) for path in paths])

    def choose_and_import(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择要复制到 GS Viewer 的 PLY", "", "PLY 高斯点云 (*.ply)"
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
            self._add_viewer_tab(path, self.tabs)
        if invalid_count:
            self.statusBar().showMessage(
                f"已忽略 {invalid_count} 个不存在或非 .ply 的文件", 5000
            )

    def _add_viewer_tab(self, path, target_tabs):
        viewer = ViewerTab(path)
        if hasattr(self, "split_action") and self.split_action.isChecked():
            viewer.set_compact_mode(True)
        viewer.message.connect(self.statusBar().showMessage)
        index = target_tabs.addTab(viewer, path.stem)
        target_tabs.setTabToolTip(index, str(path))
        target_tabs.setCurrentIndex(index)
        return viewer

    def close_tab(self, tabs, index):
        if tabs.widget(index) is self.welcome_page:
            return
        widget = tabs.widget(index)
        tabs.removeTab(index)
        if isinstance(widget, ViewerTab):
            widget.dispose()
        widget.deleteLater()

        if (
            self.split_action.isChecked()
            and tabs is self.tabs
            and not self._viewer_indices(self.tabs)
        ):
            self.split_action.setChecked(False)

    def dragEnterEvent(self, event):
        if _paths_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = _paths_from_mime(event.mimeData())
        if paths:
            self.open_paths(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        for tabs in (self.tabs, self.right_tabs):
            for index in range(tabs.count()):
                widget = tabs.widget(index)
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
QLabel#pathLabel { color: #7b8798; font-size: 13px; }
QFrame#sceneHost { background: #f5f7fb; border: 1px solid #d7dee9; border-radius: 8px; }
QFrame#sceneHost QToolBar { min-height: 32px; padding: 3px 4px; spacing: 2px; }
QFrame#sceneHost QToolBar QToolButton { min-width: 22px; max-width: 28px; min-height: 24px; max-height: 28px; padding: 1px 2px; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #e4eaf2; padding: 12px 20px; min-width: 72px; margin-right: 3px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:hover { background: #edf2f8; }
QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; font-weight: 600; }
QPushButton#paneMoveButton { padding: 6px 11px; min-height: 22px; margin: 3px 6px; color: #315783; }
QLabel#rightPaneLabel { color: #5c7290; font-weight: 600; padding: 8px 12px; }
ViewerTab[compact="true"] QPushButton#viewerActionButton { padding: 6px 9px; min-height: 22px; font-size: 14px; }
ViewerTab[compact="true"] QDoubleSpinBox, ViewerTab[compact="true"] QSpinBox { min-width: 58px; padding: 5px; }
QStatusBar { background: #ffffff; border-top: 1px solid #dfe5ee; color: #52627a; min-height: 28px; }
QDoubleSpinBox, QSpinBox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 7px; min-height: 24px; min-width: 72px; }
QCheckBox { spacing: 6px; padding: 2px 4px; }
QScrollBar:vertical { background: #edf1f6; width: 12px; margin: 2px; border-radius: 6px; }
QScrollBar::handle:vertical { background: #aebed2; min-height: 36px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def run(initial_files: Iterable[Path] = ()) -> int:
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GS Viewer")
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 11))
    app.setStyleSheet(STYLE)
    window = MainWindow(initial_files)
    window.show()
    return app.exec_()
