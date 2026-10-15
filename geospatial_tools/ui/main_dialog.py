"""
GeoSpatial Tools — Main Plugin Dialog.

Orchestrates location search, AOI management, layer selection,
map rendering, georeferencing, GeoTIFF creation, validation,
and automatic loading back into QGIS.
"""

import os
import traceback
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
    QgsWkbTypes,
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapTool,
    QgsMapToolEmitPoint,
    QgsRubberBand,
    QgsVertexMarker,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
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
from ..utils.compat import (
    MESSAGE_BOX_BUTTONS,
    POLYGON_GEOMETRY,
    QgsRubberBand,
)
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


class RectangleAOIMapTool(QgsMapTool):
    """Native canvas tool for drawing a rectangular AOI."""
    completed = pyqtSignal(object, object)

    def __init__(self, canvas, rubber_band):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = rubber_band
        self.start_point = None
        self.setCursor(Qt.CrossCursor)

    def canvasPressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.start_point = self.toMapCoordinates(event.pos())
        self.rubber_band.reset(POLYGON_GEOMETRY)
        self._draw(self.start_point, self.start_point)

    def canvasMoveEvent(self, event):
        if self.start_point is not None:
            self._draw(self.start_point, self.toMapCoordinates(event.pos()))

    def canvasReleaseEvent(self, event):
        if self.start_point is None or event.button() != Qt.LeftButton:
            return
        end_point = self.toMapCoordinates(event.pos())
        start = self.start_point
        self.start_point = None
        rect = QgsRectangle(start, end_point)
        if rect.width() <= 0 or rect.height() <= 0:
            self.rubber_band.reset(POLYGON_GEOMETRY)
            return
        self._draw(start, end_point)
        self.completed.emit(rect, self.canvas.mapSettings().destinationCrs())

    def _draw(self, first, second):
        rect = QgsRectangle(first, second)
        if rect.isEmpty():
            return
        self.rubber_band.setToGeometry(QgsGeometry.fromRect(rect), self.canvas.mapSettings().destinationCrs())
        self.rubber_band.show()


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
        self._location_marker: Optional[QgsVertexMarker] = None
        self._map_tool: Optional[QgsMapToolEmitPoint] = None
        self._previous_map_tool = None
        self._project_connections = []
        self._layer_name_connections = {}
        self._active_layer_ids = set()
        self._render_invalidated = False

        self.setWindowTitle(f"{PLUGIN_NAME} — Geospatial Raster Toolkit")
        self.resize(780, 850)

        self._setup_ui()
        self._connect_signals()
        self._connect_project_signals()

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
        help_row = QHBoxLayout()
        help_row.addStretch(1)
        self._btn_help = QPushButton("Help / How to Use")
        self._btn_help.setToolTip("Open the step-by-step guide for searching, selecting an AOI, and exporting.")
        help_row.addWidget(self._btn_help)
        content_layout.addLayout(help_row)

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
        self._widget_location.search_started.connect(self._clear_search_highlight)

        # AOI changed -> update export widget & canvas rubber band
        self._widget_aoi.aoi_changed.connect(self._on_aoi_changed)
        self._widget_aoi.draw_requested.connect(self._on_draw_aoi_requested)
        self._widget_layers.selection_changed.connect(self._update_generate_enabled)

        # Buttons
        self._btn_preview.clicked.connect(self._zoom_to_aoi)
        self._btn_help.clicked.connect(self._show_help)
        self._btn_generate.clicked.connect(self._on_generate_clicked)
        self._btn_close.clicked.connect(self.close)
        self._update_generate_enabled()

    def _connect_project_signals(self) -> None:
        if self._project_connections:
            return
        project = QgsProject.instance()
        connections = (
            (getattr(project, "layersWillBeRemoved", None), self._on_layers_will_be_removed),
            (getattr(project, "layersRemoved", None), self._on_layers_removed),
            (getattr(project, "layersAdded", None), self._on_layers_added),
            (getattr(project, "cleared", None), self._on_project_cleared),
        )
        root = project.layerTreeRoot()
        connections += (
            (getattr(root, "visibilityChanged", None), self._on_project_tree_changed),
            (getattr(root, "customOrderChanged", None), self._on_project_tree_changed),
            (getattr(root, "addedChildren", None), self._on_project_tree_changed),
            (getattr(root, "removedChildren", None), self._on_project_tree_changed),
        )
        for signal, handler in connections:
            if signal is not None:
                signal.connect(handler)
                self._project_connections.append((signal, handler))
        self._widget_location.connect_project_signals()
        self._refresh_layer_name_connections()

    def _disconnect_project_signals(self) -> None:
        for signal, handler in self._project_connections:
            signal.disconnect(handler)
        self._project_connections.clear()
        for layer_id in list(self._layer_name_connections):
            self._disconnect_layer_name_signal(layer_id)
        self._widget_location.disconnect_project_signals()

    def _refresh_layer_name_connections(self) -> None:
        project = QgsProject.instance()
        current_ids = set(project.mapLayers())
        for layer_id in set(self._layer_name_connections) - current_ids:
            self._disconnect_layer_name_signal(layer_id)
        for layer_id in current_ids - set(self._layer_name_connections):
            layer = project.mapLayer(layer_id)
            if layer is None or not layer.isValid():
                continue
            slot = lambda *_args: self._refresh_project_layers()
            layer.nameChanged.connect(slot)
            self._layer_name_connections[layer_id] = slot

    def _disconnect_layer_name_signal(self, layer_id: str) -> None:
        slot = self._layer_name_connections.pop(layer_id, None)
        layer = QgsProject.instance().mapLayer(layer_id)
        if slot is not None and layer is not None:
            layer.nameChanged.disconnect(slot)

    @staticmethod
    def _signal_layer_ids(args) -> set:
        layer_ids = set()
        for value in args:
            if isinstance(value, (list, tuple, set)):
                for layer in value:
                    layer_ids.add(layer.id() if hasattr(layer, "id") else str(layer))
            elif hasattr(value, "id"):
                layer_ids.add(value.id())
            elif isinstance(value, str):
                layer_ids.add(value)
        return layer_ids

    def _on_layers_will_be_removed(self, *args) -> None:
        layer_ids = self._signal_layer_ids(args)
        if not layer_ids:
            return
        self._widget_layers.layer_will_be_removed(layer_ids)
        self._widget_aoi.layer_removed(layer_ids)
        for layer_id in layer_ids:
            self._disconnect_layer_name_signal(layer_id)
        if self._active_layer_ids.intersection(layer_ids):
            self._render_invalidated = True
            self._renderer.cancel()

    def _on_layers_removed(self, *_args) -> None:
        self._refresh_project_layers()

    def _on_layers_added(self, *_args) -> None:
        self._refresh_project_layers()

    def _on_project_cleared(self, *_args) -> None:
        self._widget_aoi.clear_source_layer()
        self._refresh_project_layers()

    def _on_project_tree_changed(self, *_args) -> None:
        self._refresh_project_layers()

    def _refresh_project_layers(self) -> None:
        self._widget_layers.refresh_layers()
        self._widget_aoi.refresh_layers()
        self._refresh_layer_name_connections()
        self._update_generate_enabled()

    def _update_generate_enabled(self, *_args) -> None:
        if hasattr(self, "_btn_generate"):
            self._btn_generate.setEnabled(
                bool(self._widget_layers.get_selected_layer_ids())
                and not self._progress_bar.isVisible()
            )

    # ------------------------------------------------------------------
    # Location & AOI Slots
    # ------------------------------------------------------------------

    def _on_location_selected(self, result: GeocodingResult) -> None:
        try:
            logger.info(
                f"Location chosen: {result.display_name} "
                f"({result.latitude}, {result.longitude})"
            )
            pt = QgsPointXY(result.longitude, result.latitude)
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

            self._widget_aoi.set_center(pt, wgs84)
            self._widget_export.set_suggested_filename(
                result.name or result.display_name or "export"
            )

            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if result.bbox and len(result.bbox) == 4:
                south, north, west, east = result.bbox
                if east > west and north > south:
                    location_extent = QgsRectangle(west, south, east, north)
                else:
                    location_extent = QgsRectangle(
                        result.longitude - 0.001,
                        result.latitude - 0.001,
                        result.longitude + 0.001,
                        result.latitude + 0.001,
                    )
            else:
                location_extent = QgsRectangle(
                    result.longitude - 0.001,
                    result.latitude - 0.001,
                    result.longitude + 0.001,
                    result.latitude + 0.001,
                )
            center = location_extent.center()
            half_width = max(location_extent.width() * 0.6, 0.0005)
            half_height = max(location_extent.height() * 0.6, 0.0005)
            location_extent = QgsRectangle(
                center.x() - half_width,
                center.y() - half_height,
                center.x() + half_width,
                center.y() + half_height,
            )

            location_extent_canvas = transform_extent(
                location_extent, wgs84, canvas_crs
            )
            self.canvas.zoomToFeatureExtent(location_extent_canvas)
            self._update_rubber_band(location_extent, wgs84)
            self._update_location_marker(pt, wgs84)
            if self._location_marker is not None:
                self._location_marker.setToolTip(
                    "CFEES — Timarpur, Delhi" if result.provider_id == "local/cfees-timarpur"
                    else (result.name or result.display_name)
                )
            self.canvas.refresh()
        except Exception as exc:
            logger.error(
                f"Could not navigate to search result: {exc}\n{traceback.format_exc()}"
            )
            self._lbl_status.setText(f"Could not navigate to location: {exc}")

    def _update_location_marker(
        self,
        point: QgsPointXY,
        crs: QgsCoordinateReferenceSystem,
    ) -> None:
        if self._location_marker is None:
            self._location_marker = QgsVertexMarker(self.canvas)
            icon_types = getattr(QgsVertexMarker, "IconType", QgsVertexMarker)
            circle_icon = getattr(
                icon_types,
                "ICON_CIRCLE",
                getattr(QgsVertexMarker, "ICON_CIRCLE", 0),
            )
            self._location_marker.setIconType(circle_icon)
            self._location_marker.setIconSize(14)
            self._location_marker.setPenWidth(3)
            self._location_marker.setColor(QColor(0, 110, 70))
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        self._location_marker.setCenter(transform_point(point, crs, canvas_crs))
        self._location_marker.show()

    def _clear_search_highlight(self) -> None:
        self._clear_rubber_band()
        if self._location_marker is not None:
            self._location_marker.hide()

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
        """Activate a QGIS canvas drag tool and capture its rectangle."""
        self._ensure_aoi_rubber_band()
        if self._map_tool is not None:
            try:
                self._map_tool.completed.disconnect(self._on_rectangle_selected)
            except (TypeError, RuntimeError):
                pass
        self._map_tool = RectangleAOIMapTool(self.canvas, self._rubber_band)
        self._map_tool.completed.connect(self._on_rectangle_selected)
        self._previous_map_tool = self.canvas.mapTool()
        self.canvas.setMapTool(self._map_tool)
        self._lbl_status.setText("Drag on the map canvas to select an AOI.")

    def _on_rectangle_selected(self, extent, crs):
        self._widget_aoi.set_manual_extent(extent, crs)
        self._lbl_status.setText("AOI selected from the map canvas.")
        if self.canvas.mapTool() == self._map_tool and self._previous_map_tool is not None:
            self.canvas.setMapTool(self._previous_map_tool)
        self._map_tool = None

    def _ensure_aoi_rubber_band(self):
        if self._rubber_band is None:
            self._rubber_band = QgsRubberBand(self.canvas, POLYGON_GEOMETRY)
            self._rubber_band.setColor(QColor(255, 190, 0, 55))
            self._rubber_band.setStrokeColor(QColor(0, 0, 0, 240))
            self._rubber_band.setWidth(3)

    def _show_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("GeoSpatial Tools — Help / How to Use")
        dialog.resize(650, 600)
        layout = QVBoxLayout(dialog)
        guide = QLabel(
            "<h2>Getting Started</h2><p>This plugin runs inside QGIS and renders selected project layers "
            "within an AOI to a georeferenced GeoTIFF. Output pixel size controls the export grid; it does "
            "not improve the source imagery's actual spatial resolution.</p>"
            "<h3>1. Load Your Map</h3><p>Open or create a QGIS project, add permitted raster, vector, XYZ, WMS "
            "or WMTS layers, and confirm they render on the canvas. Connectivity, permissions, configuration "
            "or provider limits can prevent rendering. Check export rights for each source.</p>"
            "<h3>2. Find a Location</h3><p>Enter a name, address or latitude/longitude, search, review results, "
            "select the match and confirm its coordinates. Geocoding accuracy depends on address data; a locality "
            "match may not identify an exact building.</p>"
            "<h3>3. Select the Area</h3><p>Choose Draw rectangle on canvas, click Click &amp; Drag Extent on Map, then "
            "hold the left mouse button at one corner, drag to the opposite corner and release. Inspect the "
            "rectangle and dimensions. Press the Click & Drag Extent on Map button again to redraw, or choose another AOI method (radius, dimensions, canvas extent, "
            "or layer). Use a different AOI method to reset the selection.</p>"
            "<h3>4. Configure Export</h3><p>Select layers, output CRS, pixel size, filename and destination. Review "
            "estimated dimensions and size. Large areas or very small pixels need substantial memory and storage.</p>"
            "<h3>5. Generate the GeoTIFF</h3><p>Review AOI and settings, start generation, wait for rendering and "
            "validation, review messages, then confirm the loaded raster aligns with the original map.</p>"
            "<h3>Troubleshooting</h3><p>No search results: check spelling, connectivity, or enter coordinates. Wrong "
            "place: inspect alternatives or use coordinates. Drag does not start / rectangle invisible: activate "
            "Draw rectangle on canvas again and drag on the map canvas. Wrong dimensions or region: check the "
            "displayed CRS and redraw at the intended bounds. No layers: select at least one valid layer. Remote "
            "layers fail: check connection, credentials and provider limits. CRS missing/wrong: set an output CRS. "
            "Export fails or is slow: check destination permissions, reduce AOI or use a larger pixel size, and "
            "check available disk and memory.</p>"
        )
        guide.setWordWrap(True)
        guide.setTextFormat(Qt.RichText)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(guide)
        layout.addWidget(scroll)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.show()
        self._help_dialog = dialog

    def _zoom_to_aoi(self) -> None:
        aoi = self._widget_aoi.current_aoi()
        if not aoi or not aoi.extent:
            QMessageBox.warning(self, "No AOI", "Please define an Area of Interest first.")
            return

        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            extent_canvas = transform_extent(aoi.extent, aoi.crs, canvas_crs)
            self.canvas.setExtent(extent_canvas)
            self.canvas.refresh()
            self._update_rubber_band(aoi.extent, aoi.crs)
        except Exception as exc:
            logger.error(f"Could not zoom to AOI: {exc}\n{traceback.format_exc()}")
            self._lbl_status.setText(f"Could not zoom to AOI: {exc}")

    # ------------------------------------------------------------------
    # Rubber Band Visualization
    # ------------------------------------------------------------------

    def _update_rubber_band(
        self,
        extent: QgsRectangle,
        crs: QgsCoordinateReferenceSystem,
    ) -> None:
        if self._rubber_band is None:
            self._rubber_band = QgsRubberBand(self.canvas, POLYGON_GEOMETRY)
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
            try:
                self._rubber_band.reset(POLYGON_GEOMETRY)
            except TypeError:
                self._rubber_band.reset()
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
        layer_ids = [layer.id() for layer in layers]

        # 3. Output dimensions & safeguards
        w_px, h_px = self._widget_export.get_calculated_dimensions()
        out_crs = self._widget_export.get_output_crs()
        res_m = self._widget_export.get_resolution()
        out_path = os.path.normpath(self._widget_export.get_output_path())

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
                MESSAGE_BOX_BUTTONS.Yes | MESSAGE_BOX_BUTTONS.No,
                MESSAGE_BOX_BUTTONS.No,
            )
            if reply != MESSAGE_BOX_BUTTONS.Yes:
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
        try:
            render_extent = transform_extent(aoi.extent, aoi.crs, out_crs)
        except Exception as exc:
            logger.error(
                f"Could not transform AOI for rendering: {exc}\n{traceback.format_exc()}"
            )
            QMessageBox.critical(self, "CRS Transformation Failed", str(exc))
            return

        # 4. Prepare UI for execution
        self._set_ui_busy(True)
        self._active_layer_ids = set(layer_ids)
        self._render_invalidated = False
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

            if self._render_invalidated:
                raise RuntimeError("A selected layer was removed during rendering. Please retry.")

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

            try:
                val_res = self._validator.validate(
                    path=out_path,
                    expected=georef,
                    expected_bands=4 if write_opts.include_alpha else 3,
                )
            except Exception:
                if os.path.exists(out_path):
                    os.remove(out_path)
                raise

            if not val_res.valid:
                logger.warning(f"GeoTIFF Validation issues:\n{val_res.summary}")
                if os.path.exists(out_path):
                    os.remove(out_path)
                raise RuntimeError(
                    "GeoTIFF validation failed; the invalid output was removed.\n"
                    + "\n".join(val_res.errors)
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
            logger.error(f"{err_msg}\n{traceback.format_exc()}")
            self._lbl_status.setText("Error during generation.")
            QMessageBox.critical(self, "Export Failed", err_msg)
            self.iface.messageBar().pushCritical(PLUGIN_NAME, err_msg)

        finally:
            self._active_layer_ids.clear()
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
        self._btn_generate.setEnabled(
            not busy and bool(self._widget_layers.get_selected_layer_ids())
        )
        self._btn_preview.setEnabled(not busy)
        self._widget_location.setEnabled(not busy)
        self._widget_aoi.setEnabled(not busy)
        self._widget_layers.setEnabled(not busy)
        self._widget_export.setEnabled(not busy)

    def closeEvent(self, event) -> None:
        if self._map_tool is not None and self.canvas.mapTool() == self._map_tool:
            if self._previous_map_tool is not None:
                self.canvas.setMapTool(self._previous_map_tool)
            else:
                self.canvas.unsetMapTool(self._map_tool)
        self._map_tool = None
        self._widget_location.cancel_pending_requests()
        self._disconnect_project_signals()
        self._clear_rubber_band()
        if self._location_marker is not None:
            self._location_marker.hide()
            self.canvas.scene().removeItem(self._location_marker)
            self._location_marker = None
        if self._rubber_band is not None:
            self.canvas.scene().removeItem(self._rubber_band)
            self._rubber_band = None
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._connect_project_signals()
        self._refresh_project_layers()
