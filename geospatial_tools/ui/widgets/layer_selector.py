"""
GeoSpatial Tools — Layer Selector Widget.

Provides a list of existing QGIS project layers with checkboxes,
type indicators, visibility toggles, and bulk selection controls.
"""

from typing import List, Optional

from qgis.core import QgsMapLayer, QgsProject
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.layer_manager import LayerInfo, LayerManager
from ...utils.plugin_logger import get_logger

logger = get_logger()


class LayerSelectorWidget(QGroupBox):
    """
    Widget allowing user to select which QGIS layers participate in rendering.

    Signals:
        selection_changed(list): Emitted with list of selected layer IDs.
    """

    selection_changed = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Layers to Render", parent)
        self._manager = LayerManager()
        self._layers_cache: List[LayerInfo] = []

        self._setup_ui()
        self._connect_signals()
        self.refresh_layers()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Table for layers
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Include", "Layer Name", "Type", "CRS"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # Control Buttons
        btn_row = QHBoxLayout()
        self._btn_all = QPushButton("Select All")
        self._btn_none = QPushButton("Clear All")
        self._btn_visible = QPushButton("Select Visible")
        self._btn_refresh = QPushButton("↻ Refresh")

        btn_row.addWidget(self._btn_all)
        btn_row.addWidget(self._btn_none)
        btn_row.addWidget(self._btn_visible)
        btn_row.addStretch(1)
        btn_row.addWidget(self._btn_refresh)
        layout.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self._btn_all.clicked.connect(self._select_all)
        self._btn_none.clicked.connect(self._select_none)
        self._btn_visible.clicked.connect(self._select_visible)
        self._btn_refresh.clicked.connect(self.refresh_layers)
        self._table.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def refresh_layers(self) -> None:
        """Reload layers from the active QGIS project."""
        self._table.blockSignals(True)
        self._table.setRowCount(0)

        self._layers_cache = self._manager.get_all_layers()

        self._table.setRowCount(len(self._layers_cache))
        for row, info in enumerate(self._layers_cache):
            # Checkbox item
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Checked if info.visible else Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, info.layer_id)
            self._table.setItem(row, 0, chk_item)

            # Name item
            name_item = QTableWidgetItem(info.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 1, name_item)

            # Type item
            type_item = QTableWidgetItem(info.layer_type.capitalize())
            type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 2, type_item)

            # CRS item
            crs_item = QTableWidgetItem(info.crs_auth or "—")
            crs_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 3, crs_item)

        self._table.blockSignals(False)
        self._emit_selection()

    def get_selected_layer_ids(self) -> List[str]:
        """
        Return the list of checked layer IDs in rendering order
        (bottom to top / layer tree order inverted for painter).
        """
        selected_ids: List[str] = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                layer_id = item.data(Qt.ItemDataRole.UserRole)
                if layer_id:
                    selected_ids.append(layer_id)
        # Note: in QGIS layer tree, top is index 0. For QgsMapSettings,
        # layers are rendered back-to-front, so we keep order or reverse as desired.
        return selected_ids

    # ------------------------------------------------------------------
    # Internal Slots
    # ------------------------------------------------------------------

    def _select_all(self) -> None:
        self._set_all_check_states(Qt.CheckState.Checked)

    def _select_none(self) -> None:
        self._set_all_check_states(Qt.CheckState.Unchecked)

    def _select_visible(self) -> None:
        self._table.blockSignals(True)
        for row, info in enumerate(self._layers_cache):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if info.visible else Qt.CheckState.Unchecked)
        self._table.blockSignals(False)
        self._emit_selection()

    def _set_all_check_states(self, state: Qt.CheckState) -> None:
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(state)
        self._table.blockSignals(False)
        self._emit_selection()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._emit_selection()

    def _emit_selection(self) -> None:
        self.selection_changed.emit(self.get_selected_layer_ids())
