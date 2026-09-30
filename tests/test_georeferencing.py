"""
Unit tests for GeoTransform and georeferencing calculations.
"""

import unittest
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle
from geospatial_tools.core.georeferencing import (
    GeoTransform,
    build_georeference,
    build_geotransform,
    extent_from_geotransform,
)


class TestGeoreferencing(unittest.TestCase):
    """Test georeferencing math and GDAL affine transform correctness."""

    def test_build_geotransform(self):
        # 1000m x 1000m extent, 2000 x 2000 pixels -> 0.5m/pixel
        extent = QgsRectangle(700000.0, 3100000.0, 701000.0, 3101000.0)
        width_px = 2000
        height_px = 2000

        gt = build_geotransform(extent, width_px, height_px)

        self.assertAlmostEqual(gt.origin_x, 700000.0)
        self.assertAlmostEqual(gt.pixel_width, 0.5)
        self.assertAlmostEqual(gt.rotation_x, 0.0)
        self.assertAlmostEqual(gt.origin_y, 3101000.0)  # ymax
        self.assertAlmostEqual(gt.rotation_y, 0.0)
        self.assertAlmostEqual(gt.pixel_height, -0.5)  # negative for north-up
        self.assertTrue(gt.is_north_up)

        gdal_tuple = gt.to_gdal_tuple()
        self.assertEqual(len(gdal_tuple), 6)
        self.assertEqual(gdal_tuple[0], 700000.0)
        self.assertEqual(gdal_tuple[1], 0.5)
        self.assertEqual(gdal_tuple[2], 0.0)
        self.assertEqual(gdal_tuple[3], 3101000.0)
        self.assertEqual(gdal_tuple[4], 0.0)
        self.assertEqual(gdal_tuple[5], -0.5)

    def test_extent_from_geotransform_reconstruction(self):
        extent = QgsRectangle(100.0, 200.0, 500.0, 600.0)
        width_px = 800
        height_px = 800

        gt = build_geotransform(extent, width_px, height_px)
        reconstructed = extent_from_geotransform(gt, width_px, height_px)

        self.assertAlmostEqual(reconstructed.xMinimum(), extent.xMinimum(), places=6)
        self.assertAlmostEqual(reconstructed.yMinimum(), extent.yMinimum(), places=6)
        self.assertAlmostEqual(reconstructed.xMaximum(), extent.xMaximum(), places=6)
        self.assertAlmostEqual(reconstructed.yMaximum(), extent.yMaximum(), places=6)

    def test_invalid_dimensions_raise_error(self):
        extent = QgsRectangle(0.0, 0.0, 10.0, 10.0)
        with self.assertRaises(ValueError):
            build_geotransform(extent, 0, 100)
        with self.assertRaises(ValueError):
            build_geotransform(extent, 100, -5)


if __name__ == "__main__":
    unittest.main()
