"""
GeoSpatial Tools — Settings Dialog.

Allows configuring plugin preferences stored persistently
using QGIS's native QgsSettings infrastructure.
"""

from typing import Optional

from qgis.core import QgsSettings
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..utils.constants import (
    COMPRESSION_OPTIONS,
    DEFAULT_BIGTIFF,
    DEFAULT_COMPRESSION,
    DEFAULT_RESOLUTION_M,
    GEOCODER_TIMEOUT_S,
    MAX_RASTER_DIMENSION,
    NOMINATIM_URL,
    PLUGIN_TAG,
)


class SettingsDialog(QDialog):
    """Configuration dialog for GeoSpatial Tools settings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GeoSpatial Tools — Settings")
        self.resize(500, 350)
        self._settings = QgsSettings()

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Default export directory
        row_dir = QHBoxLayout()
        self._txt_dir = QLineEdit()
        self._btn_browse_dir = QPushButton("Browse…") if False else QFileDialog
        self._btn_dir = QDialogButtonBox() if False else None
        # Use simple browse button
        from qgis.PyQt.QtWidgets import QPushButton
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_dir)
        row_dir.addWidget(self._txt_dir, stretch=1)
        row_dir.addWidget(btn_browse)
        form.addRow("Default Output Directory:", row_dir)

        # Default Resolution
        self._spin_res = QDoubleSpinBox()
        self._spin_res.setRange(0.01, 1000.0)
        self._spin_res.setValue(DEFAULT_RESOLUTION_M)
        self._spin_res.setSuffix(" m/pixel")
        form.addRow("Default Resolution:", self._spin_res)

        # Default Compression
        self._combo_compression = QComboBox()
        self._combo_compression.addItems(COMPRESSION_OPTIONS)
        form.addRow("Default Compression:", self._combo_compression)

        # Max dimension safeguard
        self._spin_max_dim = QSpinBox()
        self._spin_max_dim.setRange(1000, 100000)
        self._spin_max_dim.setValue(MAX_RASTER_DIMENSION)
        self._spin_max_dim.setSingleStep(5000)
        form.addRow("Max Dimension Safeguard (px):", self._spin_max_dim)

        # Geocoder URL
        self._txt_geocoder_url = QLineEdit()
        form.addRow("Geocoder Search URL:", self._txt_geocoder_url)

        # Geocoder Timeout
        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(2, 60)
        self._spin_timeout.setValue(GEOCODER_TIMEOUT_S)
        self._spin_timeout.setSuffix(" s")
        form.addRow("Geocoder Timeout:", self._spin_timeout)

        layout.addLayout(form)

        # OK / Cancel buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Default Output Directory", self._txt_dir.text()
        )
        if directory:
            self._txt_dir.setText(directory)

    def _load_settings(self) -> None:
        prefix = f"{PLUGIN_TAG}/"
        self._txt_dir.setText(self._settings.value(f"{prefix}export_dir", ""))
        self._spin_res.setValue(
            float(self._settings.value(f"{prefix}default_res", DEFAULT_RESOLUTION_M))
        )
        self._combo_compression.setCurrentText(
            self._settings.value(f"{prefix}compression", DEFAULT_COMPRESSION)
        )
        self._spin_max_dim.setValue(
            int(self._settings.value(f"{prefix}max_dim", MAX_RASTER_DIMENSION))
        )
        self._txt_geocoder_url.setText(
            self._settings.value(f"{prefix}geocoder_url", NOMINATIM_URL)
        )
        self._spin_timeout.setValue(
            int(self._settings.value(f"{prefix}geocoder_timeout", GEOCODER_TIMEOUT_S))
        )

    def _save_and_accept(self) -> None:
        prefix = f"{PLUGIN_TAG}/"
        self._settings.setValue(f"{prefix}export_dir", self._txt_dir.text().strip())
        self._settings.setValue(f"{prefix}default_res", self._spin_res.value())
        self._settings.setValue(f"{prefix}compression", self._combo_compression.currentText())
        self._settings.setValue(f"{prefix}max_dim", self._spin_max_dim.value())
        self._settings.setValue(f"{prefix}geocoder_url", self._txt_geocoder_url.text().strip())
        self._settings.setValue(f"{prefix}geocoder_timeout", self._spin_timeout.value())
        self.accept()
