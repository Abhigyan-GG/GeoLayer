"""Project-backed POI point storage."""

import json
import math
import os
import re
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .geocoder import GeocodingResult
from ..utils.plugin_logger import get_logger

logger = get_logger()

LAYER_NAME = "GeoSpatial Tools Data Points"
LAYER_PROPERTY = "geospatial_tools/data_points"


class DataPointsManager:
    """Create, update, remove, and persist POI features in a project layer."""

    def __init__(self) -> None:
        self._layer_id: Optional[str] = None

    def current_layer(self) -> Optional[QgsVectorLayer]:
        """Resolve the managed point layer from the current project."""
        return self._resolve_layer()

    def _resolve_layer(self, create: bool = False) -> Optional[QgsVectorLayer]:
        project = QgsProject.instance()
        if self._layer_id:
            layer = project.mapLayer(self._layer_id)
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                return layer

        for candidate in project.mapLayers().values():
            if (
                isinstance(candidate, QgsVectorLayer)
                and candidate.isValid()
                and candidate.customProperty(LAYER_PROPERTY, False)
            ):
                self._layer_id = candidate.id()
                return candidate

        if not create:
            return None
        layer = QgsVectorLayer("Point?crs=EPSG:4326", LAYER_NAME, "memory")
        if not layer.isValid():
            raise RuntimeError("Could not create the POI data-points layer.")
        layer.setCustomProperty(LAYER_PROPERTY, True)
        layer.dataProvider().addAttributes([
            QgsField("name", QVariant.String),
            QgsField("latitude", QVariant.Double),
            QgsField("longitude", QVariant.Double),
            QgsField("address", QVariant.String),
            QgsField("category", QVariant.String),
            QgsField("subcategory", QVariant.String),
            QgsField("phone", QVariant.String),
            QgsField("website", QVariant.String),
            QgsField("opening_hours", QVariant.String),
            QgsField("provider", QVariant.String),
            QgsField("provider_id", QVariant.String),
            QgsField("raw_metadata", QVariant.String),
        ])
        layer.updateFields()
        project.addMapLayer(layer)
        self._layer_id = layer.id()
        return layer

    def add_result(self, result: GeocodingResult) -> Dict[str, object]:
        """Add a result unless an equivalent provider ID or nearby name exists."""
        layer = self._resolve_layer(create=True)
        provider_index = layer.fields().indexFromName("provider_id")
        name_index = layer.fields().indexFromName("name")
        lat_index = layer.fields().indexFromName("latitude")
        lon_index = layer.fields().indexFromName("longitude")
        normalized_name = self._normalize_name(result.name or result.display_name)
        for feature in layer.getFeatures():
            provider_id = str(feature[provider_index] or "")
            if result.provider_id and provider_id == result.provider_id:
                return {"added": False, "feature_id": feature.id(), "reason": "duplicate"}
            feature_name = self._normalize_name(str(feature[name_index] or ""))
            if (
                (not result.provider_id or not provider_id)
                and feature_name == normalized_name
                and self._distance_metres(
                    result.latitude, result.longitude,
                    float(feature[lat_index]), float(feature[lon_index]),
                ) <= 15.0
            ):
                return {"added": False, "feature_id": feature.id(), "reason": "duplicate"}

        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(
            QgsPointXY(result.longitude, result.latitude)
        ))
        address = result.display_name or ", ".join(result.address.values())
        raw_metadata = json.dumps(
            {"metadata": result.metadata, "raw": result.raw},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        feature.setAttributes([
            result.name or result.display_name,
            result.latitude,
            result.longitude,
            address,
            result.category,
            result.subcategory,
            result.phone,
            result.website,
            result.opening_hours,
            result.source,
            result.provider_id,
            raw_metadata,
        ])
        success, added = layer.dataProvider().addFeatures([feature])
        if not success or not added:
            raise RuntimeError("QGIS could not add the POI point feature.")
        layer.updateExtents()
        layer.triggerRepaint()
        return {"added": True, "feature_id": added[0].id(), "reason": "added"}

    def delete_feature(self, feature_id: int) -> bool:
        """Delete one stored point without removing its layer."""
        layer = self._resolve_layer()
        if layer is None:
            return False
        deleted = layer.dataProvider().deleteFeatures([feature_id])
        if deleted:
            layer.updateExtents()
            layer.triggerRepaint()
        return bool(deleted)

    def list_points(self) -> List[Dict[str, object]]:
        """Return detached dictionaries for the current data-point features."""
        layer = self._resolve_layer()
        if layer is None:
            return []
        return [
            {"feature_id": feature.id(), "name": str(feature["name"] or ""),
             "latitude": float(feature["latitude"]),
             "longitude": float(feature["longitude"])}
            for feature in layer.getFeatures()
        ]

    def save_as(self, path: str) -> str:
        """Write the current points to a GeoPackage and load it in the project."""
        layer = self._resolve_layer()
        if layer is None:
            raise ValueError("There are no data points to save.")
        output_path = os.path.normpath(path)
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = "UTF-8"
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, output_path, QgsProject.instance().transformContext(), options
        )
        writer_error = getattr(QgsVectorFileWriter, "WriterError", None)
        no_error = getattr(
            QgsVectorFileWriter,
            "NoError",
            getattr(writer_error, "NoError", 0),
        )
        if result[0] != no_error:
            raise RuntimeError(str(result[1]))
        saved = QgsVectorLayer(output_path, os.path.splitext(os.path.basename(path))[0], "ogr")
        if not saved.isValid():
            raise RuntimeError("The saved GeoPackage could not be loaded in QGIS.")
        saved.setCustomProperty(LAYER_PROPERTY, True)
        QgsProject.instance().addMapLayer(saved)
        if layer.id() != saved.id():
            QgsProject.instance().removeMapLayer(layer.id())
        self._layer_id = saved.id()
        return output_path

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"\s+", " ", name.casefold()).strip()

    @staticmethod
    def _distance_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371008.8
        lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        value = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad)
            * math.sin(delta_lon / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))