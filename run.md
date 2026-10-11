# Run GeoSpatial Tools in QGIS

## 1. Install QGIS

Install QGIS for macOS from the official QGIS download page: <https://qgis.org/download/>. Launch QGIS once so it creates a user profile, then close it before installing this plugin.

The plugin requires QGIS 3.28 or newer. PyQGIS, GDAL, and Qt are supplied by QGIS; a regular system Python installation does not include them.

## 2. Find the plugin folder

In QGIS, open **Settings → User Profiles → Open Active Profile Folder** (the menu wording can vary slightly by QGIS version). Inside that folder, the plugin directory is:

```text
python/plugins/
```

On a standard macOS default profile, the full path is usually:

```text
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
```

Use the active profile folder shown by QGIS if you selected a different profile. You can also confirm the path from QGIS's Python Console:

```python
from qgis.core import QgsApplication
import os

plugin_path = os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins", "geospatial_tools")
print(plugin_path)
print(os.path.isdir(plugin_path))
```

The second line of output should be `True` after installation.

## 3. Install this checkout

Open Terminal and change to the repository root (the directory containing `README.md` and `geospatial_tools/`). For example:

```bash
cd ~/Downloads/GeoLayer
```

Create the plugin folder if needed, then make a symlink so edits in this checkout are used directly by QGIS:

```bash
PLUGIN_DIR="$HOME/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins"
mkdir -p "$PLUGIN_DIR"
ln -s "$PWD/geospatial_tools" "$PLUGIN_DIR/geospatial_tools"
```

If you use a non-default QGIS profile, replace `PLUGIN_DIR` with that profile's `python/plugins` path. If `geospatial_tools` already exists there, inspect it first: keep a backup or remove/rename the old installation before creating the symlink. Do not replace an existing folder blindly.

Alternatively, create an installable ZIP from the repository root:

```bash
zip -r geospatial_tools.zip geospatial_tools -x "*.pyc" "*__pycache__*"
```

Then in QGIS select **Plugins → Manage and Install Plugins… → Install from ZIP**, choose `geospatial_tools.zip`, and install it.

## 4. Enable and open the plugin

1. Start or restart QGIS.
2. Open **Plugins → Manage and Install Plugins… → Installed**.
3. Find **GeoSpatial Tools** and check its box to enable it.
4. Open it from the **Raster → GeoSpatial Tools** menu or its toolbar button. If it is not listed, see the troubleshooting section below.

## 5. Run a quick smoke check

1. Load at least one raster or vector layer into a QGIS project. An XYZ/WMS layer can also be used if it is available and its provider permits export.
2. Open **GeoSpatial Tools → Render & Generate GeoTIFF…** from the Raster menu.
3. Search for a place or enter coordinates, choose an AOI, select layers, and choose an output file and resolution.
4. Generate the GeoTIFF. Confirm that the output is added to the project under **GeoSpatial Tools — Exports** and that the file exists at the chosen location.

For a safe first run, use a small area and a modest resolution. Export rights for third-party map data remain subject to the provider's terms.

## 6. Run the tests

Run the tests using Python provided by the same QGIS installation, not macOS's standalone `python3`. The repository test suite imports PyQGIS and GDAL, so a normal system interpreter will report missing `qgis` or `osgeo` modules.

From a QGIS Python Console, the following runs the suite with QGIS's active Python environment. Replace the repository path if it is elsewhere:

```python
import os
import subprocess
import sys

repo = os.path.expanduser("~/Downloads/GeoLayer")
subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", os.path.join(repo, "tests"), "-p", "test_*.py", "-v"],
    cwd=repo,
)
```

## Troubleshooting

- **Plugin missing from the Installed list:** confirm that `geospatial_tools/metadata.txt` is inside the active profile's `python/plugins/geospatial_tools/` directory, enable the plugin in Plugin Manager, and restart QGIS.
- **Plugin fails to load:** open **Plugins → Python Console**, inspect the QGIS message log for the traceback, and verify that the installation contains the current `geospatial_tools` package. The plugin's main entry point is `geospatial_tools/__init__.py` (`classFactory`).
- **Plugin installed to the wrong profile:** use QGIS's **Open Active Profile Folder** command and move/install it under that profile's `python/plugins/` folder.
- **Tests fail with `No module named 'qgis'` or `No module named 'osgeo'`:** the tests are being run with a Python environment outside QGIS. Run them from QGIS's Python environment as described above.
