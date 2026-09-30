"""
GeoSpatial Tools — QGIS Plugin for Geospatial Rendering & GeoTIFF Generation.

This plugin provides a workflow to render QGIS map layers into properly
georeferenced GeoTIFF files with full CRS, extent, and affine transform
preservation.
"""


def classFactory(iface):
    """
    QGIS plugin entry point.

    Called by QGIS when the plugin is loaded. Returns an instance of the
    main plugin class.

    Args:
        iface: QgisInterface instance providing access to the QGIS application.

    Returns:
        GeoSpatialToolsPlugin instance.
    """
    from .geospatial_tools import GeoSpatialToolsPlugin
    return GeoSpatialToolsPlugin(iface)
