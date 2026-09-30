"""
Unit tests for GeoTIFF validation with synthetic raster data.
"""

import os
import shutil
import tempfile
import unittest

from osgeo import gdal, osr
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle

from geospatial_tools.core.georeferencing import build_georeference
from geospatial_tools.core.validation import GeoTiffValidator


class TestGeoTiffValidator(unittest.TestCase):
    """Test validation of synthetic GeoTIFF files."""

    @classmethod
    def setUpClass(cls):
        gdal.AllRegister()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.validator = GeoTiffValidator()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_synthetic_geotiff(
        self,
        filepath: str,
        width: int,
        height: int,
        extent: QgsRectangle,
        epsg: int,
        bands: int = 3,
    ) -> None:
        """Helper to create a known synthetic GeoTIFF with GDAL."""
        driver = gdal.GetDriverByName("GTiff")
        ds = driver.Create(filepath, width, height, bands, gdal.GDT_Byte)

        pixel_w = (extent.xMaximum() - extent.xMinimum()) / width
        pixel_h = (extent.yMaximum() - extent.yMinimum()) / height
        gt = (extent.xMinimum(), pixel_w, 0.0, extent.yMaximum(), 0.0, -pixel_h)
        ds.SetGeoTransform(gt)

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)
        ds.SetProjection(srs.ExportToWkt())

        # Write dummy data to each band
        import numpy as np
        dummy_data = np.full((height, width), 128, dtype=np.uint8)
        for b in range(1, bands + 1):
            band = ds.GetRasterBand(b)
            band.WriteArray(dummy_data)
            band.FlushCache()

        ds.FlushCache()
        ds = None

    def test_validation_passes_on_correct_raster(self):
        width, height = 500, 500
        extent = QgsRectangle(1000.0, 2000.0, 1500.0, 2500.0)
        crs = QgsCoordinateReferenceSystem("EPSG:32643")
        georef = build_georeference(extent, crs, width, height)

        tif_path = os.path.join(self.temp_dir, "valid.tif")
        self._create_synthetic_geotiff(tif_path, width, height, extent, 32643, bands=3)

        result = self.validator.validate(tif_path, georef, expected_bands=3)
        self.assertTrue(result.valid, f"Validation failed with errors: {result.errors}")
        self.assertEqual(len(result.errors), 0)

    def test_validation_fails_on_dimension_mismatch(self):
        width, height = 500, 500
        extent = QgsRectangle(1000.0, 2000.0, 1500.0, 2500.0)
        crs = QgsCoordinateReferenceSystem("EPSG:32643")
        georef = build_georeference(extent, crs, width, height)

        # Create file with 400x400 instead of 500x500
        tif_path = os.path.join(self.temp_dir, "wrong_dim.tif")
        self._create_synthetic_geotiff(tif_path, 400, 400, extent, 32643, bands=3)

        result = self.validator.validate(tif_path, georef, expected_bands=3)
        self.assertFalse(result.valid)
        self.assertTrue(any("Dimensions mismatch" in err for err in result.errors))

    def test_validation_fails_on_missing_file(self):
        extent = QgsRectangle(0.0, 0.0, 10.0, 10.0)
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        georef = build_georeference(extent, crs, 100, 100)

        result = self.validator.validate(os.path.join(self.temp_dir, "nonexistent.tif"), georef)
        self.assertFalse(result.valid)
        self.assertTrue(any("does not exist" in err for err in result.errors))


if __name__ == "__main__":
    unittest.main()
