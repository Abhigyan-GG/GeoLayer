"""
Unit tests for AOI Manager extent creation.
"""

import unittest
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsRectangle,
)
from geospatial_tools.core.aoi_manager import (
    AOIManager,
    AOIMethod,
    AOIParameters,
)


class TestAOIManager(unittest.TestCase):
    """Test AOI creation with metric parameters."""

    @classmethod
    def setUpClass(cls):
        # Initialize minimal QGIS application instance if not running
        cls.qgs_app = QgsApplication([], False)
        cls.qgs_app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.qgs_app.exitQgis()

    def setUp(self):
        self.manager = AOIManager()

    def test_aoi_from_radius(self):
        # Center in Delhi in UTM 43N
        utm_crs = QgsCoordinateReferenceSystem("EPSG:32643")
        center = QgsPointXY(718000.0, 3169000.0)

        params = AOIParameters(
            method=AOIMethod.RADIUS,
            center=center,
            center_crs=utm_crs,
            radius_m=500.0,
        )

        res = self.manager.create_aoi(params, output_crs=utm_crs)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.extent)

        # 500m radius -> 1000m width & height
        self.assertAlmostEqual(res.extent.width(), 1000.0, places=2)
        self.assertAlmostEqual(res.extent.height(), 1000.0, places=2)
        self.assertAlmostEqual(res.extent.center().x(), 718000.0, places=2)
        self.assertAlmostEqual(res.extent.center().y(), 3169000.0, places=2)

    def test_aoi_from_rectangle(self):
        utm_crs = QgsCoordinateReferenceSystem("EPSG:32643")
        center = QgsPointXY(718000.0, 3169000.0)

        params = AOIParameters(
            method=AOIMethod.RECTANGLE,
            center=center,
            center_crs=utm_crs,
            width_m=2000.0,
            height_m=1200.0,
        )

        res = self.manager.create_aoi(params, output_crs=utm_crs)
        self.assertTrue(res.success)
        self.assertAlmostEqual(res.extent.width(), 2000.0, places=2)
        self.assertAlmostEqual(res.extent.height(), 1200.0, places=2)

    def test_missing_center_fails_gracefully(self):
        params = AOIParameters(
            method=AOIMethod.RADIUS,
            center=None,
        )
        res = self.manager.create_aoi(params)
        self.assertFalse(res.success)
        self.assertIn("Centre point is required", res.error_message)


if __name__ == "__main__":
    unittest.main()
