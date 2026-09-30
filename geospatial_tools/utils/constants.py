"""
GeoSpatial Tools — Plugin Constants & Defaults.

Centralizes all magic numbers, default values, and safety limits
so they are never scattered across the codebase.
"""

# ---------------------------------------------------------------------------
# Plugin identity
# ---------------------------------------------------------------------------
PLUGIN_NAME = "GeoSpatial Tools"
PLUGIN_VERSION = "0.1.0"
PLUGIN_TAG = "GeoSpatialTools"

# ---------------------------------------------------------------------------
# Rendering defaults
# ---------------------------------------------------------------------------
DEFAULT_DPI = 96
DEFAULT_RESOLUTION_M = 1.0  # metres per pixel
MIN_RESOLUTION_M = 0.01     # 1 cm — practical lower bound
MAX_RESOLUTION_M = 10000.0  # 10 km — practical upper bound

# ---------------------------------------------------------------------------
# Output safety limits
# ---------------------------------------------------------------------------
MAX_RASTER_DIMENSION = 40_000           # pixels in either axis
MAX_PIXEL_COUNT = 400_000_000           # ~400 MP
MAX_ESTIMATED_MEMORY_BYTES = 4_000_000_000  # 4 GB
BYTES_PER_PIXEL_RGBA = 4               # 8-bit RGBA

# ---------------------------------------------------------------------------
# GeoTIFF defaults
# ---------------------------------------------------------------------------
COMPRESSION_OPTIONS = ["DEFLATE", "LZW", "ZSTD", "NONE"]
DEFAULT_COMPRESSION = "DEFLATE"
DEFAULT_TILED = True
DEFAULT_TILE_SIZE = 256
DEFAULT_BIGTIFF = "IF_SAFER"
GEOTIFF_DRIVER_NAME = "GTiff"
BAND_COUNT_RGB = 3
BAND_COUNT_RGBA = 4

# ---------------------------------------------------------------------------
# AOI defaults
# ---------------------------------------------------------------------------
DEFAULT_AOI_RADIUS_M = 500.0
DEFAULT_AOI_WIDTH_M = 1000.0
DEFAULT_AOI_HEIGHT_M = 1000.0

# ---------------------------------------------------------------------------
# Geocoder defaults
# ---------------------------------------------------------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
GEOCODER_TIMEOUT_S = 10
GEOCODER_MAX_RETRIES = 2
GEOCODER_USER_AGENT = "QGIS-GeoSpatialTools/0.1 (Plugin)"
GEOCODER_RATE_LIMIT_S = 1.1  # Nominatim asks for ≥1 s between requests

# ---------------------------------------------------------------------------
# Validation tolerances
# ---------------------------------------------------------------------------
EXTENT_TOLERANCE_FRACTION = 1e-6   # relative tolerance for extent checks
TRANSFORM_TOLERANCE_ABS = 1e-8     # absolute tolerance for affine values

# ---------------------------------------------------------------------------
# Coordinate regex for direct-input detection
# ---------------------------------------------------------------------------
COORDINATE_REGEX = (
    r"^\s*"
    r"(?P<lat>[+-]?\d+\.?\d*)"
    r"\s*[,;\s]\s*"
    r"(?P<lon>[+-]?\d+\.?\d*)"
    r"\s*$"
)

# ---------------------------------------------------------------------------
# QGIS layer group name for generated outputs
# ---------------------------------------------------------------------------
OUTPUT_GROUP_NAME = "GeoSpatial Tools — Exports"
