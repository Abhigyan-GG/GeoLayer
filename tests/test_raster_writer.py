"""
Integration tests for RasterWriter and end-to-end GeoTIFF generation.
"""

import os
import shutil
import tempfile
import unittest

from osgeo import gdal
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle
from qgis.PyQt.QtGui import QColor, QImage, QPainter

from geospatial_tools.core.georeferencing import build_georeference
from geospatial_tools.core.raster_writer import RasterWriter, WriteOptions
from geospatial_tools.core.validation import GeoTiffValidator


class TestRasterWriter(unittest.TestCase):
    """Test QImage to GeoTIFF conversion and validation."""

    @classmethod
    def setUpClass(cls):
        gdal.AllRegister()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.writer = RasterWriter()
        self.validator = GeoTiffValidator()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_validate_rgb_geotiff(self):
        # 1. Create a synthetic test QImage (200x150)
        width, height = 200, 150
        fmt = getattr(QImage, "Format_ARGB32", getattr(QImage.Format, "Format_ARGB32", None))
        image = QImage(width, height, fmt)
        image.fill(QColor(34, 139, 34))  # Forest green

        # Draw a distinctive marker to ensure byte conversion works
        painter = QPainter(image)
        painter.setBrush(QColor(220, 20, 60))  # Crimson
        painter.drawRect(50, 40, 100, 70)
        painter.end()

        # 2. Build georeferencing
        extent = QgsRectangle(500000.0, 4000000.0, 501000.0, 4000750.0)
        crs = QgsCoordinateReferenceSystem("EPSG:32633")
        georef = build_georeference(extent, crs, width, height)

        # 3. Write GeoTIFF
        out_path = os.path.join(self.temp_dir, "test_render.tif")
        options = WriteOptions(compression="DEFLATE", tiled=True, include_alpha=False)

        res = self.writer.write(image, georef, out_path, options)

        self.assertTrue(res.success, f"Write failed: {res.error_message}")
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(res.file_size_bytes, 0)

        # 4. Reopen and validate via GeoTiffValidator
        val_res = self.validator.validate(out_path, georef, expected_bands=3)
        self.assertTrue(val_res.valid, f"Validation failed: {val_res.errors}")
        self.assertEqual(len(val_res.errors), 0)


if __name__ == "__main__":
    unittest.main()
