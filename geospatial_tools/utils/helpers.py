"""
GeoSpatial Tools — Helper Utilities.

Small, pure-Python helper functions for path handling, size formatting,
safe filename generation, and memory estimation.
"""

import os
import re
import math
from datetime import datetime, timezone
from typing import Tuple

from .constants import BYTES_PER_PIXEL_RGBA


def format_file_size(size_bytes: int) -> str:
    """
    Format a byte count into a human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string such as "12.3 MB".
    """
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    value = float(size_bytes)
    while value >= 1024.0 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(value)} B"
    return f"{value:.1f} {units[idx]}"


def estimate_raster_memory(width: int, height: int,
                           bands: int = 4) -> int:
    """
    Estimate raw memory for a raster in bytes (uncompressed).

    Args:
        width: Raster width in pixels.
        height: Raster height in pixels.
        bands: Number of bands (default 4 for RGBA).

    Returns:
        Estimated memory in bytes.
    """
    return width * height * bands


def estimate_output_size(width: int, height: int,
                         bands: int = 4,
                         compression_ratio: float = 0.5) -> int:
    """
    Rough estimate of compressed GeoTIFF size on disk.

    Args:
        width: Raster width in pixels.
        height: Raster height in pixels.
        bands: Number of bands.
        compression_ratio: Expected ratio (0.5 = 50 % of raw).

    Returns:
        Estimated file size in bytes.
    """
    raw = estimate_raster_memory(width, height, bands)
    return int(raw * compression_ratio)


def compute_pixel_dimensions(
    aoi_width_m: float,
    aoi_height_m: float,
    resolution_m: float,
) -> Tuple[int, int]:
    """
    Calculate output raster dimensions from AOI size and resolution.

    Args:
        aoi_width_m: AOI width in metres.
        aoi_height_m: AOI height in metres.
        resolution_m: Desired metres per pixel.

    Returns:
        (width_pixels, height_pixels) — both ≥ 1.
    """
    w = max(1, math.ceil(aoi_width_m / resolution_m))
    h = max(1, math.ceil(aoi_height_m / resolution_m))
    return w, h


def safe_filename(name: str, extension: str = ".tif") -> str:
    """
    Convert an arbitrary string into a filesystem-safe filename.

    Args:
        name: Raw name (e.g., location display name).
        extension: File extension including dot.

    Returns:
        Sanitised filename.
    """
    # Replace non-alphanumeric (except spaces, hyphens, underscores) with '_'
    clean = re.sub(r"[^\w\s\-]", "_", name, flags=re.UNICODE)
    # Collapse whitespace/underscores
    clean = re.sub(r"[\s_]+", "_", clean).strip("_")
    if not clean:
        clean = "export"
    return clean + extension


def ensure_directory(path: str) -> str:
    """
    Ensure the parent directory of *path* exists.

    Args:
        path: Target file path.

    Returns:
        The directory path that was created / verified.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return directory


def timestamp_string() -> str:
    """Return an ISO-8601 UTC timestamp for metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_output_path(location_name: str = "export",
                        directory: str = "") -> str:
    """
    Build a default output file path.

    Args:
        location_name: Human-readable location for the filename.
        directory: Output directory; defaults to user's home/GIS_exports.

    Returns:
        Full absolute path.
    """
    if not directory:
        directory = os.path.join(os.path.expanduser("~"), "GIS_exports")
    os.makedirs(directory, exist_ok=True)
    fname = safe_filename(location_name)
    return os.path.join(directory, fname)
