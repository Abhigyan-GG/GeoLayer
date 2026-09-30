"""
GeoSpatial Tools — Raster Writer.

Converts a rendered QImage into a properly georeferenced GeoTIFF using GDAL.
Supports configurable compression, tiling, and BigTIFF.
"""

import os
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from osgeo import gdal, osr
from qgis.PyQt.QtGui import QImage

from .georeferencing import GeoReference
from ..utils.constants import (
    BAND_COUNT_RGB,
    BAND_COUNT_RGBA,
    DEFAULT_BIGTIFF,
    DEFAULT_COMPRESSION,
    DEFAULT_TILE_SIZE,
    DEFAULT_TILED,
    GEOTIFF_DRIVER_NAME,
)
from ..utils.helpers import ensure_directory, timestamp_string
from ..utils.plugin_logger import get_logger

logger = get_logger()


@dataclass
class WriteOptions:
    """
    Configuration for GeoTIFF output.

    Attributes:
        compression: GDAL compression algorithm name.
        tiled: Whether to use tiled storage.
        tile_size: Tile width/height when tiling is enabled.
        bigtiff: GDAL BigTIFF setting ('YES', 'NO', 'IF_NEEDED', 'IF_SAFER').
        include_alpha: Whether to write the alpha band.
        metadata: Extra key=value metadata to embed in the GeoTIFF.
    """

    compression: str = DEFAULT_COMPRESSION
    tiled: bool = DEFAULT_TILED
    tile_size: int = DEFAULT_TILE_SIZE
    bigtiff: str = DEFAULT_BIGTIFF
    include_alpha: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class WriteResult:
    """
    Outcome of a GeoTIFF write operation.

    Attributes:
        success: Whether the file was written successfully.
        path: Absolute path to the output file.
        error_message: Human-readable error (empty on success).
        file_size_bytes: Size of the written file in bytes.
    """

    success: bool
    path: str
    error_message: str = ""
    file_size_bytes: int = 0


