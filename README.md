# GeoSpatial Tools — QGIS Geospatial Rendering & GeoTIFF Generator

A production-quality QGIS plugin acting as a geospatial rendering and rasterization toolkit. Renders existing QGIS map layers (XYZ tiles, WMS/WMTS, rasters, vectors, GeoPackages, Shapefiles) directly into properly georeferenced GeoTIFF files with mathematical affine transform precision, automated validation, and project integration.

---

## 🌟 Key Features

1. **Human-Readable Location Search**: Geocode places, addresses, or landmarks via OpenStreetMap Nominatim with direct latitude/longitude parsing, result selection, caching, and rate limiting.
2. **Flexible AOI (Area of Interest) Management**:
   - Radius around point (metric calculations via auto-detected UTM projections)
   - Width × Height rectangle around point
   - Current map canvas extent capture
   - Interactive click-and-drag drawing on the QGIS canvas
   - Boundary extraction from existing vector/raster layers
3. **Canvas Auto-Navigation & Rubber-Band Preview**: Zooms to search results and visually highlights the target AOI with a translucent red boundary on the live QGIS canvas.
4. **Layer Selection & Control**: Granular selection of layers participating in export, synchronized with QGIS's layer tree.
5. **Native QGIS Map Rendering**: Powered by `QgsMapRendererParallelJob` and `QgsMapSettings`. **No screen captures, no browser scraping, no lossy window captures.**
6. **Spatial Resolution Control**: User-specified ground resolution in metres per pixel (with presets from 0.1 m to 10 m). Automatically computes exact raster width and height.
7. **Strict Georeferencing Preservation**:
   - North-up affine transform matrix: `(xmin, pixel_w, 0, ymax, 0, -pixel_h)`
   - Full CRS Well-Known Text (WKT) preservation
   - Exact pixel dimensions aligned to bounding rectangle
8. **High-Performance GeoTIFF Output**:
   - Written via native GDAL `GTiff` driver
   - Configurable compression (`DEFLATE`, `LZW`, `ZSTD`, `NONE`)
   - Tiled storage (`TILED=YES`, 256×256 blocks)
   - Automatic `BIGTIFF` handling for large datasets
9. **Automated Post-Export Validation**: Reopens the written GeoTIFF through GDAL to verify file integrity, raster dimensions, band counts, CRS metadata, and geographic extent alignment before admitting the file.
10. **Automatic QGIS Project Integration**: Adds the validated raster layer into QGIS under a dedicated `"GeoSpatial Tools — Exports"` layer group and centres the map view.
11. **Safety Safeguards**: Automatic warnings and memory estimation to prevent OOM errors when users request extreme resolutions over large extents.
12. **Future Processing & Feature Extraction Ready**: Modular interfaces for raster processing, polygon vectorization, and classical CV / ML feature extraction.

---

## 🏗️ Architecture

```
qgis-geospatial-tools/
├── geospatial_tools/
│   ├── __init__.py                # QGIS classFactory entry point
│   ├── metadata.txt               # QGIS Plugin Manager metadata (Qt6 & Qt5 compatible)
│   ├── geospatial_tools.py        # Plugin lifecycle: menus, toolbars, actions
│   ├── resources.qrc              # Qt resource bundle
│   ├── icon.png                   # Plugin icon
│   │
│   ├── core/                      # Pure GIS logic — decoupled from UI
│   │   ├── geocoder.py            # Geocoder interface + Nominatim + direct parser
│   │   ├── aoi_manager.py         # Radius, rectangle, canvas, layer AOI generation
│   │   ├── layer_manager.py       # Layer tree querying and ordering
│   │   ├── renderer.py            # QgsMapRendererParallelJob off-screen engine
│   │   ├── raster_writer.py       # GDAL GeoTIFF writer (tiled, compressed, metadata)
│   │   ├── georeferencing.py      # Affine transform & GeoReference structures
│   │   ├── validation.py          # Post-export GDAL reopen & validation
│   │   └── crs_utils.py           # Auto-UTM detection and metric reprojections
│   │
│   ├── ui/                        # PyQt UI layer
│   │   ├── main_dialog.py         # Main orchestrator dialog
│   │   ├── settings_dialog.py     # QgsSettings configuration dialog
│   │   └── widgets/
│   │       ├── location_widget.py # Search bar & coordinate display
│   │       ├── aoi_widget.py      # AOI method & dimension controls
│   │       ├── layer_selector.py  # Layer checkbox list
│   │       └── export_widget.py   # Resolution, CRS, compression, estimates
│   │
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

### Option 1: Direct Copy into QGIS Plugins Directory
1. Locate your active QGIS user profile's python plugin directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
2. Copy or symlink the `geospatial_tools` folder into that directory:
   ```bash
   cp -r geospatial_tools/ "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\geospatial_tools"
   ```
3. Restart QGIS or reload plugins via the **Plugin Reloader** plugin.
4. Open **Plugins → Manage and Install Plugins… → Installed** and check **GeoSpatial Tools**.

### Option 2: Install from ZIP
1. Zip the `geospatial_tools` folder:
   ```bash
   zip -r geospatial_tools.zip geospatial_tools/
   ```
2. In QGIS, navigate to **Plugins → Manage and Install Plugins… → Install from ZIP**.
3. Select `geospatial_tools.zip` and click **Install Plugin**.

---

## 📖 Step-by-Step Usage

### 1. Open the Plugin
Click the **GeoSpatial Tools** icon on the toolbar or select **Raster → GeoSpatial Tools → Render & Generate GeoTIFF…**.

### 2. Search for a Location
- Type an address, landmark, or coordinates:
  - `"Connaught Place, New Delhi"`
  - `"IIT Delhi"`
  - `"28.6315, 77.2167"`
- Press **Enter** or click **Search**.
- Select the best result from the dropdown if multiple matches appear. The map canvas will automatically pan to the location.

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

The plugin includes an extensive unit and integration test suite:

```bash
# Run tests with QGIS Python:
python-qgis.bat -m unittest discover -s tests -p "test_*.py" -v
```

All 20 unit and integration tests verify:
- Bounding box and radius calculations in metric projections
- Nominatim coordinate parsing and boundary limits
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
