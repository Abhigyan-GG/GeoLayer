"""
GeoSpatial Tools — AOI Widget.

User interface for configuring the Area of Interest (AOI):
- Radius around point
- Rectangle (width × height) around point
- Current map canvas extent
- Draw rectangle on canvas
- From existing layer extent

All distance calculations use projected CRS via AOIManager.
"""

from typing import Optional

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsMapLayer,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.aoi_manager import AOIManager, AOIMethod, AOIParameters, AOIResult
from ...core.crs_utils import crs_to_string
from ...utils.constants import (
    DEFAULT_AOI_HEIGHT_M,
    DEFAULT_AOI_RADIUS_M,
    DEFAULT_AOI_WIDTH_M,
)
from ...utils.plugin_logger import get_logger

logger = get_logger()


class AOIWidget(QGroupBox):
    """
    Area of Interest (AOI) selection widget.

    Signals:
        aoi_changed(AOIResult): Emitted whenever the computed AOI changes.
        draw_requested(): Emitted when the user wants to draw an AOI on the map canvas.
    """

    aoi_changed = pyqtSignal(object)  # AOIResult
    draw_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Area of Interest (AOI)", parent)
        self._manager = AOIManager()
        self._center: Optional[QgsPointXY] = None
        self._center_crs: Optional[QgsCoordinateReferenceSystem] = None
        self._manual_extent: Optional[QgsRectangle] = None
        self._manual_extent_crs: Optional[QgsCoordinateReferenceSystem] = None
        self._current_aoi: Optional[AOIResult] = None

        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Method selection (Radio buttons)
        method_group = QGroupBox("Definition Method")
        method_layout = QVBoxLayout(method_group)

        self._btn_group = QButtonGroup(self)

        self._radio_radius = QRadioButton("Radius around point")
        self._radio_rectangle = QRadioButton("Width × Height rectangle")
        self._radio_canvas = QRadioButton("Current map canvas extent")
        self._radio_draw = QRadioButton("Draw rectangle on canvas")
        self._radio_layer = QRadioButton("From existing layer")

        self._radio_radius.setChecked(True)

        self._btn_group.addButton(self._radio_radius, 0)
        self._btn_group.addButton(self._radio_rectangle, 1)
        self._btn_group.addButton(self._radio_canvas, 2)
        self._btn_group.addButton(self._radio_draw, 3)
        self._btn_group.addButton(self._radio_layer, 4)

        method_layout.addWidget(self._radio_radius)
        method_layout.addWidget(self._radio_rectangle)
        method_layout.addWidget(self._radio_canvas)
        method_layout.addWidget(self._radio_draw)
        method_layout.addWidget(self._radio_layer)
        layout.addWidget(method_group)

        # Parameter Stacked Pages
        self._param_stack = QStackedWidget()

        # Page 0: Radius
        page_radius = QWidget()
        layout_radius = QFormLayout(page_radius)
        self._spin_radius = QDoubleSpinBox()
        self._spin_radius.setRange(10.0, 500_000.0)
        self._spin_radius.setValue(DEFAULT_AOI_RADIUS_M)
        self._spin_radius.setSingleStep(50.0)
        self._spin_radius.setSuffix(" m")
        layout_radius.addRow("Radius:", self._spin_radius)
        self._param_stack.addWidget(page_radius)

        # Page 1: Rectangle
        page_rect = QWidget()
        layout_rect = QFormLayout(page_rect)
        self._spin_width = QDoubleSpinBox()
        self._spin_width.setRange(10.0, 1_000_000.0)
        self._spin_width.setValue(DEFAULT_AOI_WIDTH_M)
        self._spin_width.setSingleStep(100.0)
        self._spin_width.setSuffix(" m")

        self._spin_height = QDoubleSpinBox()
        self._spin_height.setRange(10.0, 1_000_000.0)
        self._spin_height.setValue(DEFAULT_AOI_HEIGHT_M)
        self._spin_height.setSingleStep(100.0)
        self._spin_height.setSuffix(" m")

        layout_rect.addRow("Width:", self._spin_width)
        layout_rect.addRow("Height:", self._spin_height)
        self._param_stack.addWidget(page_rect)

        # Page 2: Current Canvas
        page_canvas = QWidget()
        layout_canvas = QVBoxLayout(page_canvas)
        self._btn_refresh_canvas = QPushButton("Capture Current Canvas Extent")
        layout_canvas.addWidget(self._btn_refresh_canvas)
        self._param_stack.addWidget(page_canvas)

        # Page 3: Draw on canvas
        page_draw = QWidget()
        layout_draw = QVBoxLayout(page_draw)
        self._btn_start_draw = QPushButton("Click & Drag Extent on Map")
        layout_draw.addWidget(self._btn_start_draw)
        self._param_stack.addWidget(page_draw)

        # Page 4: Layer extent
        page_layer = QWidget()
        layout_layer = QFormLayout(page_layer)
        self._combo_layers = QComboBox()
        self._btn_refresh_layers = QPushButton("↻ Refresh Layers")
        row_layer = QHBoxLayout()
        row_layer.addWidget(self._combo_layers, stretch=1)
        row_layer.addWidget(self._btn_refresh_layers)
        layout_layer.addRow("Layer:", row_layer)
        self._param_stack.addWidget(page_layer)

        layout.addWidget(self._param_stack)

        # Summary Display Group
        summary_group = QGroupBox("AOI Summary")
        summary_layout = QFormLayout(summary_group)

        self._lbl_extent = QLabel("—")
        self._lbl_extent.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._lbl_extent.setWordWrap(True)

        self._lbl_dims = QLabel("—")
        self._lbl_crs = QLabel("—")

        summary_layout.addRow("Extent:", self._lbl_extent)
        summary_layout.addRow("Size:", self._lbl_dims)
        summary_layout.addRow("CRS:", self._lbl_crs)
        layout.addWidget(summary_group)

        self._populate_layers()

    def _connect_signals(self) -> None:
        self._btn_group.buttonClicked.connect(self._on_method_changed)
        self._spin_radius.valueChanged.connect(self._recalculate_aoi)
        self._spin_width.valueChanged.connect(self._recalculate_aoi)
        self._spin_height.valueChanged.connect(self._recalculate_aoi)
        self._btn_refresh_canvas.clicked.connect(self._on_capture_canvas_clicked)
        self._btn_start_draw.clicked.connect(self.draw_requested.emit)
        self._combo_layers.currentIndexChanged.connect(self._recalculate_aoi)
        self._btn_refresh_layers.clicked.connect(self._populate_layers)

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def set_center(
        self,
        center: QgsPointXY,
        crs: Optional[QgsCoordinateReferenceSystem] = None,
    ) -> None:
        """Set or update the centre point (e.g. from location search)."""
        self._center = center
        self._center_crs = crs or QgsCoordinateReferenceSystem("EPSG:4326")
        self._recalculate_aoi()

    def set_manual_extent(
        self,
        extent: QgsRectangle,
        crs: Optional[QgsCoordinateReferenceSystem] = None,
    ) -> None:
        """Set an extent acquired from map canvas or interactive drawing."""
        self._manual_extent = extent
        self._manual_extent_crs = crs or QgsProject.instance().crs()
        self._recalculate_aoi()

    def current_aoi(self) -> Optional[AOIResult]:
        """Return the current computed AOIResult."""
        return self._current_aoi

    # ------------------------------------------------------------------
    # Internal Slots & Calculations
    # ------------------------------------------------------------------

    def _on_method_changed(self) -> None:
        idx = self._btn_group.checkedId()
        self._param_stack.setCurrentIndex(idx)
        self._recalculate_aoi()

    def _on_capture_canvas_clicked(self) -> None:
        # Request external canvas capture
        self.draw_requested.emit()

    def _populate_layers(self) -> None:
        self._combo_layers.clear()
        for layer_id, layer in QgsProject.instance().mapLayers().items():
            if layer.isValid() and not layer.extent().isEmpty():
                self._combo_layers.addItem(layer.name(), layer_id)

    def _recalculate_aoi(self) -> None:
        method_id = self._btn_group.checkedId()

        if method_id == 0:  # Radius
            if self._center is None:
                self._update_display_none("Awaiting centre location/coordinates.")
                return
            params = AOIParameters(
                method=AOIMethod.RADIUS,
                center=self._center,
                center_crs=self._center_crs,
                radius_m=self._spin_radius.value(),
            )

        elif method_id == 1:  # Rectangle
            if self._center is None:
                self._update_display_none("Awaiting centre location/coordinates.")
                return
            params = AOIParameters(
                method=AOIMethod.RECTANGLE,
                center=self._center,
                center_crs=self._center_crs,
                width_m=self._spin_width.value(),
                height_m=self._spin_height.value(),
            )

        elif method_id in (2, 3):  # Canvas Extent or Draw
            if self._manual_extent is None:
                self._update_display_none("Extent not yet captured from map canvas.")
                return
            params = AOIParameters(
                method=AOIMethod.CURRENT_EXTENT if method_id == 2 else AOIMethod.DRAW_ON_MAP,
                manual_extent=self._manual_extent,
                manual_extent_crs=self._manual_extent_crs,
            )

        elif method_id == 4:  # Layer
            layer_id = self._combo_layers.currentData()
            layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None
            if layer is None:
                self._update_display_none("No valid layer selected.")
                return
            params = AOIParameters(
                method=AOIMethod.FROM_LAYER,
                layer=layer,
            )
        else:
            return

        result = self._manager.create_aoi(params)
        self._current_aoi = result

        if result.success and result.extent:
            ext = result.extent
            self._lbl_extent.setText(
                f"[{ext.xMinimum():.2f}, {ext.yMinimum():.2f}] → "
                f"[{ext.xMaximum():.2f}, {ext.yMaximum():.2f}]"
            )
            self._lbl_dims.setText(f"{result.width_m:.1f} m × {result.height_m:.1f} m")
            self._lbl_crs.setText(crs_to_string(result.crs) if result.crs else "—")
            self.aoi_changed.emit(result)
        else:
            self._update_display_none(result.error_message or "Failed to compute AOI.")

    def _update_display_none(self, message: str) -> None:
        self._lbl_extent.setText(message)
        self._lbl_dims.setText("—")
        self._lbl_crs.setText("—")
        self._current_aoi = None
