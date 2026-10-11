# Run GeoSpatial Tools in QGIS (Windows & macOS)

This guide covers running **GeoSpatial Tools** on **QGIS 4.2.1+ (Qt6)** as well as **QGIS 3.28+ (Qt5)** across **Windows**, **macOS**, and **Linux**.

---

## 1. Prerequisites & Compatibility

- **Supported QGIS Versions:** QGIS 3.28 through QGIS 4.x (including QGIS 4.2.1-Belém do Pará).
- **Python / Qt Support:** Dual-compatible with Python 3.9–3.12+ and Qt5 / Qt6 (PyQt5 / PyQt6).
- All dependencies (`qgis`, `PyQt`, `osgeo/GDAL`, `numpy`) are provided directly inside QGIS. No separate external pip dependencies are required.

---

## 2. Locate Your QGIS Plugin Directory

The universal method on **any OS** (Windows, macOS, Linux):
1. Launch QGIS.
2. In the top menu, click **Settings → User Profiles → Open Active Profile Folder**.
3. In the folder that opens, navigate into:
   ```text
   python/plugins/
   ```

### Default Profile Paths by Operating System:
- **Windows (QGIS 4.x):**
  ```text
  %APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\
  ```
  *(e.g., `C:\Users\<username>\AppData\Roaming\QGIS\QGIS4\profiles\default\python\plugins\`)*
- **Windows (QGIS 3.x):**
  ```text
  %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\
  ```
- **macOS (QGIS 4.x):**
  ```text
  ~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/
  ```
- **macOS (QGIS 3.x):**
  ```text
  ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
  ```
- **Linux:**
  ```text
  ~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/  (or QGIS3)
  ```

---

## 3. Install the Plugin

Choose either **Method A (ZIP - Recommended for Windows)** or **Method B (Direct Folder Copy/Symlink)**.

### Method A: Install from ZIP (Recommended & Easiest)
1. In the repository folder, a clean `geospatial_tools.zip` is pre-packaged. (You can also re-create it at any time by running `python package_plugin.py`).
2. Open QGIS.
3. Go to **Plugins → Manage and Install Plugins… → Install from ZIP**.
4. Browse to and select `geospatial_tools.zip`.
5. Click **Install Plugin**.
6. When prompted, confirm overwrite if an older version exists.

### Method B: Direct Folder Copy / Symlink
Copy the `geospatial_tools` directory into your active profile's `python/plugins/` directory:

**Windows (Command Prompt / PowerShell):**
```bat
xcopy /E /I geospatial_tools "%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\geospatial_tools"
```
*(Replace `QGIS4` with `QGIS3` if running on QGIS 3.x)*

**macOS / Linux (Terminal symlink for live development):**
```bash
PLUGIN_DIR="$HOME/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins"
mkdir -p "$PLUGIN_DIR"
ln -s "$PWD/geospatial_tools" "$PLUGIN_DIR/geospatial_tools"
```

---

## 4. Enable and Open the Plugin in QGIS

1. Start or restart QGIS.
2. Open **Plugins → Manage and Install Plugins… → Installed**.
3. Check the box next to **GeoSpatial Tools**.
4. Open the plugin via:
   - The toolbar icon (blue grid icon)
   - Or the menu: **Raster → GeoSpatial Tools → Render & Generate GeoTIFF…**

---

## 5. Quick Smoke Test

1. Add any raster layer, vector layer, or OpenStreetMap XYZ Tile (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) to your QGIS project.
2. Open **GeoSpatial Tools → Render & Generate GeoTIFF…**.
3. Search for a location (e.g. `Connaught Place, New Delhi` or `28.6315, 77.2167`).
4. Select an AOI (e.g. `Radius: 500 m`). Click **Preview AOI on Canvas** to see the red preview box.
5. Select the layer in the **Layers to Render** table.
6. Choose an output destination and click **GENERATE GEOTIFF**.
7. Verify that the GeoTIFF is generated, validated via GDAL, and automatically added to your QGIS project under the `GeoSpatial Tools — Exports` group.

---

## 6. Running Unit & Integration Tests

Because PyQGIS and GDAL are provided by QGIS's environment, tests must be run using QGIS's Python interpreter:

### Windows (OSGeo4W Shell or Python Console):
From OSGeo4W Shell:
```bat
python-qgis -m unittest discover -s tests -p "test_*.py" -v
```

### From QGIS Python Console (Any OS):
Open **Plugins → Python Console** in QGIS and run:
```python
import os, subprocess, sys

repo = r"C:\path\to\GeoLayer"  # Replace with your repository path
subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", os.path.join(repo, "tests"), "-p", "test_*.py", "-v"],
    cwd=repo,
)
```

---

## 7. Troubleshooting & Error Explanations

### `ImportError: cannot import name 'QgsRubberBand' from 'qgis.core'`
- **Cause:** In earlier plugin builds, `QgsRubberBand` was incorrectly imported from `qgis.core`. In both QGIS 3 and QGIS 4, `QgsRubberBand` belongs to `qgis.gui`.
- **Solution:** This has been resolved in v0.1.1 with a dual-fallback compatibility layer (`geospatial_tools.utils.compat`). If you previously installed an older version, make sure to overwrite or delete the old folder in `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\geospatial_tools` and reinstall from `geospatial_tools.zip`.

### Plugin does not show in QGIS 4 Plugin Manager
- **Cause:** QGIS 4 requires `qgisMaximumVersion = 4.99` in `metadata.txt`. If absent, QGIS assumes the plugin only targets QGIS 3.
- **Solution:** `metadata.txt` is updated with `qgisMinimumVersion=3.28` and `qgisMaximumVersion=4.99`. Deprecated `supportsQt6=True` flag has been removed.

### Path / Filename errors on Windows
- **Cause:** File paths containing colons or unescaped backslashes from location names (e.g. `Delhi: Zone 1`).
- **Solution:** Built-in filename sanitization (`safe_filename`) strips illegal Windows characters (`<>:"/\|?*`) and ensures all paths are normalized via `os.path.normpath`.
