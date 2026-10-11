"""
GeoSpatial Tools — Main Plugin Entry Class.

Integrates with QGIS GUI: toolbar buttons, Raster menu entries,
actions, and dialog lifecycle management.
"""

import os
from typing import Optional

from qgis.core import Qgis
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .ui.main_dialog import MainDialog
from .ui.settings_dialog import SettingsDialog
from .utils.constants import PLUGIN_NAME
from .utils.plugin_logger import get_logger

logger = get_logger()


class GeoSpatialToolsPlugin:
    """
    Main QGIS plugin class instantiated by classFactory().
    """

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        self.actions = []
        self.menu = f"&{PLUGIN_NAME}"

        self.main_dialog: Optional[MainDialog] = None
        self.settings_dialog: Optional[SettingsDialog] = None

    # ------------------------------------------------------------------
    # Plugin Lifecycle
    # ------------------------------------------------------------------

    def initGui(self) -> None:
        """Create the UI elements: menus, toolbar icons, and actions."""
        # 1. Main Action: Generate GeoTIFF
        icon_main = self._get_icon("icon.png", fallback_color=QColor(43, 120, 228))
        self.action_main = QAction(
            icon_main,
            self.tr("Render & Generate GeoTIFF…"),
            self.iface.mainWindow(),
        )
        self.action_main.setObjectName("actionGeoSpatialToolsMain")
        self.action_main.setStatusTip(self.tr("Render QGIS layers to georeferenced GeoTIFF"))
        self.action_main.triggered.connect(self.run)

        # 2. Settings Action
        icon_settings = self._get_icon("settings.png", fallback_color=QColor(100, 100, 100))
        self.action_settings = QAction(
            icon_settings,
            self.tr("Settings…"),
            self.iface.mainWindow(),
        )
        self.action_settings.setObjectName("actionGeoSpatialToolsSettings")
        self.action_settings.triggered.connect(self.open_settings)

        # Add to Toolbar & Raster Menu
        self.iface.addToolBarIcon(self.action_main)
        self.iface.addPluginToRasterMenu(self.menu, self.action_main)
        self.iface.addPluginToRasterMenu(self.menu, self.action_settings)

        self.actions.extend([self.action_main, self.action_settings])
        logger.info(f"{PLUGIN_NAME} initialized successfully.")

    def unload(self) -> None:
        """Remove actions from menus and toolbars when unloaded."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        if self.main_dialog:
            self.main_dialog.close()
            self.main_dialog = None

        if self.settings_dialog:
            self.settings_dialog.close()
            self.settings_dialog = None

        logger.info(f"{PLUGIN_NAME} unloaded.")

    # ------------------------------------------------------------------
    # Action Triggers
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Open or raise the main dialog."""
        if self.main_dialog is None:
            self.main_dialog = MainDialog(self.iface, parent=self.iface.mainWindow())
        self.main_dialog.show()
        self.main_dialog.raise_()
        self.main_dialog.activateWindow()

    def open_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(parent=self.iface.mainWindow())
        exec_method = getattr(dialog, "exec", None) or getattr(dialog, "exec_")
        exec_method()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def tr(self, message: str) -> str:
        """Translate helper."""
        return QCoreApplication.translate("GeoSpatialTools", message)

    def _get_icon(self, filename: str, fallback_color: QColor) -> QIcon:
        """Load an icon from disk or generate a crisp programmatic fallback."""
        icon_path = os.path.join(self.plugin_dir, filename)
        if os.path.exists(icon_path):
            return QIcon(icon_path)

        # Generate a clean vector-like icon pixmap
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        hint = getattr(QPainter, "Antialiasing", getattr(getattr(QPainter, "RenderHint", None), "Antialiasing", None))
        if hint is not None:
            painter.setRenderHint(hint)
        painter.setBrush(fallback_color)
        painter.setPen(QColor(255, 255, 255))
        painter.drawRoundedRect(2, 2, 28, 28, 4, 4)
        # Inner raster grid lines
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawLine(10, 4, 10, 28)
        painter.drawLine(18, 4, 18, 28)
        painter.drawLine(4, 10, 28, 10)
        painter.drawLine(4, 18, 28, 18)
        painter.end()
        return QIcon(pix)
