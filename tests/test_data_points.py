"""QGIS integration tests for POI data-point storage."""

import unittest

from qgis.core import QgsApplication, QgsProject

from geospatial_tools.core.data_points import DataPointsManager
from geospatial_tools.core.geocoder import GeocodingResult


class TestDataPointsManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qgs_app = QgsApplication.instance() or QgsApplication([], False)
        cls.qgs_app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.qgs_app.exitQgis()

    def setUp(self):
        QgsProject.instance().clear()
        self.manager = DataPointsManager()

    def test_add_deduplicates_provider_id_and_deletes_one_feature(self):
        result = GeocodingResult(
            latitude=28.703665,
            longitude=77.216863,
            display_name="Example Institute, Delhi",
            name="Example Institute",
            source="test-provider",
            provider_id="way/123",
            category="amenity",
            subcategory="university",
        )
        first = self.manager.add_result(result)
        duplicate = self.manager.add_result(result)

        self.assertTrue(first["added"])
        self.assertFalse(duplicate["added"])
        self.assertEqual(len(self.manager.list_points()), 1)
        point = self.manager.list_points()[0]
        self.assertAlmostEqual(point["latitude"], 28.703665)
        self.assertAlmostEqual(point["longitude"], 77.216863)
        self.assertTrue(self.manager.delete_feature(first["feature_id"]))
        self.assertEqual(self.manager.list_points(), [])

    def test_deduplicates_nearby_normalized_names_without_provider_id(self):
        first = GeocodingResult(
            latitude=10.0,
            longitude=20.0,
            name="Example   Place",
        )
        nearby = GeocodingResult(
            latitude=10.00001,
            longitude=20.00001,
            name="example place",
        )
        self.manager.add_result(first)
        duplicate = self.manager.add_result(nearby)
        self.assertFalse(duplicate["added"])
        self.assertEqual(len(self.manager.list_points()), 1)


if __name__ == "__main__":
    unittest.main()
