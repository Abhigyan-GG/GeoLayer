"""
Unit tests for geocoding and coordinate parsing.
"""

import unittest
from geospatial_tools.core.geocoder import parse_coordinates


class TestGeocoder(unittest.TestCase):
    """Test direct coordinate parsing and validation."""

    def test_parse_valid_comma_coordinates(self):
        result = parse_coordinates("28.6315, 77.2167")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.latitude, 28.6315)
        self.assertAlmostEqual(result.longitude, 77.2167)
        self.assertEqual(result.source, "direct_input")

    def test_parse_valid_space_separated_coordinates(self):
        result = parse_coordinates("28.6315 77.2167")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.latitude, 28.6315)
        self.assertAlmostEqual(result.longitude, 77.2167)

    def test_parse_negative_coordinates(self):
        result = parse_coordinates("-33.8688, 151.2093")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.latitude, -33.8688)
        self.assertAlmostEqual(result.longitude, 151.2093)

    def test_reject_invalid_text(self):
        self.assertIsNone(parse_coordinates("Connaught Place, New Delhi"))
        self.assertIsNone(parse_coordinates("IIT Delhi"))
        self.assertIsNone(parse_coordinates("invalid, coords"))

    def test_reject_out_of_bounds_coordinates(self):
        # Lat > 90
        self.assertIsNone(parse_coordinates("95.0, 77.0"))
        # Lon > 180
        self.assertIsNone(parse_coordinates("28.0, 195.0"))


if __name__ == "__main__":
    unittest.main()
