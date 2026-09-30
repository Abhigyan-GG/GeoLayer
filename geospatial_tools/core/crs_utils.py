"""
GeoSpatial Tools — CRS Utilities.

Helpers for coordinate reference system detection, automatic UTM zone
selection, and metric-safe transformations.
"""

import math
from typing import Optional, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)

from ..utils.plugin_logger import get_logger

logger = get_logger()


def get_project_crs() -> QgsCoordinateReferenceSystem:
    """
    Return the current QGIS project CRS.

    Returns:
        QgsCoordinateReferenceSystem of the active project.
    """
    return QgsProject.instance().crs()


def is_geographic(crs: QgsCoordinateReferenceSystem) -> bool:
    """Check whether a CRS uses geographic (degree-based) units."""
    return crs.isGeographic()


def is_projected(crs: QgsCoordinateReferenceSystem) -> bool:
    """Check whether a CRS uses projected (metre/foot-based) units."""
    return not crs.isGeographic()


def auto_utm_epsg(longitude: float, latitude: float) -> int:
    """
    Determine the EPSG code for the UTM zone covering *longitude*/*latitude*.

    Uses WGS 84 UTM zones (EPSG 326xx for north, 327xx for south).

    Args:
        longitude: Longitude in decimal degrees.
        latitude: Latitude in decimal degrees.

    Returns:
        EPSG integer code.
    """
    zone_number = int((longitude + 180.0) / 6.0) + 1
    zone_number = max(1, min(60, zone_number))
    if latitude >= 0:
        return 32600 + zone_number  # North
    return 32700 + zone_number      # South


def auto_utm_crs(
    longitude: float, latitude: float
) -> QgsCoordinateReferenceSystem:
    """
    Create a QgsCoordinateReferenceSystem for the appropriate UTM zone.

    Args:
        longitude: Longitude in decimal degrees.
        latitude: Latitude in decimal degrees.

    Returns:
        QgsCoordinateReferenceSystem for the UTM zone.
    """
    epsg = auto_utm_epsg(longitude, latitude)
    crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
    if not crs.isValid():
        logger.warning(f"Auto-UTM CRS EPSG:{epsg} is invalid; falling back to project CRS.")
        return get_project_crs()
    return crs


def suggested_metric_crs(
    center: QgsPointXY,
    source_crs: QgsCoordinateReferenceSystem,
) -> QgsCoordinateReferenceSystem:
    """
    For a given centre point, suggest a projected CRS suitable for metric
    distance calculations.

    If *source_crs* is already projected, return it unchanged.
    Otherwise, auto-detect the appropriate UTM zone.

    Args:
        center: Point in *source_crs*.
        source_crs: Current CRS of the centre point.

    Returns:
        A projected QgsCoordinateReferenceSystem.
    """
    if is_projected(source_crs):
        return source_crs

    # Transform to WGS 84 to read lon/lat
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    xform = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
    pt84 = xform.transform(center)

    return auto_utm_crs(pt84.x(), pt84.y())


def transform_point(
    point: QgsPointXY,
    source_crs: QgsCoordinateReferenceSystem,
    dest_crs: QgsCoordinateReferenceSystem,
) -> QgsPointXY:
    """
    Reproject a single point.

    Args:
        point: Input point.
        source_crs: Source CRS.
        dest_crs: Destination CRS.

    Returns:
        Reprojected QgsPointXY.
    """
    if source_crs == dest_crs:
        return QgsPointXY(point)
    xform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    return xform.transform(point)


def transform_extent(
    extent: QgsRectangle,
    source_crs: QgsCoordinateReferenceSystem,
    dest_crs: QgsCoordinateReferenceSystem,
) -> QgsRectangle:
    """
    Reproject a rectangle extent.

    Args:
        extent: Input extent.
        source_crs: Source CRS.
        dest_crs: Destination CRS.

    Returns:
        Reprojected QgsRectangle.
    """
    if source_crs == dest_crs:
        return QgsRectangle(extent)
    xform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
    return xform.transformBoundingBox(extent)


def extent_dimensions_metres(
    extent: QgsRectangle,
    crs: QgsCoordinateReferenceSystem,
) -> Tuple[float, float]:
    """
    Calculate the width and height of an extent in metres.

    For projected CRS this is straightforward arithmetic.
    For geographic CRS the extent is first transformed to the appropriate UTM.

    Args:
        extent: Bounding rectangle.
        crs: CRS of the extent.

    Returns:
        (width_m, height_m) tuple.
    """
    if is_projected(crs):
        # Assume CRS units are metres (most projected CRS are)
        return extent.width(), extent.height()

    # Transform to UTM for the centre of the extent
    center = extent.center()
    utm = suggested_metric_crs(center, crs)
    projected = transform_extent(extent, crs, utm)
    return projected.width(), projected.height()


def crs_to_string(crs: QgsCoordinateReferenceSystem) -> str:
    """
    Human-readable CRS description.

    Example: "EPSG:32643 — WGS 84 / UTM zone 43N"
    """
    auth = crs.authid() or "Unknown"
    desc = crs.description() or ""
    if desc:
        return f"{auth} — {desc}"
    return auth
