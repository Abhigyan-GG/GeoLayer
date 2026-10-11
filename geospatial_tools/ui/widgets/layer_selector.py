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
from ...utils.compat import (
    CHECK_CHECKED,
    CHECK_UNCHECKED,
    HEADER_RESIZE_TO_CONTENTS,
    HEADER_STRETCH,
    ITEM_CHECKABLE,
    ITEM_ENABLED,
    ITEM_SELECTABLE,
    SELECTION_SELECT_ROWS,
    USER_ROLE,
)
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
        self._table.horizontalHeader().setSectionResizeMode(0, HEADER_RESIZE_TO_CONTENTS)
        self._table.horizontalHeader().setSectionResizeMode(1, HEADER_STRETCH)
        self._table.horizontalHeader().setSectionResizeMode(2, HEADER_RESIZE_TO_CONTENTS)
        self._table.horizontalHeader().setSectionResizeMode(3, HEADER_RESIZE_TO_CONTENTS)
        self._table.setSelectionBehavior(SELECTION_SELECT_ROWS)
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
        """Rebuild the table from current project state, retaining valid selections."""
        previously_selected = set(self.get_selected_layer_ids())
        previous_ids = {info.layer_id for info in self._layers_cache}
        valid_ids = self._manager.get_valid_layer_ids()
        previously_selected.intersection_update(valid_ids)

        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            self._layers_cache = self._manager.get_all_layers()
            self._table.setRowCount(len(self._layers_cache))
            for row, info in enumerate(self._layers_cache):
                checked = (
                    info.layer_id in previously_selected
                    if info.layer_id in previous_ids
                    else info.visible
                )
                chk_item = QTableWidgetItem()
                chk_item.setFlags(ITEM_CHECKABLE | ITEM_ENABLED)
                chk_item.setCheckState(CHECK_CHECKED if checked else CHECK_UNCHECKED)
                chk_item.setData(USER_ROLE, info.layer_id)
                self._table.setItem(row, 0, chk_item)

                name_item = QTableWidgetItem(info.name)
                name_item.setFlags(ITEM_ENABLED | ITEM_SELECTABLE)
                self._table.setItem(row, 1, name_item)

                type_item = QTableWidgetItem(info.layer_type.capitalize())
                type_item.setFlags(ITEM_ENABLED | ITEM_SELECTABLE)
                self._table.setItem(row, 2, type_item)

                crs_item = QTableWidgetItem(info.crs_auth or "—")
                crs_item.setFlags(ITEM_ENABLED | ITEM_SELECTABLE)
                self._table.setItem(row, 3, crs_item)
        finally:
            self._table.blockSignals(False)
        self._emit_selection()

    def get_selected_layer_ids(self) -> List[str]:
        """
        Return checked IDs in project layer-tree order (top to bottom).
        """
        selected_ids: List[str] = []
        valid_ids = self._manager.get_valid_layer_ids()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.checkState() == CHECK_CHECKED:
                layer_id = item.data(USER_ROLE)
                if layer_id and layer_id in valid_ids:
                    selected_ids.append(layer_id)
        # QgsMapSettings uses index zero for the topmost layer.
        return selected_ids

    def layer_will_be_removed(self, layer_ids: set) -> None:
        """Uncheck IDs before QGIS destroys their layer objects."""
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(USER_ROLE) in layer_ids:
                item.setCheckState(CHECK_UNCHECKED)
        self._table.blockSignals(False)
        self._emit_selection()

    # ------------------------------------------------------------------
    # Internal Slots
    # ------------------------------------------------------------------

    def _select_all(self) -> None:
        self._set_all_check_states(CHECK_CHECKED)

    def _select_none(self) -> None:
        self._set_all_check_states(CHECK_UNCHECKED)

    def _select_visible(self) -> None:
        visible_ids = {
            info.layer_id for info in self._manager.get_visible_layers()
        }
        self._table.blockSignals(True)
        for row, info in enumerate(self._layers_cache):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(
                    CHECK_CHECKED if info.layer_id in visible_ids else CHECK_UNCHECKED
                )
        self._table.blockSignals(False)
        self._emit_selection()

    def _set_all_check_states(self, state) -> None:
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