class RasterWriter:
    """
    Writes a QImage + GeoReference to a GeoTIFF file via GDAL.

    This is a pure write operation — no rendering or screen capture.
    """

    def write(
        self,
        image: QImage,
        georef: GeoReference,
        output_path: str,
        options: Optional[WriteOptions] = None,
    ) -> WriteResult:
        """
        Write a rendered QImage as a georeferenced GeoTIFF.

        Args:
            image: Rendered QImage (expected ARGB32 or ARGB32_Premultiplied).
            georef: Complete georeferencing information.
            output_path: Destination file path.
            options: Write options (compression, tiling, etc.).

        Returns:
            WriteResult indicating success/failure.
        """
        if options is None:
            options = WriteOptions()

        try:
            return self._write_impl(image, georef, output_path, options)
        except Exception as exc:
            msg = f"GeoTIFF write failed: {exc}"
            logger.error(msg)
            return WriteResult(success=False, path=output_path, error_message=msg)

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _write_impl(
        self,
        image: QImage,
        georef: GeoReference,
        output_path: str,
        options: WriteOptions,
    ) -> WriteResult:
        """Core write logic — separated for clean exception handling."""

        # Ensure output directory exists
        ensure_directory(output_path)

        # Convert QImage → numpy array
        array = self._qimage_to_numpy(image)
        if array is None:
            return WriteResult(
                success=False,
                path=output_path,
                error_message="Failed to convert QImage to numpy array.",
            )

        height, width = array.shape[:2]

        # Validate dimensions against georef
        if width != georef.width or height != georef.height:
            logger.warning(
                f"Image dimensions ({width}×{height}) differ from georef "
                f"({georef.width}×{georef.height}). Using image dimensions."
            )

        # Decide band count
        has_alpha = array.shape[2] == 4 if len(array.shape) == 3 else False
        if options.include_alpha and has_alpha:
            band_count = BAND_COUNT_RGBA
        else:
            band_count = BAND_COUNT_RGB

        # Build GDAL creation options
        creation_opts = self._build_creation_options(options)

        logger.info(
            f"Writing GeoTIFF: {width}×{height}, {band_count} bands, "
            f"compression={options.compression}, path={output_path}"
        )

        # Create GDAL dataset
        driver = gdal.GetDriverByName(GEOTIFF_DRIVER_NAME)
        if driver is None:
            gdal.AllRegister()
            driver = gdal.GetDriverByName(GEOTIFF_DRIVER_NAME)

        if driver is None:
            return WriteResult(
                success=False,
                path=output_path,
                error_message="GDAL GTiff driver not available.",
            )

        ds = driver.Create(
            output_path,
            width,
            height,
            band_count,
            gdal.GDT_Byte,
            creation_opts,
        )
        if ds is None:
            return WriteResult(
                success=False,
                path=output_path,
                error_message=f"GDAL failed to create dataset at {output_path}.",
            )

        # Set georeferencing
        ds.SetGeoTransform(georef.transform.to_gdal_tuple())

        # Set CRS via spatial reference
        srs = osr.SpatialReference()
        srs.ImportFromWkt(georef.crs_wkt)
        ds.SetProjection(srs.ExportToWkt())

        # Write bands (R, G, B, optionally A)
        # numpy array is (H, W, C) in RGBA order after conversion
        for band_idx in range(band_count):
            band = ds.GetRasterBand(band_idx + 1)
            band.WriteArray(array[:, :, band_idx])
            band.FlushCache()

        # Set metadata
        meta = self._build_metadata(georef, options)
        ds.SetMetadata(meta)

        # Flush and close
        ds.FlushCache()
        ds = None  # Explicitly close the GDAL dataset

        # Verify file was written
        if not os.path.isfile(output_path):
            return WriteResult(
                success=False,
                path=output_path,
                error_message="GeoTIFF file was not created on disk.",
            )

        file_size = os.path.getsize(output_path)
        logger.info(
            f"GeoTIFF written successfully: {output_path} "
            f"({file_size:,} bytes)"
        )

        return WriteResult(
            success=True,
            path=output_path,
            file_size_bytes=file_size,
        )

    @staticmethod
    def _qimage_to_numpy(image: QImage) -> Optional[np.ndarray]:
        """
        Convert a QImage to a numpy array with shape (H, W, 4) in RGBA order.

        QImage stores pixels as ARGB (or BGRA in memory on little-endian).
        This method normalises to RGBA.
        """
        # Support both Qt5 and Qt6 enum namespace
        fmt = getattr(QImage, "Format_ARGB32", getattr(QImage.Format, "Format_ARGB32", None))
        img = image.convertToFormat(fmt)

        width = img.width()
        height = img.height()

        # Access raw pixel data
        ptr = img.bits()
        if ptr is None:
            return None

        ptr.setsize(height * width * 4)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4)).copy()

        # QImage ARGB32 is stored as BGRA in memory (little-endian)
        # Reorder to RGBA: swap B and R channels
        rgba = np.empty_like(arr)
        rgba[:, :, 0] = arr[:, :, 2]  # R ← B position
        rgba[:, :, 1] = arr[:, :, 1]  # G
        rgba[:, :, 2] = arr[:, :, 0]  # B ← R position
        rgba[:, :, 3] = arr[:, :, 3]  # A

        return rgba

    @staticmethod
    def _build_creation_options(options: WriteOptions) -> List[str]:
        """Build the GDAL creation options list."""
        opts = []

        if options.compression and options.compression.upper() != "NONE":
            opts.append(f"COMPRESS={options.compression.upper()}")

        if options.tiled:
            opts.append("TILED=YES")
            opts.append(f"BLOCKXSIZE={options.tile_size}")
            opts.append(f"BLOCKYSIZE={options.tile_size}")

        opts.append(f"BIGTIFF={options.bigtiff}")

        return opts

    @staticmethod
    def _build_metadata(
        georef: GeoReference, options: WriteOptions
    ) -> dict:
        """Build the metadata dictionary to embed in the GeoTIFF."""
        meta = {
            "PLUGIN": "GeoSpatial Tools",
            "CREATION_TIME": timestamp_string(),
            "CRS_AUTH": georef.crs.authid() or "Unknown",
            "EXTENT_XMIN": str(georef.extent.xMinimum()),
            "EXTENT_YMIN": str(georef.extent.yMinimum()),
            "EXTENT_XMAX": str(georef.extent.xMaximum()),
            "EXTENT_YMAX": str(georef.extent.yMaximum()),
            "PIXEL_SIZE_X": str(georef.pixel_size_x),
            "PIXEL_SIZE_Y": str(georef.pixel_size_y),
            "COMPRESSION": options.compression,
        }
        # Merge user-supplied metadata
        meta.update(options.metadata)
        return meta
