# Developer Guide — Contributing & Testing

## 1. Development Environment Setup

### Prerequisites
- QGIS 3.28 LTR or newer (including QGIS 3.34+ and QGIS 4.x with Qt6 / Python 3.12 support).
- Python 3.8+ with PyQGIS, GDAL/osgeo, and NumPy.

### Running Tests Locally
On Windows with QGIS installed:
```cmd
"C:\Program Files\QGIS 4.2.3\bin\python-qgis.bat" -m unittest discover -s tests -p "test_*.py" -v
```

On Linux:
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 2. Directory Conventions

- `geospatial_tools/core/`: Keep this directory completely free of Qt GUI dependencies (`QWidget`, `QDialog`, `QMessageBox`, etc.) so core geospatial logic can be tested in headless environments and CI runners.
- `geospatial_tools/ui/`: Contains all PyQt widgets and dialogs.
- `geospatial_tools/utils/`: Shared utilities, logging, and safety constants.
- `tests/`: Automated unit tests using Python's `unittest` module.

---

## 3. Packaging for Release

To package the plugin for installation through the QGIS Plugin Manager:
```bash
# Exclude git repository and temporary artifacts
zip -r geospatial_tools.zip geospatial_tools/ -x "*.pyc" "*__pycache__*" "*.git*"
```
The resulting `.zip` file can be installed via **Plugins → Manage and Install Plugins… → Install from ZIP**.
