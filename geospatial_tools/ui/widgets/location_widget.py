"""
GeoSpatial Tools — Location Search Widget.

Provides a search bar for entering addresses / place names / coordinates,
displays results, and emits signals when a location is selected.
"""

import traceback
from typing import Optional

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.data_points import DataPointsManager
from ...core.geocoder import GeocodingResult, NominatimGeocoder, parse_coordinates
from ...utils.compat import TEXT_SELECTABLE_BY_MOUSE
from ...utils.plugin_logger import get_logger

logger = get_logger()


class _GeocodeSignals(QObject):
    completed = pyqtSignal(int, object, str, bool)


class _GeocodeTask(QRunnable):
    def __init__(self, geocoder, token: int, query: str, reverse: bool) -> None:
        super().__init__()
        self.geocoder = geocoder
        self.token = token
        self.query = query
        self.reverse = reverse
        self.signals = _GeocodeSignals()

    def run(self) -> None:
        try:
            if self.reverse:
                coordinates = parse_coordinates(self.query)
                if coordinates is None:
                    raise ValueError("Enter latitude, longitude to reverse geocode.")
                result = self.geocoder.reverse_geocode(
                    coordinates.latitude, coordinates.longitude
                )
                results = [result] if result else []
            else:
                results = self.geocoder.geocode(self.query)
            self.signals.completed.emit(self.token, results, "", self.reverse)
        except Exception as exc:
            logger.error(f"Geocoding request failed: {exc}\n{traceback.format_exc()}")
            self.signals.completed.emit(self.token, [], str(exc), self.reverse)


