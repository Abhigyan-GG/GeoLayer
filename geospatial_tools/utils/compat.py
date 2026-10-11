"""
GeoSpatial Tools — Qt and QGIS Version Compatibility Layer.

Provides unified abstractions across Qt5 (PyQt5 / QGIS 3) and Qt6 (PyQt6 / QGIS 4),
including scoped enumeration fallbacks, widget helpers, and logging enums.
"""

from qgis.core import Qgis, QgsMapSettings, QgsWkbTypes
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QHeaderView,
    QMessageBox,
)

# ---------------------------------------------------------------------------
# 1. Action compatibility (QtGui in Qt6, QtWidgets in Qt5)
# ---------------------------------------------------------------------------
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction  # type: ignore

# ---------------------------------------------------------------------------
# 2. QgsRubberBand import compatibility
# ---------------------------------------------------------------------------
try:
    from qgis.gui import QgsRubberBand
except ImportError:
    from qgis.core import QgsRubberBand  # type: ignore

# ---------------------------------------------------------------------------
# 3. Polygon Geometry enum for QgsRubberBand
# Qt6/QGIS 4 uses Qgis.GeometryType.Polygon, while Qt5/QGIS 3 uses QgsWkbTypes.PolygonGeometry
# ---------------------------------------------------------------------------
POLYGON_GEOMETRY = (
    getattr(getattr(Qgis, "GeometryType", None), "Polygon", None)
    or getattr(getattr(QgsWkbTypes, "GeometryType", None), "PolygonGeometry", None)
    or getattr(QgsWkbTypes, "PolygonGeometry", 2)
)

# ---------------------------------------------------------------------------
# 4. Qt item flags & check states (PyQt5 vs PyQt6 scoped enums)
# ---------------------------------------------------------------------------
ITEM_CHECKABLE = (
    getattr(getattr(Qt, "ItemFlag", None), "ItemIsUserCheckable", None)
    or getattr(Qt, "ItemIsUserCheckable", 8)
)
ITEM_ENABLED = (
    getattr(getattr(Qt, "ItemFlag", None), "ItemIsEnabled", None)
    or getattr(Qt, "ItemIsEnabled", 32)
)
ITEM_SELECTABLE = (
    getattr(getattr(Qt, "ItemFlag", None), "ItemIsSelectable", None)
    or getattr(Qt, "ItemIsSelectable", 1)
)

CHECK_CHECKED = (
    getattr(getattr(Qt, "CheckState", None), "Checked", None)
    or getattr(Qt, "Checked", 2)
)
CHECK_UNCHECKED = (
    getattr(getattr(Qt, "CheckState", None), "Unchecked", None)
    or getattr(Qt, "Unchecked", 0)
)

USER_ROLE = (
    getattr(getattr(Qt, "ItemDataRole", None), "UserRole", None)
    or getattr(Qt, "UserRole", 32)
)

TEXT_SELECTABLE_BY_MOUSE = (
    getattr(getattr(Qt, "TextInteractionFlag", None), "TextSelectableByMouse", None)
    or getattr(Qt, "TextSelectableByMouse", 1)
)

# ---------------------------------------------------------------------------
# 5. Table view enum helpers
# ---------------------------------------------------------------------------
HEADER_RESIZE_TO_CONTENTS = (
    getattr(getattr(QHeaderView, "ResizeMode", None), "ResizeToContents", None)
    or getattr(QHeaderView, "ResizeToContents", 0)
)
HEADER_STRETCH = (
    getattr(getattr(QHeaderView, "ResizeMode", None), "Stretch", None)
    or getattr(QHeaderView, "Stretch", 1)
)
SELECTION_SELECT_ROWS = (
    getattr(getattr(QAbstractItemView, "SelectionBehavior", None), "SelectRows", None)
    or getattr(QAbstractItemView, "SelectRows", 1)
)

# ---------------------------------------------------------------------------
# 6. Dialog buttons
# ---------------------------------------------------------------------------
BUTTON_BOX_BUTTONS = getattr(QDialogButtonBox, "StandardButton", QDialogButtonBox)
MESSAGE_BOX_BUTTONS = getattr(QMessageBox, "StandardButton", QMessageBox)

# ---------------------------------------------------------------------------
# 7. QImage format helper
# ---------------------------------------------------------------------------
QIMAGE_FORMAT_ARGB32 = (
    getattr(getattr(QImage, "Format", None), "Format_ARGB32", None)
    or getattr(QImage, "Format_ARGB32", 3)
)

# ---------------------------------------------------------------------------
# 8. QgsMapSettings flags helper
# ---------------------------------------------------------------------------
def set_map_setting_flag(settings: QgsMapSettings, flag_name: str, enabled: bool) -> None:
    """Safely set a map setting flag across QGIS 3 and QGIS 4 enum namespaces."""
    flags_cls = getattr(Qgis, "MapSettingsFlag", QgsMapSettings)
    flag_val = getattr(flags_cls, flag_name, None)
    if flag_val is not None:
        settings.setFlag(flag_val, enabled)

# ---------------------------------------------------------------------------
# 9. QgsMessageLog level helpers
# ---------------------------------------------------------------------------
def get_message_level(level_name: str) -> int:
    """Return Qgis MessageLevel enum value across QGIS 3 and QGIS 4."""
    lvl_cls = getattr(Qgis, "MessageLevel", Qgis)
    return getattr(lvl_cls, level_name, 0)
