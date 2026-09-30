"""
GeoSpatial Tools — AOI Manager.

Creates Area of Interest (AOI) extents from various user inputs:
radius around a point, width×height rectangle, current map extent,
or an existing polygon layer.

All distance calculations use projected CRS or geodesic maths —
never raw degree arithmetic.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)

from .crs_utils import (
    is_geographic,
    suggested_metric_crs,
    transform_extent,
    transform_point,
)
from ..utils.constants import (
    DEFAULT_AOI_HEIGHT_M,
    DEFAULT_AOI_RADIUS_M,
    DEFAULT_AOI_WIDTH_M,
)
from ..utils.plugin_logger import get_logger

logger = get_logger()


class AOIMethod(Enum):
    """Supported AOI creation methods."""

    RADIUS = "radius"
    RECTANGLE = "rectangle"
    CURRENT_EXTENT = "current_extent"
    DRAW_ON_MAP = "draw_on_map"
    FROM_LAYER = "from_layer"


@dataclass
class AOIParameters:
    """
    Parameters for AOI creation.

    Attributes:
        method: How the AOI should be constructed.
        center: Centre point (in *center_crs*). Required for RADIUS/RECTANGLE.
        center_crs: CRS of *center*. Defaults to WGS 84.
        radius_m: Radius in metres (RADIUS method).
        width_m: Width in metres (RECTANGLE method).
        height_m: Height in metres (RECTANGLE method).
        manual_extent: Pre-defined extent (CURRENT_EXTENT / DRAW_ON_MAP).
        manual_extent_crs: CRS of *manual_extent*.
        layer: Vector layer whose extent serves as AOI (FROM_LAYER).
    """

    method: AOIMethod = AOIMethod.RADIUS
    center: Optional[QgsPointXY] = None
    center_crs: Optional[QgsCoordinateReferenceSystem] = None
    radius_m: float = DEFAULT_AOI_RADIUS_M
    width_m: float = DEFAULT_AOI_WIDTH_M
    height_m: float = DEFAULT_AOI_HEIGHT_M
    manual_extent: Optional[QgsRectangle] = None
    manual_extent_crs: Optional[QgsCoordinateReferenceSystem] = None
    layer: Optional[QgsVectorLayer] = None


@dataclass
class AOIResult:
    """
    Result of AOI creation.

    Attributes:
        extent: Bounding rectangle in *crs*.
        crs: CRS of the extent.
        width_m: Approximate width in metres.
        height_m: Approximate height in metres.
        success: Whether creation succeeded.
        error_message: Human-readable error on failure.
    """

    extent: Optional[QgsRectangle] = None
    crs: Optional[QgsCoordinateReferenceSystem] = None
    width_m: float = 0.0
    height_m: float = 0.0
    success: bool = True
    error_message: str = ""


class AOIManager:
    """
    Creates and validates Area of Interest extents.

    All distance-based methods (RADIUS, RECTANGLE) work in a projected
    CRS to avoid the distortion of calculating distances in degrees.
    """

    def create_aoi(
        self,
        params: AOIParameters,
        output_crs: Optional[QgsCoordinateReferenceSystem] = None,
    ) -> AOIResult:
        """
        Build an AOI extent according to *params*.

        Args:
            params: AOI creation parameters.
            output_crs: Desired CRS for the returned extent.
                        If None, a suitable projected CRS is chosen automatically.

        Returns:
            AOIResult with the computed extent.
        """
        try:
            if params.method == AOIMethod.RADIUS:
                return self._from_radius(params, output_crs)
            elif params.method == AOIMethod.RECTANGLE:
                return self._from_rectangle(params, output_crs)
            elif params.method in (AOIMethod.CURRENT_EXTENT, AOIMethod.DRAW_ON_MAP):
                return self._from_manual_extent(params, output_crs)
            elif params.method == AOIMethod.FROM_LAYER:
                return self._from_layer(params, output_crs)
            else:
                return AOIResult(
                    success=False,
                    error_message=f"Unknown AOI method: {params.method}",
                )
        except Exception as exc:
            msg = f"AOI creation failed: {exc}"
            logger.error(msg)
            return AOIResult(success=False, error_message=msg)

    # ------------------------------------------------------------------
    # Method implementations
    # ------------------------------------------------------------------

    def _from_radius(
        self,
        params: AOIParameters,
        output_crs: Optional[QgsCoordinateReferenceSystem],
    ) -> AOIResult:
        """Create a square AOI from a point + radius."""
        if params.center is None:
            return AOIResult(success=False, error_message="Centre point is required for radius AOI.")

        center_crs = params.center_crs or QgsCoordinateReferenceSystem("EPSG:4326")
        metric_crs = suggested_metric_crs(params.center, center_crs)

        # Project centre to metric CRS
        center_m = transform_point(params.center, center_crs, metric_crs)

        r = params.radius_m
        extent_m = QgsRectangle(
            center_m.x() - r,
            center_m.y() - r,
            center_m.x() + r,
            center_m.y() + r,
        )

        # Transform to output CRS if needed
        final_crs = output_crs or metric_crs
        final_extent = transform_extent(extent_m, metric_crs, final_crs)

        logger.info(
            f"AOI (radius {r} m) → {final_extent.width():.2f}×"
            f"{final_extent.height():.2f} in {final_crs.authid()}"
        )

        return AOIResult(
            extent=final_extent,
            crs=final_crs,
            width_m=r * 2,
            height_m=r * 2,
        )

    def _from_rectangle(
        self,
        params: AOIParameters,
        output_crs: Optional[QgsCoordinateReferenceSystem],
    ) -> AOIResult:
        """Create a rectangular AOI from a point + width/height."""
        if params.center is None:
            return AOIResult(success=False, error_message="Centre point is required for rectangle AOI.")

        center_crs = params.center_crs or QgsCoordinateReferenceSystem("EPSG:4326")
        metric_crs = suggested_metric_crs(params.center, center_crs)

        center_m = transform_point(params.center, center_crs, metric_crs)

        hw = params.width_m / 2.0
        hh = params.height_m / 2.0
        extent_m = QgsRectangle(
            center_m.x() - hw,
            center_m.y() - hh,
            center_m.x() + hw,
            center_m.y() + hh,
        )

        final_crs = output_crs or metric_crs
        final_extent = transform_extent(extent_m, metric_crs, final_crs)

        logger.info(
            f"AOI (rect {params.width_m}×{params.height_m} m) → "
            f"{final_extent.width():.2f}×{final_extent.height():.2f} "
            f"in {final_crs.authid()}"
        )

        return AOIResult(
            extent=final_extent,
            crs=final_crs,
            width_m=params.width_m,
            height_m=params.height_m,
        )

    def _from_manual_extent(
        self,
        params: AOIParameters,
        output_crs: Optional[QgsCoordinateReferenceSystem],
    ) -> AOIResult:
        """Use a manually specified or drawn extent."""
        if params.manual_extent is None or params.manual_extent.isEmpty():
            return AOIResult(success=False, error_message="Manual extent is empty.")

        extent_crs = params.manual_extent_crs or QgsProject.instance().crs()
        final_crs = output_crs or extent_crs
        final_extent = transform_extent(params.manual_extent, extent_crs, final_crs)

        # Estimate metric dimensions
        from .crs_utils import extent_dimensions_metres
        w_m, h_m = extent_dimensions_metres(final_extent, final_crs)

        logger.info(
            f"AOI (manual extent) → {w_m:.0f}×{h_m:.0f} m in {final_crs.authid()}"
        )

        return AOIResult(
            extent=final_extent,
            crs=final_crs,
            width_m=w_m,
            height_m=h_m,
        )

    def _from_layer(
        self,
        params: AOIParameters,
        output_crs: Optional[QgsCoordinateReferenceSystem],
    ) -> AOIResult:
        """Use the extent of an existing vector/raster layer."""
        if params.layer is None:
            return AOIResult(success=False, error_message="No layer provided for AOI.")

        layer_extent = params.layer.extent()
        if layer_extent.isEmpty():
            return AOIResult(
                success=False,
                error_message=f"Layer '{params.layer.name()}' has an empty extent.",
            )

        layer_crs = params.layer.crs()
        final_crs = output_crs or layer_crs
        final_extent = transform_extent(layer_extent, layer_crs, final_crs)

        from .crs_utils import extent_dimensions_metres
        w_m, h_m = extent_dimensions_metres(final_extent, final_crs)

        logger.info(
            f"AOI (from layer '{params.layer.name()}') → "
            f"{w_m:.0f}×{h_m:.0f} m in {final_crs.authid()}"
        )

        return AOIResult(
            extent=final_extent,
            crs=final_crs,
            width_m=w_m,
            height_m=h_m,
        )