class LocationWidget(QGroupBox):
    """
    Widget for location search with results display.

    Signals:
        location_selected(GeocodingResult): Emitted when the user selects
            a geocoding result.
    """

    location_selected = pyqtSignal(object)  # GeocodingResult
    search_started = pyqtSignal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__("Location Search", parent)
        self._geocoder = NominatimGeocoder()
        self._data_points = DataPointsManager()
        self._results = []
        self._request_token = 0
        self._closed = False
        self._project_connections = []
        self._points_layer_id = None
        self._points_layer_slots = {}
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(600)
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Search bar
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            "Enter address, place name, or coordinates (lat, lon)…"
        )
        self._search_btn = QPushButton("Search")
        self._reverse_btn = QPushButton("Reverse")
        search_row.addWidget(self._search_input, stretch=1)
        search_row.addWidget(self._search_btn)
        search_row.addWidget(self._reverse_btn)
        layout.addLayout(search_row)

        # Results combo
        self._results_combo = QComboBox()
        self._results_combo.setVisible(False)
        layout.addWidget(self._results_combo)

        self._details_label = QLabel("")
        self._details_label.setWordWrap(True)
        layout.addWidget(self._details_label)

        # Coordinate display
        coord_row = QHBoxLayout()
        coord_row.addWidget(QLabel("Lat:"))
        self._lat_label = QLabel("—")
        if TEXT_SELECTABLE_BY_MOUSE:
            self._lat_label.setTextInteractionFlags(TEXT_SELECTABLE_BY_MOUSE)
        coord_row.addWidget(self._lat_label)

        coord_row.addWidget(QLabel("Lon:"))
        self._lon_label = QLabel("—")
        if TEXT_SELECTABLE_BY_MOUSE:
            self._lon_label.setTextInteractionFlags(TEXT_SELECTABLE_BY_MOUSE)
        coord_row.addWidget(self._lon_label)
        layout.addLayout(coord_row)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._status_label)

        points_row = QHBoxLayout()
        self._points_combo = QComboBox()
        self._points_combo.setMinimumContentsLength(20)
        self._add_point_btn = QPushButton("Add Point")
        self._delete_point_btn = QPushButton("Delete Point")
        self._refresh_points_btn = QPushButton("Refresh")
        self._save_points_btn = QPushButton("Save Points…")
        points_row.addWidget(self._points_combo, stretch=1)
        points_row.addWidget(self._add_point_btn)
        points_row.addWidget(self._delete_point_btn)
        points_row.addWidget(self._refresh_points_btn)
        points_row.addWidget(self._save_points_btn)
        layout.addLayout(points_row)
        self._refresh_points()

    def _connect_signals(self) -> None:
        self._search_btn.clicked.connect(self._on_search)
        self._reverse_btn.clicked.connect(self._on_reverse_geocode)
        self._search_input.returnPressed.connect(self._submit_search)
        self._search_input.textChanged.connect(self._on_query_changed)
        self._debounce_timer.timeout.connect(self._submit_search)
        self._results_combo.currentIndexChanged.connect(self._on_result_selected)
        self._add_point_btn.clicked.connect(self._add_current_point)
        self._delete_point_btn.clicked.connect(self._delete_selected_point)
        self._refresh_points_btn.clicked.connect(self._refresh_points)
        self._save_points_btn.clicked.connect(self._save_points)

    def connect_project_signals(self) -> None:
        """Subscribe to data-point layer lifecycle and feature edits."""
        if self._project_connections:
            return
        project = QgsProject.instance()
        for signal_name, slot in (
            ("layersAdded", self._on_project_layers_changed),
            ("layersRemoved", self._on_project_layers_changed),
            ("layersWillBeRemoved", self._on_layers_will_be_removed),
            ("cleared", self._on_project_layers_changed),
        ):
            signal = getattr(project, signal_name, None)
            if signal is not None:
                signal.connect(slot)
                self._project_connections.append((signal, slot))
        self._bind_points_layer()

    def disconnect_project_signals(self) -> None:
        for signal, slot in self._project_connections:
            signal.disconnect(slot)
        self._project_connections.clear()
        self._unbind_points_layer()

    def _on_project_layers_changed(self, *_args) -> None:
        self._bind_points_layer()
        self._refresh_points()

    def _on_layers_will_be_removed(self, *args) -> None:
        removed_ids = set()
        for value in args:
            if isinstance(value, (list, tuple, set)):
                removed_ids.update(
                    layer.id() if hasattr(layer, "id") else str(layer)
                    for layer in value
                )
            elif hasattr(value, "id"):
                removed_ids.add(value.id())
            elif isinstance(value, str):
                removed_ids.add(value)
        if self._points_layer_id in removed_ids:
            self._unbind_points_layer()

    def _bind_points_layer(self) -> None:
        layer = self._data_points.current_layer()
        layer_id = layer.id() if layer is not None else None
        if layer_id == self._points_layer_id:
            return
        self._unbind_points_layer()
        if layer is None:
            return
        self._points_layer_id = layer_id
        for signal_name in ("featureAdded", "featureDeleted", "featuresDeleted"):
            signal = getattr(layer, signal_name, None)
            if signal is None:
                continue
            slot = lambda *_args: self._refresh_points()
            signal.connect(slot)
            self._points_layer_slots[signal_name] = slot

    def _unbind_points_layer(self) -> None:
        if self._points_layer_id:
            layer = QgsProject.instance().mapLayer(self._points_layer_id)
            if layer is not None:
                for signal_name, slot in self._points_layer_slots.items():
                    signal = getattr(layer, signal_name, None)
                    if signal is not None:
                        signal.disconnect(slot)
        self._points_layer_id = None
        self._points_layer_slots.clear()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search(self) -> None:
        self._debounce_timer.stop()
        self._submit_request(reverse=False)

    def _on_reverse_geocode(self) -> None:
        self._debounce_timer.stop()
        self._submit_request(reverse=True)

    def _on_query_changed(self, query: str) -> None:
        self._request_token += 1
        self._results = []
        self._results_combo.blockSignals(True)
        self._results_combo.clear()
        self._results_combo.setVisible(False)
        self._results_combo.blockSignals(False)
        self._details_label.clear()
        self._lat_label.setText("—")
        self._lon_label.setText("—")
        if query.strip():
            self._debounce_timer.start()
        else:
            self._debounce_timer.stop()

    def _submit_search(self) -> None:
        self._debounce_timer.stop()
        self._submit_request(reverse=False)

    def _submit_request(self, reverse: bool) -> None:
        query = self._search_input.text().strip()
        if not query:
            self._status_label.setText("Please enter a location.")
            return

        self._status_label.setText("Searching…")
        self._search_btn.setEnabled(False)
        self._reverse_btn.setEnabled(False)
        self._results = []
        self._results_combo.blockSignals(True)
        self._results_combo.clear()
        self._results_combo.setVisible(False)
        self._results_combo.blockSignals(False)
        self._details_label.clear()
        self.search_started.emit()
        self._request_token += 1
        self._closed = False
        task = _GeocodeTask(self._geocoder, self._request_token, query, reverse)
        task.signals.completed.connect(self._on_request_completed)
        self._thread_pool.start(task)

    def _on_request_completed(
        self, token: int, results: object, error: str, reverse: bool
    ) -> None:
        if self._closed or token != self._request_token:
            return
        self._search_btn.setEnabled(True)
        self._reverse_btn.setEnabled(True)
        if error:
            self._status_label.setText(f"Search failed: {error}")
            self._results_combo.setVisible(False)
            return
        results = list(results or [])

        if not results:
            self._status_label.setText("No matching location was found.")
            self._results_combo.setVisible(False)
            return

        self._results = results

        # Populate combo
        self._results_combo.blockSignals(True)
        self._results_combo.clear()
        for r in results:
            label = self._result_label(r)
            self._results_combo.addItem(label)
        self._results_combo.blockSignals(False)
        self._results_combo.setVisible(len(results) > 1)

        # Auto-select first
        self._results_combo.setCurrentIndex(0)
        self._select_result(0)

        self._status_label.setText(
            ("Reverse geocoded" if reverse else f"Found {len(results)} result(s)")
            + f" via {results[0].source}."
        )

    def _on_result_selected(self, index: int) -> None:
        if 0 <= index < len(self._results):
            self._select_result(index)

    def _select_result(self, index: int) -> None:
        result = self._results[index]
        self._lat_label.setText(f"{result.latitude:.6f}")
        self._lon_label.setText(f"{result.longitude:.6f}")
        self._details_label.setText(self._result_details(result))
        self.location_selected.emit(result)

    @staticmethod
    def _result_label(result: GeocodingResult) -> str:
        name = result.name or result.display_name or "Location"
        kind = ": ".join(part for part in (result.category, result.subcategory) if part)
        address = result.display_name or f"{result.latitude:.6f}, {result.longitude:.6f}"
        coordinates = f"{result.latitude:.5f}, {result.longitude:.5f}"
        return " | ".join(part for part in (name, kind, address, coordinates) if part)

    @staticmethod
    def _result_details(result: GeocodingResult) -> str:
        lines = [result.display_name or "Address unavailable"]
        kind = ": ".join(part for part in (result.category, result.subcategory) if part)
        if kind:
            lines.append(f"Type: {kind}")
        lines.append(f"Coordinates: {result.latitude:.7f}, {result.longitude:.7f}")
        for label, value in (
            ("Phone", result.phone), ("Website", result.website),
            ("Hours", result.opening_hours), ("Operator", result.operator),
        ):
            if value:
                lines.append(f"{label}: {value}")
        return "\n".join(lines)

    def _refresh_points(self) -> None:
        self._points_combo.blockSignals(True)
        self._points_combo.clear()
        for point in self._data_points.list_points():
            self._points_combo.addItem(
                f"{point['name']} ({point['latitude']:.5f}, {point['longitude']:.5f})",
                point["feature_id"],
            )
        self._points_combo.blockSignals(False)

    def _add_current_point(self) -> None:
        result = self.current_result()
        if result is None:
            self._status_label.setText("Search for a location before adding a point.")
            return
        try:
            outcome = self._data_points.add_result(result)
            self._refresh_points()
            self._status_label.setText(
                "Point added to the project layer."
                if outcome["added"] else "This point is already in the data-points layer."
            )
        except Exception as exc:
            logger.error(f"Could not add data point: {exc}\n{traceback.format_exc()}")
            self._status_label.setText(f"Could not add point: {exc}")

    def _delete_selected_point(self) -> None:
        feature_id = self._points_combo.currentData()
        if feature_id is None:
            self._status_label.setText("Select a data point to delete.")
            return
        if self._data_points.delete_feature(int(feature_id)):
            self._refresh_points()
            self._status_label.setText("Data point deleted.")

    def _save_points(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Data Points", "data_points.gpkg", "GeoPackage (*.gpkg)"
        )
        if not path:
            return
        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"
        try:
            saved_path = self._data_points.save_as(path)
            self._refresh_points()
            self._status_label.setText(f"Data points saved: {saved_path}")
        except Exception as exc:
            logger.error(f"Could not save data points: {exc}\n{traceback.format_exc()}")
            self._status_label.setText(f"Could not save data points: {exc}")

    def cancel_pending_requests(self) -> None:
        self._closed = True
        self._request_token += 1
        self._debounce_timer.stop()
        self._search_btn.setEnabled(True)
        self._reverse_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def current_result(self) -> Optional[GeocodingResult]:
        """Return the currently selected geocoding result, or None."""
        idx = self._results_combo.currentIndex()
        if 0 <= idx < len(self._results):
            return self._results[idx]
        return None
