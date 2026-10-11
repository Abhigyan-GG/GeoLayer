"""
GeoSpatial Tools — Location Search Widget.

Provides a search bar for entering addresses / place names / coordinates,
displays results, and emits signals when a location is selected.
"""

from typing import List, Optional

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.geocoder import GeocodingResult, NominatimGeocoder
from ...utils.compat import TEXT_SELECTABLE_BY_MOUSE
from ...utils.plugin_logger import get_logger

logger = get_logger()


class LocationWidget(QGroupBox):
    """
    Widget for location search with results display.

    Signals:
        location_selected(GeocodingResult): Emitted when the user selects
            a geocoding result.
    """

    location_selected = pyqtSignal(object)  # GeocodingResult

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__("Location Search", parent)
        self._geocoder = NominatimGeocoder()
        self._results: list = []
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
        search_row.addWidget(self._search_input, stretch=1)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        # Results combo
        self._results_combo = QComboBox()
        self._results_combo.setVisible(False)
        layout.addWidget(self._results_combo)

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

    def _connect_signals(self) -> None:
        self._search_btn.clicked.connect(self._on_search)
        self._search_input.returnPressed.connect(self._on_search)
        self._results_combo.currentIndexChanged.connect(self._on_result_selected)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            self._status_label.setText("Please enter a location.")
            return

        self._status_label.setText("Searching…")
        self._search_btn.setEnabled(False)

        try:
            results = self._geocoder.geocode(query)
        except Exception as exc:
            self._status_label.setText(f"Error: {exc}")
            self._search_btn.setEnabled(True)
            return

        self._search_btn.setEnabled(True)

        if not results:
            self._status_label.setText(
                f"No results for '{query}'. Try a more specific address."
            )
            self._results_combo.setVisible(False)
            return

        self._results = results

        # Populate combo
        self._results_combo.blockSignals(True)
        self._results_combo.clear()
        for r in results:
            label = r.display_name or f"{r.latitude:.6f}, {r.longitude:.6f}"
            self._results_combo.addItem(label)
        self._results_combo.blockSignals(False)
        self._results_combo.setVisible(len(results) > 1)

        # Auto-select first
        self._results_combo.setCurrentIndex(0)
        self._select_result(0)

        self._status_label.setText(
            f"Found {len(results)} result(s) via {results[0].source}."
        )

    def _on_result_selected(self, index: int) -> None:
        if 0 <= index < len(self._results):
            self._select_result(index)

    def _select_result(self, index: int) -> None:
        result = self._results[index]
        self._lat_label.setText(f"{result.latitude:.6f}")
        self._lon_label.setText(f"{result.longitude:.6f}")
        self.location_selected.emit(result)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def current_result(self) -> Optional[GeocodingResult]:
        """Return the currently selected geocoding result, or None."""
        idx = self._results_combo.currentIndex()
        if 0 <= idx < len(self._results):
            return self._results[idx]
        return None
