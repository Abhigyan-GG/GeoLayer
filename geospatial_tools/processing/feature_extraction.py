"""
GeoSpatial Tools — Feature Extraction Interface.

Decoupled architecture for computer-vision and ML-based feature
extraction (contours, building footprints, road networks, land cover).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExtractionMethod(Enum):
    """Extraction paradigm."""
    CLASSICAL_CV = "classical_cv"
    SEMANTIC_SEGMENTATION = "semantic_segmentation"
    OBJECT_DETECTION = "object_detection"
    CUSTOM = "custom"


@dataclass
class ExtractedFeature:
    """
    Representation of a detected feature in pixel and/or geographic space.
    """
    feature_id: int
    class_name: str
    confidence: float
    pixel_polygon: List[tuple] = field(default_factory=list)
    geo_polygon: Optional[Any] = None
    properties: Dict[str, Any] = field(default_factory=dict)


class BaseFeatureExtractor(ABC):
    """
    Abstract interface for feature extractors.
    Allows plug-and-play addition of OpenCV, PyTorch, ONNX, or scikit-image algorithms.
    """

    @property
    @abstractmethod
    def method(self) -> ExtractionMethod:
        """Return the extraction paradigm used."""
        pass

    @abstractmethod
    def extract(
        self,
        raster_path: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[ExtractedFeature]:
        """Extract features from a georeferenced raster."""
        pass
