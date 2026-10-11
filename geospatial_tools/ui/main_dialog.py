"""
GeoSpatial Tools — Main Plugin Dialog.

Orchestrates location search, AOI management, layer selection,
map rendering, georeferencing, GeoTIFF creation, validation,
and automatic loading back into QGIS.
"""

import os
from typing import List, Optional

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsMapLayer,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsRubberBand,
    QgsWkbTypes,
)
from qgis.gui import QgsMapCanvas, QgsMapToolEmitPoint
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.aoi_manager import AOIResult
from ..core.crs_utils import transform_extent, transform_point
from ..core.geocoder import GeocodingResult
from ..core.georeferencing import build_georeference
from ..core.layer_manager import LayerManager
from ..core.raster_writer import RasterWriter
from ..core.renderer import MapRenderer, RenderRequest
from ..core.validation import GeoTiffValidator
from ..utils.constants import (
    MAX_ESTIMATED_MEMORY_BYTES,
    MAX_RASTER_DIMENSION,
    OUTPUT_GROUP_NAME,
    PLUGIN_NAME,
)
from ..utils.helpers import format_file_size
from ..utils.plugin_logger import get_logger
from .widgets.aoi_widget import AOIWidget
from .widgets.export_widget import ExportWidget
from .widgets.layer_selector import LayerSelectorWidget
from .widgets.location_widget import LocationWidget

logger = get_logger()


