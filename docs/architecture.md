# Architecture Guide — GeoSpatial Tools

## 1. System Philosophy

GeoSpatial Tools is designed as a modular, native QGIS plugin that separates the user interface from core geospatial rendering and writing algorithms.

Key design principles:
1. **QGIS Engine Native**: Uses QGIS's internal rendering pipeline (`QgsMapSettings`, `QgsMapRendererParallelJob`) rather than screen captures or manual tile scraping.
2. **Strict Georeferencing**: Rasters must align pixel-for-pixel with native vector and raster layers in the QGIS canvas.
3. **Decoupled Architecture**: UI components in `ui/` only communicate with `core/` through well-defined dataclasses and interfaces.
4. **Validation-First**: Every exported file is verified through GDAL before being admitted to the user's project.

---

## 2. Component Structure

```
geospatial_tools/
├── core/
│   ├── geocoder.py         # Provider interface and normalized Nominatim results
│   ├── data_points.py      # Project POI layer and GeoPackage persistence
│   ├── aoi_manager.py      # AOI calculation in metric CRS
│   ├── layer_manager.py    # QGIS layer tree enumeration
│   ├── renderer.py         # Parallel map rendering engine
│   ├── raster_writer.py    # GDAL dataset creation and compression
│   ├── georeferencing.py   # Affine transform math and metadata
│   ├── validation.py       # Independent GDAL re-opening & verification
│   └── crs_utils.py        # Coordinate reference system utilities
│
├── ui/
│   ├── main_dialog.py      # Dialog lifecycle & execution orchestration
│   ├── settings_dialog.py  # Persistent preferences via QgsSettings
│   └── widgets/
│       ├── location_widget.py
│       ├── aoi_widget.py
│       ├── layer_selector.py
│       └── export_widget.py
│
└── processing/
    ├── raster_processing.py
    ├── vector_processing.py
    └── feature_extraction.py
```

---

## 3. Data Flow Pipeline

```
Human Search Query (e.g. "Connaught Place")
                   │
                   ▼
          [ Nominatim Geocoder ]
                   │
       Lat, Lon Coordinates (WGS 84)
                   │
                   ▼
          [ AOI Manager ] ──> Auto-UTM Projection
                   │
         Projected QgsRectangle
                   │
                   ▼
          [ Layer Manager ] ──> Selected QgsMapLayers
                   │
                   ▼
         [ Map Renderer ] ──> QgsMapRendererParallelJob
                   │
               QImage (ARGB32)
                   │
                   ▼
       [ Georeferencing Builder ] ──> GDAL 6-tuple Affine Transform
                   │
                   ▼
          [ GDAL Raster Writer ] ──> Tiled, Compressed GeoTIFF
                   │
                   ▼
        [ GeoTIFF Validator ] ──> GDAL Extent / CRS / Dims Check
                   │
                   ▼
      [ QGIS Project Integration ] ──> Dedicated Layer Group
```

## 4. Lifecycle and Search Safety

- Layer selectors persist IDs, not project-owned layer wrappers, and rebuild from current project state after layer-tree changes.
- AOI-from-layer state stores a layer ID and resolves it immediately before calculation. Removal clears the source selection.
- Rendering builds a fresh valid-layer snapshot and cancels/waits for an active job if one of its layers is about to be removed.
- Search and reverse-geocode requests run in a worker thread; debounce timers and request tokens prevent stale results from replacing newer searches.
- Nominatim results normalize optional address, category, provider ID, extra tags, named details, and contact fields.
- Search results can be saved as EPSG:4326 point features in the project data-points layer and exported to GeoPackage.
