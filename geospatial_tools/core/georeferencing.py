"""
GeoSpatial Tools — Georeferencing.

Builds GDAL-compatible affine GeoTransforms from extent + pixel dimensions
and provides structures for passing georeferencing metadata through the
pipeline.
"""

from dataclasses import dataclass, field
from typing import Tuple

from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle

from ..utils.plugin_logger import get_logger

logger = get_logger()


@dataclass(frozen=True)
class GeoTransform:
    """
    Immutable representation of a GDAL-style affine GeoTransform.

    Attributes:
        origin_x: X coordinate of the upper-left corner of the upper-left pixel.
        pixel_width: Pixel size in the X direction (positive, in CRS units).
        rotation_x: Row rotation (usually 0.0).
        origin_y: Y coordinate of the upper-left corner of the upper-left pixel.
        rotation_y: Column rotation (usually 0.0).
        pixel_height: Pixel size in the Y direction (negative for north-up).
    """

    origin_x: float
    pixel_width: float
    rotation_x: float
    origin_y: float
    rotation_y: float
    pixel_height: float  # Should be negative for north-up rasters

    def to_gdal_tuple(self) -> Tuple[float, float, float, float, float, float]:
        """
        Return the transform as a 6-element tuple for GDAL's SetGeoTransform().
        """
        return (
            self.origin_x,
            self.pixel_width,
            self.rotation_x,
            self.origin_y,
            self.rotation_y,
            self.pixel_height,
        )

    @property
    def is_north_up(self) -> bool:
        """True when the raster follows the conventional north-up orientation."""
        return (
            self.rotation_x == 0.0
            and self.rotation_y == 0.0
            and self.pixel_height < 0.0
        )


@dataclass(frozen=True)
class GeoReference:
    """
    Complete georeferencing information for a raster output.

    Combines the affine transform with CRS and pixel dimensions so that
    any downstream consumer has everything needed to write a valid GeoTIFF.
    """

    transform: GeoTransform
    crs: QgsCoordinateReferenceSystem
    width: int
    height: int
    extent: QgsRectangle

    @property
    def crs_wkt(self) -> str:
        """CRS in Well-Known Text format."""
        return self.crs.toWkt()

    @property
    def pixel_size_x(self) -> float:
        """Absolute pixel width in CRS units."""
        return abs(self.transform.pixel_width)

    @property
    def pixel_size_y(self) -> float:
        """Absolute pixel height in CRS units."""
        return abs(self.transform.pixel_height)


def build_geotransform(
    extent: QgsRectangle,
    width: int,
    height: int,
) -> GeoTransform:
    """
    Construct a north-up affine GeoTransform from an extent and pixel dims.

    Pixel (0, 0) maps to (xmin, ymax) — the top-left corner.
    Pixel (width, height) maps to (xmax, ymin) — the bottom-right corner.

    Args:
        extent: Geographic/projected bounding rectangle.
        width: Raster width in pixels.
        height: Raster height in pixels.

    Returns:
        GeoTransform dataclass.

    Raises:
        ValueError: If dimensions are non-positive or extent is empty.
    """
    if width <= 0 or height <= 0:
        raise ValueError(
            f"Raster dimensions must be positive; got {width}×{height}."
        )
    if extent.isEmpty():
        raise ValueError("Extent must not be empty.")

    pixel_w = (extent.xMaximum() - extent.xMinimum()) / width
    pixel_h = (extent.yMaximum() - extent.yMinimum()) / height

    if pixel_w <= 0.0 or pixel_h <= 0.0:
        raise ValueError(
            f"Computed pixel size is non-positive: "
            f"({pixel_w}, {pixel_h}). Check extent."
        )

    gt = GeoTransform(
        origin_x=extent.xMinimum(),
        pixel_width=pixel_w,
        rotation_x=0.0,
        origin_y=extent.yMaximum(),
        rotation_y=0.0,
        pixel_height=-pixel_h,  # Negative for north-up
    )

    logger.debug(
        f"Built GeoTransform: origin=({gt.origin_x:.6f}, {gt.origin_y:.6f}), "
        f"pixel=({gt.pixel_width:.8f}, {gt.pixel_height:.8f})"
    )
    return gt


def build_georeference(
    extent: QgsRectangle,
    crs: QgsCoordinateReferenceSystem,
    width: int,
    height: int,
) -> GeoReference:
    """
    Build a complete GeoReference object.

    Args:
        extent: Bounding rectangle in *crs*.
        crs: Output coordinate reference system.
        width: Output raster width in pixels.
        height: Output raster height in pixels.

    Returns:
        GeoReference dataclass.
    """
    transform = build_geotransform(extent, width, height)
    return GeoReference(
        transform=transform,
        crs=crs,
        width=width,
        height=height,
        extent=QgsRectangle(extent),
    )


def extent_from_geotransform(
    gt: GeoTransform,
    width: int,
    height: int,
) -> QgsRectangle:
    """
    Reconstruct the extent from a GeoTransform and pixel dimensions.

    Useful for validation — the reconstructed extent should match the
    original AOI within floating-point tolerance.

    Args:
        gt: GeoTransform.
        width: Raster width.
        height: Raster height.

    Returns:
        QgsRectangle.
    """
    xmin = gt.origin_x
    ymax = gt.origin_y
    xmax = xmin + gt.pixel_width * width
    ymin = ymax + gt.pixel_height * height  # pixel_height is negative
    return QgsRectangle(xmin, ymin, xmax, ymax)
