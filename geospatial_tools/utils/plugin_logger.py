"""
GeoSpatial Tools — Plugin Logger.

Provides structured logging that integrates with QGIS's message log system.
"""

import logging
from typing import Optional


# Plugin-wide logger name
PLUGIN_LOG_TAG = "GeoSpatial Tools"


class PluginLogger:
    """
    Structured logger for the GeoSpatial Tools plugin.

    Logs to both Python's logging system and QGIS's QgsMessageLog.
    Provides consistent formatting and log-level control.
    """

    def __init__(self, name: str = PLUGIN_LOG_TAG, level: int = logging.INFO):
        """
        Initialize the plugin logger.

        Args:
            name: Logger name / tag for QGIS message log.
            level: Minimum logging level.
        """
        self.tag = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # Avoid duplicate handlers on reload
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(name)s] %(levelname)s: %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        # Try to import QGIS logging — may not be available in tests
        self._qgis_available = False
        try:
            from qgis.core import QgsMessageLog, Qgis
            self._QgsMessageLog = QgsMessageLog
            self._Qgis = Qgis
            self._qgis_available = True
        except ImportError:
            pass

    def info(self, message: str) -> None:
        """Log an informational message."""
        self._logger.info(message)
        if self._qgis_available:
            self._QgsMessageLog.logMessage(
                message, self.tag, self._Qgis.Info
            )

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self._logger.warning(message)
        if self._qgis_available:
            self._QgsMessageLog.logMessage(
                message, self.tag, self._Qgis.Warning
            )

    def error(self, message: str) -> None:
        """Log an error message."""
        self._logger.error(message)
        if self._qgis_available:
            self._QgsMessageLog.logMessage(
                message, self.tag, self._Qgis.Critical
            )

    def debug(self, message: str) -> None:
        """Log a debug message."""
        self._logger.debug(message)

    def set_level(self, level: int) -> None:
        """Change the logging level at runtime."""
        self._logger.setLevel(level)


# Singleton logger instance for the plugin
_logger_instance: Optional[PluginLogger] = None


def get_logger() -> PluginLogger:
    """
    Get the singleton plugin logger instance.

    Returns:
        PluginLogger: The shared logger instance.
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PluginLogger()
    return _logger_instance
