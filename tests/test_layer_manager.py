"""QGIS integration tests for current-project layer resolution."""

import unittest

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer

from geospatial_tools.core.layer_manager import LayerManager


class TestLayerManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qgs_app = QgsApplication.instance() or QgsApplication([], False)
        cls.qgs_app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.qgs_app.exitQgis()

    def setUp(self):
        self.project = QgsProject.instance()
        self.project.clear()
        self.manager = LayerManager()

    def test_deleted_layer_id_resolves_to_nothing(self):
        self.assertEqual(self.manager.get_layers_by_ids(["not-in-project"]), [])

    def test_added_layer_is_current_and_removed_layer_disappears(self):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "temporary", "memory")
        self.assertTrue(layer.isValid())
        layer_id = layer.id()
        self.project.addMapLayer(layer)

        resolved = self.manager.get_layers_by_ids([layer_id])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].id(), layer_id)

        self.project.removeMapLayer(layer_id)
        self.assertEqual(self.manager.get_layers_by_ids([layer_id]), [])
        self.assertNotIn(layer_id, {info.layer_id for info in self.manager.get_all_layers()})

    def test_empty_project_has_no_rendering_layers(self):
        self.assertEqual(self.manager.get_rendering_layers(), [])


if __name__ == "__main__":
    unittest.main()
