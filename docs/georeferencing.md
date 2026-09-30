# Georeferencing & Spatial Alignment Guide

## 1. The Core Principle

A generated GeoTIFF must align with original QGIS layers when added back to the project. Any discrepancy in origin coordinates, pixel sizes, or CRS representation degrades data integrity.

---

## 2. Affine Transform Formulation

In GDAL and GeoTIFF standards, the mapping from pixel coordinates `(pixel, line)` to projected coordinates `(Xp, Yp)` is defined by an affine transformation matrix represented as a 6-element tuple:

```
Xp = geotransform[0] + pixel * geotransform[1] + line * geotransform[2]
Yp = geotransform[3] + pixel * geotransform[4] + line * geotransform[5]
```

### Element Breakdown

| Index | Parameter | Description | In GeoSpatial Tools |
|---|---|---|---|
| `0` | `origin_x` | X coordinate of upper-left corner of upper-left pixel | `extent.xMinimum()` |
| `1` | `pixel_width` | Pixel size in X direction (CRS units/pixel) | `(xmax - xmin) / width_px` |
| `2` | `rotation_x` | Row rotation / skew | `0.0` (North-up) |
| `3` | `origin_y` | Y coordinate of upper-left corner of upper-left pixel | `extent.yMaximum()` |
| `4` | `rotation_y` | Column rotation / skew | `0.0` (North-up) |
| `5` | `pixel_height` | Pixel size in Y direction (negative for north-up) | `-(ymax - ymin) / height_px` |

---

## 3. Metric vs Geographic Coordinate Systems

When user specifies ground resolution (e.g. `0.5 m/pixel`), degree-based coordinate systems like WGS 84 (`EPSG:4326`) cannot be used directly because degrees vary with latitude:

$$1^\circ \text{ longitude} \approx 111.320 \times \cos(\text{latitude}) \text{ km}$$

### Strategy
1. Determine location coordinates in WGS 84.
2. Select the optimal Universal Transverse Mercator (UTM) zone covering the area:
   $$\text{Zone Number} = \left\lfloor \frac{\text{longitude} + 180}{6} \right\rfloor + 1$$
   $$\text{EPSG Code} = 32600 + \text{Zone} \text{ (North)} \quad \text{or} \quad 32700 + \text{Zone} \text{ (South)}$$
3. Compute extent boundaries in metric UTM coordinates.
4. If the user specifies an alternative output CRS, reproject the bounding box cleanly using `QgsCoordinateTransform`.

---

## 4. Automated Verification

Before any GeoTIFF is added to QGIS, `GeoTiffValidator` opens the file independently and verifies:
1. `RasterXSize == expected_width` and `RasterYSize == expected_height`.
2. Projection WKT matches target CRS authority.
3. Affine transform matches expected 6-tuple within a tolerance of $10^{-8}$.
4. Reconstructed extent bounds match the original AOI.
