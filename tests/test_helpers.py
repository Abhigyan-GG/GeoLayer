"""
Unit tests for GeoSpatial Tools utility helpers.
"""

import unittest
from geospatial_tools.utils.helpers import (
    compute_pixel_dimensions,
    estimate_output_size,
    estimate_raster_memory,
    format_file_size,
    safe_filename,
)


class TestHelpers(unittest.TestCase):
    """Test helper functions."""

    def test_format_file_size(self):
        self.assertEqual(format_file_size(0), "0 B")
        self.assertEqual(format_file_size(500), "500 B")
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1024 * 1024), "1.0 MB")
        self.assertEqual(format_file_size(1572864), "1.5 MB")
        self.assertEqual(format_file_size(1024 * 1024 * 1024), "1.0 GB")

    def test_compute_pixel_dimensions(self):
        # 1000m x 1000m at 0.5m/pixel -> 2000 x 2000 pixels
        w, h = compute_pixel_dimensions(1000.0, 1000.0, 0.5)
        self.assertEqual(w, 2000)
        self.assertEqual(h, 2000)

        # 500m x 250m at 1.0m/pixel -> 500 x 250 pixels
        w, h = compute_pixel_dimensions(500.0, 250.0, 1.0)
        self.assertEqual(w, 500)
        self.assertEqual(h, 250)

        # Fractional dimensions round up safely (ceil)
        w, h = compute_pixel_dimensions(100.1, 100.1, 1.0)
        self.assertEqual(w, 101)
        self.assertEqual(h, 101)

    def test_estimate_raster_memory(self):
        # 2000 x 2000 x 4 bytes = 16,000,000 bytes (~16 MB)
        mem = estimate_raster_memory(2000, 2000, 4)
        self.assertEqual(mem, 16_000_000)

    def test_estimate_output_size(self):
        # 50% compression of 16 MB -> 8 MB
        size = estimate_output_size(2000, 2000, 4, 0.5)
        self.assertEqual(size, 8_000_000)

    def test_safe_filename(self):
        self.assertEqual(
            safe_filename("Connaught Place, New Delhi"),
            "Connaught_Place_New_Delhi.tif"
        )
        self.assertEqual(
            safe_filename("IIT Delhi / Hauz Khas : Zone 1"),
            "IIT_Delhi_Hauz_Khas_Zone_1.tif"
        )
        self.assertEqual(
            safe_filename("   "),
            "export.tif"
        )


if __name__ == "__main__":
    unittest.main()
