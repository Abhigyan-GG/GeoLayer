"""
GeoSpatial Tools — Export Configuration Widget.

Configures:
- Spatial resolution (m/pixel)
- Output CRS
- Output raster dimensions & estimated memory
- Compression and tiling options
- Destination file path
- Post-export actions (add to QGIS project)
"""

import os
from typing import Optional, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.crs_utils import crs_to_string, get_project_crs
from ...core.raster_writer import WriteOptions
from ...utils.constants import (
    COMPRESSION_OPTIONS,
    DEFAULT_COMPRESSION,
    DEFAULT_RESOLUTION_M,
    DEFAULT_TILED,
    MAX_ESTIMATED_MEMORY_BYTES,
    MAX_RASTER_DIMENSION,
    MIN_RESOLUTION_M,
)
from ...utils.helpers import (
    compute_pixel_dimensions,
    default_output_path,
    estimate_output_size,
    estimate_raster_memory,
    format_file_size,
)
from ...utils.plugin_logger import get_logger

logger = get_logger()


class ExportWidget(QGroupBox):
    """
    Configuration widget for GeoTIFF generation parameters.

    Signals:
        parameters_changed(): Emitted when resolution, CRS, or output options change.
    """

    parameters_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Export & GeoTIFF Settings", parent)
        self._aoi_width_m: float = 1000.0
        self._aoi_height_m: float = 1000.0
        self._extent: Optional[QgsRectangle] = None
        self._selected_crs: QgsCoordinateReferenceSystem = get_project_crs()

        self._setup_ui()
        self._connect_signals()
        self._update_estimates()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Resolution (m/px)
        row_res = QHBoxLayout()
        self._spin_resolution = QDoubleSpinBox()
        self._spin_resolution.setRange(MIN_RESOLUTION_M, 10000.0)
        self._spin_resolution.setDecimals(3)
        self._spin_resolution.setSingleStep(0.5)
        self._spin_resolution.setValue(DEFAULT_RESOLUTION_M)
        self._spin_resolution.setSuffix(" m/pixel")
        row_res.addWidget(self._spin_resolution, stretch=1)

        # Quick preset combo
        self._combo_presets = QComboBox()
        self._combo_presets.addItem("Presets…", None)
        self._combo_presets.addItem("0.10 m (Ultra High)", 0.10)
        self._combo_presets.addItem("0.25 m (High Detail)", 0.25)
        self._combo_presets.addItem("0.50 m (Standard)", 0.50)
        self._combo_presets.addItem("1.00 m (Overview)", 1.00)
        self._combo_presets.addItem("2.00 m (Fast/Low)", 2.00)
        self._combo_presets.addItem("10.0 m (Regional)", 10.0)
        row_res.addWidget(self._combo_presets)

        form.addRow("Spatial Resolution:", row_res)

        # Output CRS Combo
        self._combo_crs = QComboBox()
        self._populate_crs_options()
        form.addRow("Output CRS:", self._combo_crs)

        # Compression Combo
        self._combo_compression = QComboBox()
        self._combo_compression.addItems(COMPRESSION_OPTIONS)
        self._combo_compression.setCurrentText(DEFAULT_COMPRESSION)
        form.addRow("Compression:", self._combo_compression)

        # Tiling & Alpha Options
        row_opts = QHBoxLayout()
        self._chk_tiled = QCheckBox("Tiled Storage")
        self._chk_tiled.setChecked(DEFAULT_TILED)
        self._chk_alpha = QCheckBox("Include Alpha (Transparency)")
        self._chk_alpha.setChecked(False)
        row_opts.addWidget(self._chk_tiled)
        row_opts.addWidget(self._chk_alpha)
        row_opts.addStretch(1)
        form.addRow("Storage Options:", row_opts)

        # Destination File Path
        row_path = QHBoxLayout()
        self._txt_output_path = QLineEdit(default_output_path("geospatial_export"))
        self._btn_browse = QPushButton("Browse…")
        row_path.addWidget(self._txt_output_path, stretch=1)
        row_path.addWidget(self._btn_browse)
        form.addRow("Output File:", row_path)

        # Post-export Options
        self._chk_add_to_qgis = QCheckBox("Add generated GeoTIFF to QGIS map canvas")
        self._chk_add_to_qgis.setChecked(True)
        form.addRow("", self._chk_add_to_qgis)

        layout.addLayout(form)

        # Estimates Box
        est_box = QGroupBox("Calculated Raster Dimensions & Resource Estimates")
        est_layout = QFormLayout(est_box)

        self._lbl_dimensions = QLabel("—")
        self._lbl_pixel_count = QLabel("—")
        self._lbl_memory_est = QLabel("—")
        self._lbl_file_est = QLabel("—")
        self._lbl_warning = QLabel("")
        self._lbl_warning.setStyleSheet("color: #d9534f; font-weight: bold;")
        self._lbl_warning.setVisible(False)

        est_layout.addRow("Raster Size:", self._lbl_dimensions)
        est_layout.addRow("Total Pixels:", self._lbl_pixel_count)
        est_layout.addRow("Estimated RAM:", self._lbl_memory_est)
        est_layout.addRow("Estimated File Size:", self._lbl_file_est)
        est_layout.addRow("", self._lbl_warning)

        layout.addWidget(est_box)

    def _connect_signals(self) -> None:
        self._spin_resolution.valueChanged.connect(self._on_resolution_changed)
        self._combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        self._combo_crs.currentIndexChanged.connect(self._on_crs_changed)
        self._combo_compression.currentIndexChanged.connect(self.parameters_changed.emit)
        self._chk_tiled.toggled.connect(self.parameters_changed.emit)
        self._chk_alpha.toggled.connect(self._update_estimates)
        self._btn_browse.clicked.connect(self._on_browse_file)
        self._txt_output_path.textChanged.connect(self.parameters_changed.emit)

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def set_aoi_dimensions(
        self,
        width_m: float,
        height_m: float,
        extent: Optional[QgsRectangle] = None,
        suggested_crs: Optional[QgsCoordinateReferenceSystem] = None,
    ) -> None:
        """Update AOI metrics to refresh pixel dimensions and memory calculation."""
        self._aoi_width_m = max(1.0, width_m)
        self._aoi_height_m = max(1.0, height_m)
        self._extent = extent

        if suggested_crs and suggested_crs.isValid():
            self._add_or_select_crs(suggested_crs)

        self._update_estimates()

    def get_resolution(self) -> float:
        """Return the current user-selected resolution in metres per pixel."""
        return self._spin_resolution.value()

    def get_output_crs(self) -> QgsCoordinateReferenceSystem:
        """Return the chosen output CRS."""
        data = self._combo_crs.currentData()
        if isinstance(data, QgsCoordinateReferenceSystem) and data.isValid():
            return data
        return get_project_crs()

    def get_output_path(self) -> str:
        """Return absolute path to output file."""
        return os.path.normpath(self._txt_output_path.text().strip())

    def set_suggested_filename(self, name: str) -> None:
        """Update suggested filename based on location name."""
        curr_dir = os.path.dirname(self.get_output_path()) or os.path.expanduser("~")
        self._txt_output_path.setText(default_output_path(name, curr_dir))

    def should_add_to_qgis(self) -> bool:
        """Return whether user checked 'Add to QGIS'."""
        return self._chk_add_to_qgis.isChecked()

    def get_write_options(self) -> WriteOptions:
        """Build WriteOptions instance from widget settings."""
        return WriteOptions(
            compression=self._combo_compression.currentText(),
            tiled=self._chk_tiled.isChecked(),
            include_alpha=self._chk_alpha.isChecked(),
        )

    def get_calculated_dimensions(self) -> Tuple[int, int]:
        """Return (width_px, height_px)."""
        res = self.get_resolution()
        return compute_pixel_dimensions(self._aoi_width_m, self._aoi_height_m, res)

    # ------------------------------------------------------------------
    # Internal Slots & Logic
    # ------------------------------------------------------------------

    def _populate_crs_options(self) -> None:
        self._combo_crs.clear()
        proj_crs = get_project_crs()
        self._combo_crs.addItem(f"Project CRS ({crs_to_string(proj_crs)})", proj_crs)

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if wgs84.isValid() and wgs84 != proj_crs:
            self._combo_crs.addItem(f"WGS 84 ({crs_to_string(wgs84)})", wgs84)

        web_merc = QgsCoordinateReferenceSystem("EPSG:3857")
        if web_merc.isValid() and web_merc != proj_crs:
            self._combo_crs.addItem(f"WGS 84 / Pseudo-Mercator ({crs_to_string(web_merc)})", web_merc)

    def _add_or_select_crs(self, crs: QgsCoordinateReferenceSystem) -> None:
        for idx in range(self._combo_crs.count()):
            item_crs = self._combo_crs.itemData(idx)
            if item_crs == crs:
                self._combo_crs.setCurrentIndex(idx)
                return
        # Add new entry
        label = f"Suggested: {crs_to_string(crs)}"
        self._combo_crs.addItem(label, crs)
        self._combo_crs.setCurrentIndex(self._combo_crs.count() - 1)

    def _on_resolution_changed(self) -> None:
        self._combo_presets.blockSignals(True)
        self._combo_presets.setCurrentIndex(0)
        self._combo_presets.blockSignals(False)
        self._update_estimates()
        self.parameters_changed.emit()

    def _on_preset_selected(self, index: int) -> None:
        val = self._combo_presets.itemData(index)
        if val is not None:
            self._spin_resolution.blockSignals(True)
            self._spin_resolution.setValue(float(val))
            self._spin_resolution.blockSignals(False)
            self._update_estimates()
            self.parameters_changed.emit()

    def _on_crs_changed(self) -> None:
        self._selected_crs = self.get_output_crs()
        self._update_estimates()
        self.parameters_changed.emit()

    def _on_browse_file(self) -> None:
        curr = self.get_output_path()
        init_dir = os.path.dirname(curr) if curr else os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Output GeoTIFF",
            curr or init_dir,
            "GeoTIFF Files (*.tif *.tiff);;All Files (*)",
        )
        if path:
            path = os.path.normpath(path)
            if not (path.lower().endswith(".tif") or path.lower().endswith(".tiff")):
                path += ".tif"
            self._txt_output_path.setText(path)

    def _update_estimates(self) -> None:
        w_px, h_px = self.get_calculated_dimensions()
        total_pixels = w_px * h_px
        bands = 4 if self._chk_alpha.isChecked() else 3

        mem_bytes = estimate_raster_memory(w_px, h_px, bands)
        file_bytes = estimate_output_size(w_px, h_px, bands)

        self._lbl_dimensions.setText(f"{w_px:,} × {h_px:,} pixels")
        self._lbl_pixel_count.setText(f"{total_pixels / 1_000_000:.2f} Megapixels")
        self._lbl_memory_est.setText(f"~{format_file_size(mem_bytes)}")
        self._lbl_file_est.setText(f"~{format_file_size(file_bytes)} (compressed)")

        # Safeguards
        warning_msgs = []
        if w_px > MAX_RASTER_DIMENSION or h_px > MAX_RASTER_DIMENSION:
            warning_msgs.append(f"Dimension exceeds {MAX_RASTER_DIMENSION:,} px limit!")
        if mem_bytes > MAX_ESTIMATED_MEMORY_BYTES:
            warning_msgs.append(f"High RAM usage (> {format_file_size(MAX_ESTIMATED_MEMORY_BYTES)}).")

        if warning_msgs:
            self._lbl_warning.setText("⚠️ " + " ".join(warning_msgs))
            self._lbl_warning.setVisible(True)
        else:
            self._lbl_warning.setVisible(False)
