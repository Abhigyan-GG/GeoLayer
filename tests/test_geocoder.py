"""
Unit tests for geocoding and coordinate parsing.
"""

import unittest
import io
import json
import socket
import urllib.error
from unittest.mock import patch
from geospatial_tools.core.geocoder import (
    GeocoderRequestError,
    NominatimGeocoder,
    predefined_location,
    normalize_nominatim_result,
    parse_coordinates,
)


class TestGeocoder(unittest.TestCase):
    """Test direct coordinate parsing and validation."""

    def test_predefined_cfees_aliases_are_offline_and_identical(self):
        aliases = (
            "CFEES", "Cfees", " cfees   Timarpur ", "DRDO CFEES",
            "CFEES Delhi", "Centre for Fire, Explosive and Environment Safety",
        )
        results = [predefined_location(alias) for alias in aliases]
        self.assertTrue(all(results))
        self.assertEqual({result.provider_id for result in results}, {"local/cfees-timarpur"})
        self.assertEqual({(result.latitude, result.longitude) for result in results},
                         {(28.7037056, 77.2168583)})
        for alias in aliases:
            result = NominatimGeocoder().geocode(alias)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].provider_id, "local/cfees-timarpur")

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

    def test_normalize_nominatim_poi_metadata(self):
        result = normalize_nominatim_result({
            "lat": "28.703665",
            "lon": "77.216863",
            "name": "Example Institute",
            "display_name": "Example Institute, Timarpur, Delhi",
            "category": "amenity",
            "type": "university",
            "osm_type": "way",
            "osm_id": 123,
            "address": {"road": "Brig SK Mazumdar Marg", "postcode": "110054"},
            "extratags": {
                "phone": "12345",
                "contact:website": "https://example.test",
                "opening_hours": "Mo-Fr 09:00-17:00",
                "operator": "Example Operator",
            },
            "namedetails": {"name": "Example Institute"},
        })

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Example Institute")
        self.assertEqual(result.category, "amenity")
        self.assertEqual(result.subcategory, "university")
        self.assertEqual(result.postcode, "110054")
        self.assertEqual(result.phone, "12345")
        self.assertEqual(result.website, "https://example.test")
        self.assertEqual(result.provider_id, "way/123")
        self.assertEqual(result.metadata["address"]["road"], "Brig SK Mazumdar Marg")

    def test_normalize_nominatim_missing_optional_metadata(self):
        result = normalize_nominatim_result({"lat": "1", "lon": "2"})
        self.assertIsNotNone(result)
        self.assertEqual(result.address, {})
        self.assertEqual(result.metadata["extratags"], {})
        self.assertEqual(result.phone, "")
        self.assertEqual(result.provider_id, "")

    def test_normalize_nominatim_rejects_malformed_coordinates(self):
        self.assertIsNone(normalize_nominatim_result({"lat": "91", "lon": "0"}))

    def test_empty_search_response_returns_no_results(self):
        geocoder = NominatimGeocoder(rate_limit=0)
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"[]")):
            self.assertEqual(geocoder.geocode("nowhere test"), [])

    def test_invalid_json_is_reported_as_provider_error(self):
        geocoder = NominatimGeocoder(rate_limit=0)
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"not json")):
            with self.assertRaisesRegex(GeocoderRequestError, "invalid JSON"):
                geocoder.geocode("test place")

    def test_http_429_has_actionable_error(self):
        geocoder = NominatimGeocoder(max_retries=1, rate_limit=0)
        response = urllib.error.HTTPError(
            "https://example.test", 429, "Too Many Requests", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=response):
            with self.assertRaisesRegex(GeocoderRequestError, "HTTP 429"):
                geocoder.geocode("test place")

    def test_network_timeout_has_actionable_error(self):
        geocoder = NominatimGeocoder(max_retries=1, rate_limit=0)
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError(socket.timeout("timed out")),
        ):
            with self.assertRaisesRegex(GeocoderRequestError, "timed out"):
                geocoder.geocode("test place")

    def test_reverse_geocoding_normalizes_poi_fields(self):
        geocoder = NominatimGeocoder(rate_limit=0)
        response = {
            "lat": "28.703665",
            "lon": "77.216863",
            "display_name": "Example Institute, Delhi",
            "category": "amenity",
            "type": "university",
            "address": {"postcode": "110054"},
            "osm_type": "way",
            "osm_id": 42,
        }
        with patch(
            "urllib.request.urlopen",
            return_value=io.BytesIO(json.dumps(response).encode("utf-8")),
        ):
            result = geocoder.reverse_geocode(28.703665, 77.216863)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "amenity")
        self.assertEqual(result.postcode, "110054")
        self.assertEqual(result.provider_id, "way/42")


if __name__ == "__main__":
    unittest.main()
