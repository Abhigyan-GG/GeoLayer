# GeoSpatial Tools — QGIS Geospatial Rendering & GeoTIFF Generator

A production-quality QGIS plugin for rendering map layers into validated, georeferenced GeoTIFF files.

---

## 🌟 Key Features

1. **POI-Aware Location Search**: Search places, addresses, buildings, organizations, and coordinates through Nominatim, with normalized provider metadata and reverse geocoding.
2. **Data Points Layer**: Add selected results as WGS 84 points, deduplicate repeats, delete individual features, and save points to GeoPackage.
3. **Flexible AOI (Area of Interest) Management**:
   - Radius around point (metric calculations via auto-detected UTM projections)
   - Width × Height rectangle around point
   - Current map canvas extent capture
   - Interactive click-and-drag drawing on the QGIS canvas
   - Boundary extraction from existing vector/raster layers
4. **Canvas Navigation & Highlight**: Zooms to selected result bounds, showing a native point marker and result-area highlight.
5. **Dynamic Layer Selection**: Tracks project layer IDs and refreshes as layers are added or removed.
6. **Native QGIS Map Rendering**: Powered by `QgsMapRendererParallelJob` and `QgsMapSettings`. **No screen captures, no browser scraping, no lossy window captures.**
7. **Spatial Resolution Control**: User-specified ground resolution in metres per pixel (with presets from 0.1 m to 10 m). Automatically computes exact raster width and height.
8. **Strict Georeferencing Preservation**:
   - North-up affine transform matrix: `(xmin, pixel_w, 0, ymax, 0, -pixel_h)`
   - Full CRS Well-Known Text (WKT) preservation
   - Exact pixel dimensions aligned to bounding rectangle
9. **High-Performance GeoTIFF Output**:
   - Written via native GDAL `GTiff` driver
   - Configurable compression (`DEFLATE`, `LZW`, `ZSTD`, `NONE`)
   - Tiled storage (`TILED=YES`, 256×256 blocks)
   - Automatic `BIGTIFF` handling for large datasets
10. **Automated Post-Export Validation**: Reopens the written GeoTIFF through GDAL to verify file integrity, raster dimensions, band counts, CRS metadata, and geographic extent alignment before admitting the file.
11. **Automatic QGIS Project Integration**: Adds the validated raster layer into QGIS under a dedicated `"GeoSpatial Tools — Exports"` layer group and centres the map view.
12. **Safety Safeguards**: Automatic warnings and memory estimation to prevent OOM errors when users request extreme resolutions over large extents.
13. **Future Processing & Feature Extraction Ready**: Modular interfaces for raster processing, polygon vectorization, and classical CV / ML feature extraction.

---
## 🏗️ Architecture

```
qgis-geospatial-tools/
├── geospatial_tools/
│   ├── __init__.py                # QGIS classFactory entry point
│   ├── metadata.txt               # Plugin metadata
│   ├── geospatial_tools.py        # Plugin lifecycle and actions
│   ├── core/
│   │   ├── geocoder.py            # Normalized location and POI providers
│   │   ├── data_points.py         # Project POI layer and GeoPackage persistence
│   │   ├── aoi_manager.py         # AOI geometry calculations
│   │   ├── layer_manager.py       # Current project layer resolution
│   │   ├── renderer.py            # QgsMapRendererParallelJob wrapper
│   │   ├── raster_writer.py       # GDAL GeoTIFF writer
│   │   └── validation.py          # Post-export validation
│   ├── ui/
│   │   ├── main_dialog.py         # Dialog orchestration
│   │   └── widgets/
│   │       ├── location_widget.py # Search, reverse geocode, and data points
│   │       ├── aoi_widget.py      # AOI controls
│   │       └── layer_selector.py  # Dynamic layer selection
│   ├── processing/                # Extensible post-processing stubs
│   │   ├── raster_processing.py   # Clipping, resampling, reprojection
│   │   ├── vector_processing.py   # Polygonization, simplification
│   │   └── feature_extraction.py  # Classical CV & ML feature extraction
│   │
│   └── utils/
│       ├── constants.py           # Safety limits, defaults, constants
│       ├── helpers.py             # Size formatting, memory calculation, paths
│       └── plugin_logger.py       # QgsMessageLog and standard logging
│
├── tests/                         # Automated unit & integration tests
│   ├── test_aoi.py                # AOI geometry calculations
│   ├── test_geocoder.py           # Coordinate parsing & validation
│   ├── test_georeferencing.py     # Affine transform math
│   ├── test_helpers.py            # Helpers, dimensions, memory
│   ├── test_raster_writer.py      # QImage -> GeoTIFF write & validate loop
│   └── test_validation.py         # Synthetic GeoTIFF validation
│
├── docs/                          # In-depth technical documentation
│   ├── architecture.md
│   ├── georeferencing.md
│   ├── rendering.md
│   ├── raster-processing.md
│   └── development.md
│
├── LICENSE                        # MIT License
└── README.md
```

---

## 🚀 Installation

### Option 1: Install from ZIP (Recommended for Windows & All Platforms)
1. Generate or use `geospatial_tools.zip` in the repository root (run `python package_plugin.py` to rebuild if needed).
2. In QGIS, navigate to **Plugins → Manage and Install Plugins… → Install from ZIP**.
3. Select `geospatial_tools.zip` and click **Install Plugin**.
4. Check **GeoSpatial Tools** under the **Installed** tab to enable it.