class MainDialog(QDialog):
    """
    Main dialog window for GeoSpatial Tools.
    """

    def __init__(self, iface, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self.canvas: QgsMapCanvas = iface.mapCanvas()

        self._renderer = MapRenderer()
        self._writer = RasterWriter()
        self._validator = GeoTiffValidator()
        self._layer_mgr = LayerManager()

        # Canvas visualization rubber band
        self._rubber_band: Optional[QgsRubberBand] = None
        self._map_tool: Optional[QgsMapToolEmitPoint] = None

        self.setWindowTitle(f"{PLUGIN_NAME} — Geospatial Raster Toolkit")
        self.resize(780, 850)

        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Scroll area to handle smaller monitor screens smoothly
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        content_layout = QVBoxLayout(container)

        # 1. Location search widget
        self._widget_location = LocationWidget()
        content_layout.addWidget(self._widget_location)

        # 2. AOI widget
        self._widget_aoi = AOIWidget()
        content_layout.addWidget(self._widget_aoi)

        # 3. Layer selector widget
        self._widget_layers = LayerSelectorWidget()
        content_layout.addWidget(self._widget_layers)

        # 4. Export configuration widget
        self._widget_export = ExportWidget()
        content_layout.addWidget(self._widget_export)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)

        # Status label
        self._lbl_status = QLabel("Ready.")
        self._lbl_status.setStyleSheet("font-weight: bold; color: #333;")
        main_layout.addWidget(self._lbl_status)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self._btn_preview = QPushButton("Preview AOI on Canvas")
        self._btn_generate = QPushButton("GENERATE GEOTIFF")
        self._btn_generate.setStyleSheet(
            "background-color: #2b78e4; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;"
        )
        self._btn_close = QPushButton("Close")

        btn_layout.addWidget(self._btn_preview)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self._btn_generate)
        btn_layout.addWidget(self._btn_close)
        main_layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        # Location selected -> feed AOI widget & zoom canvas
        self._widget_location.location_selected.connect(self._on_location_selected)

        # AOI changed -> update export widget & canvas rubber band
        self._widget_aoi.aoi_changed.connect(self._on_aoi_changed)
        self._widget_aoi.draw_requested.connect(self._on_draw_aoi_requested)

        # Buttons
        self._btn_preview.clicked.connect(self._zoom_to_aoi)
        self._btn_generate.clicked.connect(self._on_generate_clicked)
        self._btn_close.clicked.connect(self.close)

    # ------------------------------------------------------------------
    # Location & AOI Slots
    # ------------------------------------------------------------------

    def _on_location_selected(self, result: GeocodingResult) -> None:
        logger.info(f"Location chosen: {result.display_name} ({result.latitude}, {result.longitude})")
        pt = QgsPointXY(result.longitude, result.latitude)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

        # Update AOI widget center
        self._widget_aoi.set_center(pt, wgs84)

        # Update export suggested filename
        self._widget_export.set_suggested_filename(result.display_name or "export")

        # Zoom canvas to location
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        center_canvas = transform_point(pt, wgs84, canvas_crs)
        self.canvas.setCenter(center_canvas)
        self.canvas.refresh()

    def _on_aoi_changed(self, aoi: AOIResult) -> None:
        if not aoi.success or aoi.extent is None:
            self._clear_rubber_band()
            return

        self._widget_export.set_aoi_dimensions(
            width_m=aoi.width_m,
            height_m=aoi.height_m,
            extent=aoi.extent,
            suggested_crs=aoi.crs,
        )

        self._update_rubber_band(aoi.extent, aoi.crs)

    def _on_draw_aoi_requested(self) -> None:
        """Capture canvas extent as AOI."""
        canvas_ext = self.canvas.extent()
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        self._widget_aoi.set_manual_extent(canvas_ext, canvas_crs)
        self._lbl_status.setText("Captured current map canvas extent as AOI.")

    def _zoom_to_aoi(self) -> None:
        aoi = self._widget_aoi.current_aoi()
        if not aoi or not aoi.extent:
            QMessageBox.warning(self, "No AOI", "Please define an Area of Interest first.")
            return

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        extent_canvas = transform_extent(aoi.extent, aoi.crs, canvas_crs)
        self.canvas.setExtent(extent_canvas)
        self.canvas.refresh()
        self._update_rubber_band(aoi.extent, aoi.crs)

    # ------------------------------------------------------------------
    # Rubber Band Visualization
    # ------------------------------------------------------------------

    def _update_rubber_band(
        self,
        extent: QgsRectangle,
        crs: QgsCoordinateReferenceSystem,
    ) -> None:
        if self._rubber_band is None:
            self._rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
            self._rubber_band.setColor(QColor(255, 68, 68, 60))
            self._rubber_band.setStrokeColor(QColor(255, 0, 0, 220))
            self._rubber_band.setWidth(2)

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        extent_canvas = transform_extent(extent, crs, canvas_crs)
        geom = QgsGeometry.fromRect(extent_canvas)
        self._rubber_band.setToGeometry(geom, None)
        self._rubber_band.show()

    def _clear_rubber_band(self) -> None:
        if self._rubber_band:
            self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self._rubber_band.hide()

    # ------------------------------------------------------------------
    # Export / Generation Pipeline
    # ------------------------------------------------------------------

    def _on_generate_clicked(self) -> None:
        # 1. Validate AOI
        aoi = self._widget_aoi.current_aoi()
        if not aoi or not aoi.extent or aoi.extent.isEmpty():
            QMessageBox.critical(self, "Validation Error", "Invalid or missing Area of Interest (AOI).")
            return

        # 2. Validate layers
        layer_ids = self._widget_layers.get_selected_layer_ids()
        if not layer_ids:
            QMessageBox.critical(self, "Validation Error", "Please select at least one layer to render.")
            return

        layers = self._layer_mgr.get_layers_by_ids(layer_ids)
        if not layers:
            QMessageBox.critical(self, "Validation Error", "None of the selected layers are currently valid.")
            return

        # 3. Output dimensions & safeguards
        w_px, h_px = self._widget_export.get_calculated_dimensions()
        out_crs = self._widget_export.get_output_crs()
        res_m = self._widget_export.get_resolution()
        out_path = self._widget_export.get_output_path()

        if w_px > MAX_RASTER_DIMENSION or h_px > MAX_RASTER_DIMENSION:
            msg = (
                f"Requested raster dimensions ({w_px:,} × {h_px:,}) exceed the "
                f"maximum limit of {MAX_RASTER_DIMENSION:,} pixels per axis.\n"
                f"Please increase resolution (larger m/pixel) or reduce AOI."
            )
            QMessageBox.critical(self, "Resolution Too Fine", msg)
            return

        mem_bytes = w_px * h_px * 4
        if mem_bytes > MAX_ESTIMATED_MEMORY_BYTES:
            reply = QMessageBox.question(
                self,
                "Large Export Warning",
                f"Estimated uncompressed image size is ~{format_file_size(mem_bytes)}.\n"
                f"Rendering this raster may consume significant RAM.\n\n"
                f"Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        # Ensure directory is writable
        out_dir = os.path.dirname(out_path) or "."
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Path Error", f"Cannot create directory '{out_dir}': {e}")
                return

        # Transform AOI extent to output CRS if needed
        render_extent = transform_extent(aoi.extent, aoi.crs, out_crs)

        # 4. Prepare UI for execution
        self._set_ui_busy(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(10)
        self._lbl_status.setText("Initializing map render settings…")
        self.repaint()

        try:
            # 5. Render Map via QgsMapRendererParallelJob
            self._lbl_status.setText(f"Rendering {len(layers)} layer(s) at {w_px}×{h_px} px…")
            self._progress_bar.setValue(30)

            render_req = RenderRequest(
                extent=render_extent,
                layers=layers,
                crs=out_crs,
                width=w_px,
                height=h_px,
            )

            render_res = self._renderer.render(
                render_req,
                on_progress=lambda msg: self._lbl_status.setText(msg),
            )

            if not render_res.success or render_res.image is None:
                raise RuntimeError(render_res.error_message or "Map rendering failed.")

            self._progress_bar.setValue(60)
            self._lbl_status.setText("Building georeference & affine transform…")

            # 6. Build Affine Georeference
            georef = build_georeference(
                extent=render_extent,
                crs=out_crs,
                width=render_res.width,
                height=render_res.height,
            )

            # 7. Write GeoTIFF
            self._progress_bar.setValue(75)
            self._lbl_status.setText("Writing GeoTIFF with GDAL…")

            write_opts = self._widget_export.get_write_options()
            write_res = self._writer.write(
                image=render_res.image,
                georef=georef,
                output_path=out_path,
                options=write_opts,
            )

            if not write_res.success:
                raise RuntimeError(write_res.error_message)

            # 8. Post-export GeoTIFF validation
            self._progress_bar.setValue(90)
            self._lbl_status.setText("Validating generated GeoTIFF…")

            val_res = self._validator.validate(
                path=out_path,
                expected=georef,
                expected_bands=4 if write_opts.include_alpha else 3,
            )

            if not val_res.valid:
                logger.warning(f"GeoTIFF Validation issues:\n{val_res.summary}")
                QMessageBox.warning(
                    self,
                    "Validation Issues",
                    f"GeoTIFF was generated but validation encountered warnings:\n"
                    + "\n".join(val_res.errors),
                )

            # 9. Add layer to QGIS
            if self._widget_export.should_add_to_qgis():
                self._progress_bar.setValue(95)
                self._lbl_status.setText("Adding GeoTIFF to QGIS project…")
                self._add_raster_to_qgis(out_path, render_extent)

            self._progress_bar.setValue(100)
            success_msg = f"Export completed successfully: {os.path.basename(out_path)} ({format_file_size(write_res.file_size_bytes)})"
            self._lbl_status.setText(success_msg)
            self.iface.messageBar().pushSuccess(PLUGIN_NAME, success_msg)

            QMessageBox.information(
                self,
                "Export Complete",
                f"GeoTIFF generated successfully!\n\n"
                f"File: {out_path}\n"
                f"Dimensions: {w_px} × {h_px}\n"
                f"File size: {format_file_size(write_res.file_size_bytes)}\n"
                f"CRS: {out_crs.authid()}\n\n"
                f"{val_res.summary}",
            )

        except Exception as exc:
            err_msg = f"Generation failed: {exc}"
            logger.error(err_msg)
            self._lbl_status.setText("Error during generation.")
            QMessageBox.critical(self, "Export Failed", err_msg)
            self.iface.messageBar().pushCritical(PLUGIN_NAME, err_msg)

        finally:
            self._set_ui_busy(False)
            self._progress_bar.setVisible(False)

    def _add_raster_to_qgis(self, file_path: str, extent: QgsRectangle) -> None:
        """Create QgsRasterLayer, add to dedicated group, and zoom canvas."""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        layer = QgsRasterLayer(file_path, f"{base_name} [GeoTIFF]")

        if not layer.isValid():
            logger.error(f"Failed to load generated GeoTIFF: {file_path}")
            return

        project = QgsProject.instance()

        # Place in dedicated layer group
        root = project.layerTreeRoot()
        group = root.findGroup(OUTPUT_GROUP_NAME)
        if group is None:
            group = root.insertGroup(0, OUTPUT_GROUP_NAME)

        # Add layer without auto-inserting at root
        project.addMapLayer(layer, False)
        group.insertChildNode(0, project.layerTreeRoot().findLayer(layer.id()) or group.addLayer(layer))

        # Zoom canvas to new layer extent
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        ext_canvas = transform_extent(extent, layer.crs(), canvas_crs)
        self.canvas.setExtent(ext_canvas)
        self.canvas.refresh()

    def _set_ui_busy(self, busy: bool) -> None:
        self._btn_generate.setEnabled(not busy)
        self._btn_preview.setEnabled(not busy)
        self._widget_location.setEnabled(not busy)
        self._widget_aoi.setEnabled(not busy)
        self._widget_layers.setEnabled(not busy)
        self._widget_export.setEnabled(not busy)

    def closeEvent(self, event) -> None:
        self._clear_rubber_band()
        super().closeEvent(event)
