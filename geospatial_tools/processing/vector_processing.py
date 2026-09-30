"""
GeoSpatial Tools — Future Vector Processing Interface.

Provides interfaces and pipelines for converting extracted raster features
into validated GIS vector layers (GeoPackage, Shapefile, GeoJSON).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class VectorProcessingConfig:
    """Configuration for vector geometry operations."""
    simplify_tolerance: float = 0.0
    buffer_distance: float = 0.0
    min_area_filter: float = 0.0
    dissolve: bool = False
    target_crs_auth: Optional[str] = None
    output_format: str = "GPKG"  # GPKG, GeoJSON, SHP


class BaseVectorProcessor(ABC):
    """
    Abstract interface for transforming geometries into vector layers.
    """

    @abstractmethod
    def vectorize_features(
        self,
        pixel_contours: List[Any],
        geotransform: tuple,
        crs_wkt: str,
        output_vector_path: str,
        config: Optional[VectorProcessingConfig] = None,
    ) -> bool:
        """Convert pixel contours into a georeferenced vector dataset."""
        pass