### Option 2: Direct Copy into QGIS Plugins Directory
1. Locate your active QGIS user profile's python plugin directory (or open via **Settings → User Profiles → Open Active Profile Folder**):
   - **Windows (QGIS 4.x)**: `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\`
   - **Windows (QGIS 3.x)**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/` (or `QGIS3`)
   - **macOS**: `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/` (or `QGIS3`)
2. Copy or symlink the `geospatial_tools` folder into that directory:
   ```cmd
   xcopy /E /I geospatial_tools "%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\geospatial_tools"
   ```
3. Restart QGIS or reload plugins via the **Plugin Reloader** plugin.
4. Open **Plugins → Manage and Install Plugins… → Installed** and check **GeoSpatial Tools**.

---

## 📖 Step-by-Step Usage

Click **Help / How to Use** in the plugin dialog for an in-app guide to the complete search, AOI, and export workflow. To draw an AOI, select **Draw rectangle on canvas**, click **Click & Drag Extent on Map**, then drag directly on the QGIS map canvas. The completed rectangle is transformed into the plugin's AOI CRS and used by the export pipeline.

The offline location registry includes **CFEES — Centre for Fire, Explosive and Environment Safety, Timarpur, Delhi**, at WGS 84 coordinates `28.7037056, 77.2168583`. Search aliases include CFEES, CFEES Timarpur, DRDO CFEES, CFEES Delhi, and the full organization name.

### 1. Open the Plugin
Click the **GeoSpatial Tools** icon on the toolbar or select **Raster → GeoSpatial Tools → Render & Generate GeoTIFF…**.

### 2. Search for a Location
- Type an address, landmark, or coordinates:
  - `"Connaught Place, New Delhi"`
  - `"IIT Delhi"`
  - `"28.6315, 77.2167"`
- Press **Enter** or click **Search**.
- Select the best result from the dropdown if multiple matches appear. The map canvas will automatically zoom to the location.
- Use **Reverse** with coordinates to look up nearby address and POI details.
- Use **Add Point** to store a result in the project data-points layer. **Delete Point** removes one feature; **Save Points…** writes a GeoPackage.

### 3. Define the Area of Interest (AOI)
Choose your preferred definition method:
- **Radius around point**: Enter radius in metres (e.g. `500 m` for a 1 km × 1 km square).
- **Width × Height rectangle**: Specify custom metric dimensions (e.g. `1500 m` wide × `800 m` high).
- **Current map canvas extent**: Snap the export boundary directly to what is currently visible on screen.
- **Draw rectangle on canvas**: Click to drag an interactive bounding box.
- **From existing layer**: Snap the AOI boundary to the bounding extent of any project vector/raster layer.

Click **Preview AOI on Canvas** to zoom in and review the red preview box.

### 4. Select Layers to Render
Check or uncheck layers in the **Layers to Render** table. Use **Select All**, **Clear All**, or **Select Visible** for quick toggling.

### 5. Configure Resolution & Output Settings
- **Spatial Resolution**: Enter desired resolution in metres per pixel (e.g. `0.5 m/pixel`), or choose a preset.
- The interface immediately displays:
  - Resulting dimensions (e.g. `2000 × 2000 pixels`)
  - Total megapixels (e.g. `4.00 Megapixels`)
  - Estimated uncompressed RAM and compressed disk size
- **Output CRS**: Defaults to Project CRS or auto-suggested metric UTM CRS.
- **Compression**: Choose between `DEFLATE` (default, lossless), `LZW`, `ZSTD`, or `NONE`.
- **Output File**: Choose destination directory and filename.

### 6. Generate GeoTIFF
Click **GENERATE GEOTIFF**.
1. QGIS renders the selected layers off-screen.
2. The plugin calculates the affine transform and writes the GeoTIFF.
3. The file is validated via GDAL.
4. The generated raster is loaded into QGIS and placed in the `"GeoSpatial Tools — Exports"` group.

---

## 🧪 Automated Testing

The plugin includes unit and QGIS integration tests. Use QGIS's Python environment for the full suite because it provides PyQGIS and GDAL:

```bash
# Run tests with QGIS Python:
python-qgis.bat -m unittest discover -s tests -p "test_*.py" -v
```

Coverage includes:
- Bounding box and radius calculations in metric projections
- Nominatim coordinate parsing and boundary limits
- POI metadata normalization, reverse geocoding, empty responses, HTTP 429, and timeout handling
- Data-point deduplication/deletion, current layer resolution, and AOI source removal
- North-up affine transform generation and inverse extent reconstruction
- Raster dimension rounding and RAM consumption calculations
- Complete QImage → GDAL GeoTIFF → Validator loop with synthetic datasets
- Dimension mismatch detection and missing file handling

---

## ⚖️ Source Data Licensing & Ethical Usage

This plugin is a **rendering and rasterization utility** that operates on layers loaded within QGIS. It is **not** an automated tile scraper or bulk downloader.

- Users are responsible for complying with the terms of service and licensing agreements of any third-party data providers (e.g., OpenStreetMap, Google Maps, Bing, Esri, Mapbox, or commercial satellite providers) loaded in QGIS.
- If a data provider prohibits local caching or export of rendered tiles, do not export those layers.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
