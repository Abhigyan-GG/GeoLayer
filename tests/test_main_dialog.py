"""QGIS GUI regressions for Help and interactive AOI drawing.

Run with QGIS Python; set QT_QPA_PLATFORM=offscreen for headless runs.
"""

import importlib.util
from types import SimpleNamespace
import unittest


HAS_QGIS = importlib.util.find_spec("qgis") is not None
if HAS_QGIS:
    from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsRectangle
    from qgis.gui import QgsMapCanvas, QgsMapToolPan
    from qgis.PyQt.QtCore import QPoint, Qt
    from qgis.PyQt.QtTest import QTest
    from qgis.PyQt.QtWidgets import QLabel

    from geospatial_tools.ui.main_dialog import MainDialog


@unittest.skipUnless(HAS_QGIS, "Requires QGIS Python and Qt")
class TestMainDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication.instance()
        cls.owns_app = cls.app is None
        if cls.owns_app:
            cls.app = QgsApplication([], True)
            cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        if cls.owns_app:
            cls.app.exitQgis()

    def setUp(self):
        self.canvas = QgsMapCanvas()
        self.canvas.resize(400, 400)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        self.canvas.setExtent(QgsRectangle(0, 0, 1000, 1000))
        self.canvas.show()
        self.app.processEvents()
        self.pan = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(self.pan)
        self.dialog = MainDialog(SimpleNamespace(mapCanvas=lambda: self.canvas))

    def tearDown(self):
        self.dialog.close()
        self.canvas.close()
        self.dialog.deleteLater()
        self.canvas.deleteLater()
        self.app.processEvents()

    def test_help_button_opens_rich_text_guide(self):
        self.dialog._btn_help.click()
        guide_dialog = self.dialog._help_dialog
        self.assertTrue(guide_dialog.isVisible())
        guide = guide_dialog.findChild(QLabel)
        self.assertEqual(guide.textFormat(), getattr(Qt, "TextFormat", Qt).RichText)
        self.assertIn("Getting Started", guide.text())
        guide_dialog.close()

    def _drag(self, start, end):
        self.dialog._widget_aoi._radio_draw.click()
        self.dialog._widget_aoi._btn_start_draw.click()
        tool = self.dialog._map_tool
        selections = []
        tool.completed.connect(lambda extent, crs: selections.append((extent, crs)))
        button = getattr(Qt, "MouseButton", Qt).LeftButton
        QTest.mousePress(self.canvas.viewport(), button, pos=start)
        QTest.mouseMove(self.canvas.viewport(), end)
        self.assertFalse(self.dialog._rubber_band.asGeometry().isEmpty())
        QTest.mouseRelease(self.canvas.viewport(), button, pos=end)
        self.assertEqual(len(selections), 1)
        self.assertTrue(self.dialog._widget_aoi.current_aoi().success)
        self.assertIs(self.canvas.mapTool(), self.pan)
        self.assertIsNone(self.dialog._map_tool)
        return selections[0][0]

    def test_drag_in_both_directions_and_redraw(self):
        forward = self._drag(QPoint(60, 70), QPoint(280, 300))
        backward = self._drag(QPoint(280, 300), QPoint(60, 70))
        self.assertEqual(forward, backward)

    def test_repeated_activation_preserves_previous_tool(self):
        self.dialog._on_draw_aoi_requested()
        tool = self.dialog._map_tool
        self.dialog._on_draw_aoi_requested()
        self.assertIs(self.dialog._map_tool, tool)
        self.dialog.close()
        self.assertIs(self.canvas.mapTool(), self.pan)

    def test_completion_without_previous_tool_unsets_drawing_tool(self):
        self.canvas.unsetMapTool(self.pan)
        self.dialog._on_draw_aoi_requested()
        self.dialog._restore_map_tool()
        self.assertIsNone(self.canvas.mapTool())


if __name__ == "__main__":
    unittest.main()
