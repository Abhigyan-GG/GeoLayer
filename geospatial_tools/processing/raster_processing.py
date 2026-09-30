"""
GeoSpatial Tools — Future Raster Processing Interface.

Defines the contract and extensible pipeline for post-processing
generated GeoTIFF rasters (clipping, reprojection, resampling,
normalization, enhancement).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from qgis.core import QgsRectangle


@dataclass
class RasterProcessingConfig:
    """Configuration options for raster operations."""
    clip_extent: Optional[QgsRectangle] = None
    target_crs_auth: Optional[str] = None
    resampling_method: str = "nearest"  # bilinear, cubic, lanczos
    normalize: bool = False
    denoise: bool = False
    custom_params: Dict[str, Any] = None


class BaseRasterProcessor(ABC):
    """
    Abstract base class for downstream raster operations.
    Decoupled from OpenCV / ML dependencies so core plugin remains lightweight.
    """

    @abstractmethod
    def process(
        self,
        input_raster_path: str,
        output_raster_path: str,
        config: Optional[RasterProcessingConfig] = None,
    ) -> bool:
        """Process an input GeoTIFF and write the result."""
        pass
