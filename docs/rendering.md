# Rendering Engine Guide

## 1. Why QgsMapRendererParallelJob?

Many simple tools attempt to extract map imagery using desktop screen capture, window grabbing, or tile scraping:
- **Screen capture** is restricted by display scaling, window geometry, monitor DPI, UI overlays, and occluding windows.
- **Tile scraping** violates tile usage policies, produces visible stitching seams, and fails on vector styling, custom symbology, labels, and local file layers.

GeoSpatial Tools uses **`QgsMapRendererParallelJob`**, QGIS's official multi-threaded off-screen rendering engine.

---

## 2. Configuration Pipeline

```python
settings = QgsMapSettings()

# 1. Selected layers (ordered bottom-to-top)
settings.setLayers(layers)

# 2. Bounding extent
settings.setExtent(extent)

# 3. Output CRS (QGIS reprojects on the fly)
settings.setDestinationCrs(crs)

# 4. Target dimensions
settings.setOutputSize(QSize(width_px, height_px))

# 5. DPI for text / marker scaling
settings.setOutputDpi(96)

# 6. Quality flags
settings.setFlag(QgsMapSettings.Antialiasing, True)
settings.setFlag(QgsMapSettings.UseAdvancedEffects, True)
```

---

## 3. Asynchronous Execution with Non-Blocking UI

Rendering large regions at high resolution can take several seconds. To prevent QGIS from freezing:
1. `QgsMapRendererParallelJob` dispatches rendering across background threads.
2. A local Qt event loop (`QEventLoop`) monitors completion while continuing to process UI repaint events.
3. Progress status updates are piped to the progress bar and QGIS message bar.
4. A safety timer cancels rendering if it exceeds 5 minutes.
