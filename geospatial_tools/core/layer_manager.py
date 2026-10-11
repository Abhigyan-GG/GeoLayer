"""
GeoSpatial Tools — Layer Manager.

Queries the current QGIS project's layer tree and provides helpers for
selecting, ordering, and filtering layers for rendering.
"""

from dataclasses import dataclass
from typing import List, Optional

from qgis.core import (
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsLayerTreeLayer,
)

from ..utils.plugin_logger import get_logger

logger = get_logger()


@dataclass
class LayerInfo:
    """
    Lightweight descriptor for a QGIS layer.

    Attributes:
        layer_id: QGIS internal layer ID.
        name: Display name.
        layer_type: 'raster' or 'vector'.
        provider: Data provider key (e.g. 'wms', 'gdal', 'ogr').
        crs_auth: CRS authority code (e.g. 'EPSG:4326').
        visible: Whether the layer is currently visible in the layer tree.
    """

    layer_id: str
    name: str
    layer_type: str
    provider: str
    crs_auth: str
    visible: bool


class LayerManager:
    """
    Manages the enumeration and selection of QGIS project layers.

    Uses the QgsProject layer tree APIs rather than duplicating data.
    """

    def get_all_layers(self) -> List[LayerInfo]:
        """
        Return information about all layers in the current QGIS project.

        Returns:
            List of LayerInfo descriptors, ordered as they appear
            in the layer tree (top → bottom).
        """
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        infos: List[LayerInfo] = []

        for node in root.findLayers():
            layer = node.layer()
            if layer is None or not layer.isValid():
                continue
            infos.append(self._make_info(layer, self._is_effectively_visible(node)))

        return infos

    def get_visible_layers(self) -> List[LayerInfo]:
        """Return only layers that are currently visible."""
        return [li for li in self.get_all_layers() if li.visible]

    def get_layers_by_ids(
        self, layer_ids: List[str]
    ) -> List[QgsMapLayer]:
        """
        Resolve layer IDs to QgsMapLayer instances.

        The returned list preserves the order of *layer_ids*, which
        is the QGIS render order (index zero is the top layer).

        Args:
            layer_ids: List of QGIS layer IDs to resolve.

        Returns:
            List of QgsMapLayer objects. Invalid IDs are silently skipped
            with a warning logged.
        """
        project = QgsProject.instance()
        layers: List[QgsMapLayer] = []

        for lid in layer_ids:
            layer = project.mapLayer(lid)
            if layer is not None and layer.isValid() and layer.id() == lid:
                layers.append(layer)
            else:
                logger.warning(f"Layer ID '{lid}' is missing or invalid — skipping.")

        return layers

    def get_valid_layer_ids(self) -> set:
        """Return IDs that still resolve to valid layers in the current project."""
        project = QgsProject.instance()
        return {
            layer_id
            for layer_id in project.mapLayers().keys()
            if (layer := project.mapLayer(layer_id)) is not None and layer.isValid()
        }

    @staticmethod
    def _is_effectively_visible(node: QgsLayerTreeLayer) -> bool:
        current = node
        while current is not None:
            if not current.isVisible():
                return False
            current = current.parent()
        return True

    def get_rendering_layers(
        self,
        selected_ids: Optional[List[str]] = None,
        use_visible: bool = False,
    ) -> List[QgsMapLayer]:
        """
        Build the final ordered list of layers for rendering.

        Args:
            selected_ids: Explicit layer IDs chosen by the user.
            use_visible: If True and *selected_ids* is empty,
                         use currently visible layers.

        Returns:
            Ordered list of QgsMapLayer in QGIS layer-tree order (top → bottom).
        """
        if selected_ids:
            layers = self.get_layers_by_ids(selected_ids)
        elif use_visible:
            vis = self.get_visible_layers()
            layers = self.get_layers_by_ids([li.layer_id for li in vis])
        else:
            all_layers = self.get_all_layers()
            layers = self.get_layers_by_ids(
                [li.layer_id for li in all_layers]
            )

        if not layers:
            logger.warning("No renderable layers found.")
        else:
            logger.info(
                f"Selected {len(layers)} layer(s) for rendering: "
                + ", ".join(l.name() for l in layers)
            )

        return layers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_info(layer: QgsMapLayer, visible: bool) -> LayerInfo:
        """Create a LayerInfo from a QgsMapLayer."""
        if isinstance(layer, QgsRasterLayer):
            ltype = "raster"
        elif isinstance(layer, QgsVectorLayer):
            ltype = "vector"
        else:
            ltype = "other"

        return LayerInfo(
            layer_id=layer.id(),
            name=layer.name(),
            layer_type=ltype,
            provider=layer.providerType() or "",
            crs_auth=layer.crs().authid() if layer.crs().isValid() else "",
            visible=visible,
        )
