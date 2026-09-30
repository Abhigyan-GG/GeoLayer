"""
GeoSpatial Tools — GeoTIFF Validation.

Reopens a generated GeoTIFF through GDAL and verifies that its
CRS, extent, dimensions, affine transform, and band count match
the expected values.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

from osgeo import gdal, osr
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle

from .georeferencing import GeoReference, GeoTransform, extent_from_geotransform
from ..utils.constants import EXTENT_TOLERANCE_FRACTION, TRANSFORM_TOLERANCE_ABS
from ..utils.plugin_logger import get_logger

logger = get_logger()


@dataclass
class ValidationResult:
    """
    Outcome of a GeoTIFF validation pass.

    Attributes:
        valid: True if all checks passed.
        checks: List of individual check outcomes.
        errors: List of error descriptions (empty when valid).
        warnings: List of non-fatal warnings.
    """

    valid: bool = True
    checks: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_pass(self, description: str) -> None:
        self.checks.append(f"✓ {description}")

    def add_fail(self, description: str) -> None:
        self.valid = False
        self.checks.append(f"✗ {description}")
        self.errors.append(description)

    def add_warning(self, description: str) -> None:
        self.checks.append(f"⚠ {description}")
        self.warnings.append(description)

    @property
    def summary(self) -> str:
        status = "PASSED" if self.valid else "FAILED"
        lines = [f"Validation {status}"]
        lines.extend(self.checks)
        return "\n".join(lines)


class GeoTiffValidator:
    """
    Validates a GeoTIFF file against expected georeferencing metadata.

    Opens the file independently through GDAL (not through the same
    handle that wrote it) to ensure the file is self-contained and
    correctly persisted.
    """

    def validate(
        self,
        path: str,
        expected: GeoReference,
        expected_bands: int = 3,
    ) -> ValidationResult:
        """
        Run all validation checks on *path*.

        Args:
            path: Path to the GeoTIFF file.
            expected: Expected georeferencing information.
            expected_bands: Expected band count.

        Returns:
            ValidationResult summarising pass/fail.
        """
        result = ValidationResult()

        # 1. File exists
        if not os.path.isfile(path):
            result.add_fail(f"File does not exist: {path}")
            return result
        result.add_pass("File exists")

        # 2. GDAL can open it
        ds = gdal.Open(path, gdal.GA_ReadOnly)
        if ds is None:
            result.add_fail("GDAL cannot open the file")
            return result
        result.add_pass("File opens in GDAL")

        try:
            self._check_dimensions(ds, expected, result)
            self._check_bands(ds, expected_bands, result)
            self._check_crs(ds, expected, result)
            self._check_transform(ds, expected, result)
            self._check_extent(ds, expected, result)
        finally:
            ds = None  # Close dataset

        if result.valid:
            logger.info(f"Validation PASSED for {path}")
        else:
            logger.warning(
                f"Validation FAILED for {path}: "
                + "; ".join(result.errors)
            )

        return result

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_dimensions(
        ds: gdal.Dataset,
        expected: GeoReference,
        result: ValidationResult,
    ) -> None:
        actual_w = ds.RasterXSize
        actual_h = ds.RasterYSize
        if actual_w == expected.width and actual_h == expected.height:
            result.add_pass(
                f"Dimensions match: {actual_w}×{actual_h}"
            )
        else:
            result.add_fail(
                f"Dimensions mismatch: expected {expected.width}×{expected.height}, "
                f"got {actual_w}×{actual_h}"
            )

    @staticmethod
    def _check_bands(
        ds: gdal.Dataset,
        expected_bands: int,
        result: ValidationResult,
    ) -> None:
        actual = ds.RasterCount
        if actual == expected_bands:
            result.add_pass(f"Band count matches: {actual}")
        elif actual > 0:
            result.add_warning(
                f"Band count differs: expected {expected_bands}, got {actual}"
            )
        else:
            result.add_fail("No raster bands found")

    @staticmethod
    def _check_crs(
        ds: gdal.Dataset,
        expected: GeoReference,
        result: ValidationResult,
    ) -> None:
        proj_wkt = ds.GetProjection()
        if not proj_wkt:
            result.add_fail("No CRS/projection found in GeoTIFF")
            return

        # Compare via QGIS CRS objects for robust matching
        actual_crs = QgsCoordinateReferenceSystem.fromWkt(proj_wkt)
        if not actual_crs.isValid():
            result.add_fail(f"CRS WKT is present but invalid")
            return

        # Compare authority IDs if available
        expected_auth = expected.crs.authid()
        actual_auth = actual_crs.authid()

        if expected_auth and actual_auth and expected_auth == actual_auth:
            result.add_pass(f"CRS matches: {actual_auth}")
        elif expected_auth and actual_auth:
            # They might still be equivalent CRS with different auth codes
            result.add_warning(
                f"CRS authority differs: expected {expected_auth}, got {actual_auth}. "
                f"They may still be equivalent."
            )
        else:
            result.add_pass("CRS WKT is present")

    @staticmethod
    def _check_transform(
        ds: gdal.Dataset,
        expected: GeoReference,
        result: ValidationResult,
    ) -> None:
        actual_gt = ds.GetGeoTransform()
        expected_gt = expected.transform.to_gdal_tuple()

        if actual_gt is None:
            result.add_fail("No GeoTransform found")
            return

        all_close = True
        for i, (a, e) in enumerate(zip(actual_gt, expected_gt)):
            if abs(a - e) > TRANSFORM_TOLERANCE_ABS:
                all_close = False
                break

        if all_close:
            result.add_pass("GeoTransform matches expected values")
        else:
            result.add_fail(
                f"GeoTransform mismatch:\n"
                f"  expected: {expected_gt}\n"
                f"  actual:   {actual_gt}"
            )

    @staticmethod
    def _check_extent(
        ds: gdal.Dataset,
        expected: GeoReference,
        result: ValidationResult,
    ) -> None:
        gt = ds.GetGeoTransform()
        if gt is None:
            return  # Already flagged in _check_transform

        actual_gt = GeoTransform(*gt)
        actual_extent = extent_from_geotransform(
            actual_gt, ds.RasterXSize, ds.RasterYSize
        )
        exp = expected.extent

        # Compare using relative tolerance
        def close(a: float, b: float) -> bool:
            denom = max(abs(a), abs(b), 1e-10)
            return abs(a - b) / denom < EXTENT_TOLERANCE_FRACTION

        if (
            close(actual_extent.xMinimum(), exp.xMinimum())
            and close(actual_extent.yMinimum(), exp.yMinimum())
            and close(actual_extent.xMaximum(), exp.xMaximum())
            and close(actual_extent.yMaximum(), exp.yMaximum())
        ):
            result.add_pass("Extent matches AOI")
        else:
            result.add_fail(
                f"Extent mismatch:\n"
                f"  expected: ({exp.xMinimum():.6f}, {exp.yMinimum():.6f}) → "
                f"({exp.xMaximum():.6f}, {exp.yMaximum():.6f})\n"
                f"  actual:   ({actual_extent.xMinimum():.6f}, "
                f"{actual_extent.yMinimum():.6f}) → "
                f"({actual_extent.xMaximum():.6f}, "
                f"{actual_extent.yMaximum():.6f})"
            )
