"""
GeoSpatial Tools — Map Renderer.

Uses QGIS's QgsMapRendererParallelJob to render selected layers into a
QImage at a specified extent, CRS, and output size — entirely through
the rendering engine, without any form of screen capture.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsMapLayer,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QEventLoop, QSize, QTimer
from qgis.PyQt.QtGui import QColor, QImage

from ..utils.constants import DEFAULT_DPI
from ..utils.plugin_logger import get_logger

logger = get_logger()


@dataclass
class RenderRequest:
    """
    Encapsulates all parameters needed for a single map render pass.

    Attributes:
        extent: Geographic/projected extent to render.
        layers: Ordered list in QGIS render order (top → bottom).
        crs: Destination CRS for rendering.
        width: Output image width in pixels.
        height: Output image height in pixels.
        dpi: Dots per inch (affects label/symbol sizing).
        background_color: Canvas background colour.
    """

    extent: QgsRectangle
    layers: List[QgsMapLayer]
    crs: QgsCoordinateReferenceSystem
    width: int
    height: int
    dpi: int = DEFAULT_DPI
    background_color: Optional[QColor] = None


@dataclass
class RenderResult:
    """
    Result of a render operation.

    Attributes:
        image: The rendered QImage (Format_ARGB32_Premultiplied).
        width: Pixel width.
        height: Pixel height.
        success: Whether rendering completed without errors.
        error_message: Human-readable error description (empty on success).
    """

    image: Optional[QImage]
    width: int
    height: int
    success: bool
    error_message: str = ""


class MapRenderer:
    """
    Renders QGIS map layers to an off-screen QImage using the official
    QGIS rendering engine (QgsMapRendererParallelJob).

    This is **not** a screenshot. It programmatically configures
    QgsMapSettings and runs the renderer in a background thread,
    producing a raster image that respects all layer styles, CRS,
    and extent parameters.
    """

    def __init__(self) -> None:
        self._job: Optional[QgsMapRendererParallelJob] = None
        self._job_layer_ids = set()
        self._cancelled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        request: RenderRequest,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> RenderResult:
        """
        Synchronously render the map and return a RenderResult.

        This method blocks the calling thread (via a local QEventLoop)
        until the render job completes, but the actual rendering happens
        on QGIS's background threads so the main UI stays responsive
        enough to process events.

        Args:
            request: Fully-specified render request.
            on_progress: Optional callback for status messages.

        Returns:
            RenderResult with the rendered QImage.
        """
        # --- validate -----------------------------------------------
        if not request.layers:
            return RenderResult(
                image=None, width=0, height=0,
                success=False,
                error_message="No layers selected for rendering.",
            )
        project = QgsProject.instance()
        valid_layers = []
        for layer in request.layers:
            if layer is None or not layer.isValid():
                continue
            current = project.mapLayer(layer.id())
            if current is not None and current.isValid():
                valid_layers.append(current)
        if not valid_layers:
            return RenderResult(
                image=None, width=0, height=0, success=False,
                error_message="No selected layers remain valid in the QGIS project.",
            )
        skipped_count = len(request.layers) - len(valid_layers)
        if skipped_count:
            logger.warning(f"Skipped {skipped_count} missing or invalid render layer(s).")
        if request.width <= 0 or request.height <= 0:
            return RenderResult(
                image=None, width=0, height=0,
                success=False,
                error_message=(
                    f"Invalid output dimensions: "
                    f"{request.width}×{request.height}."
                ),
            )
        if request.extent.isEmpty():
            return RenderResult(
                image=None, width=0, height=0,
                success=False,
                error_message="Render extent is empty.",
            )

        # --- configure QgsMapSettings --------------------------------
        if on_progress:
            on_progress("Configuring map settings…")

        settings = self._build_settings(request, valid_layers)

        logger.info(
            f"Rendering {len(valid_layers)} layer(s) at "
            f"{request.width}×{request.height} px, "
            f"CRS {request.crs.authid()}"
        )

        # --- run render job ------------------------------------------
        if on_progress:
            on_progress("Rendering layers…")

        job = QgsMapRendererParallelJob(settings)
        self._job = job
        self._job_layer_ids = {layer.id() for layer in valid_layers}
        self._cancelled = False

        # Use a local event loop so we block but still pump Qt events
        loop = QEventLoop()
        job.finished.connect(loop.quit)

        def cancel_for_removed_layers(*args) -> None:
            removed_ids = set()
            for value in args:
                if isinstance(value, (list, tuple, set)):
                    removed_ids.update(
                        layer.id() if hasattr(layer, "id") else str(layer)
                        for layer in value
                    )
                elif hasattr(value, "id"):
                    removed_ids.add(value.id())
                elif isinstance(value, str):
                    removed_ids.add(value)
            if self._job_layer_ids.intersection(removed_ids):
                self.cancel()

        removal_signal = getattr(project, "layersWillBeRemoved", None)
        if removal_signal is not None:
            removal_signal.connect(cancel_for_removed_layers)

        # Safety timeout: 5 minutes
        timeout = QTimer()
        timeout.setSingleShot(True)
        timed_out = [False]

        def on_timeout():
            timed_out[0] = True
            loop.quit()

        timeout.timeout.connect(on_timeout)
        timeout.start(300_000)

        exec_method = getattr(loop, "exec", None) or getattr(loop, "exec_")
        try:
            job.start()
            if job.isActive():
                exec_method()
        finally:
            timeout.stop()
            if removal_signal is not None:
                removal_signal.disconnect(cancel_for_removed_layers)

        if timed_out[0]:
            self.cancel()
            logger.error("Render timed out after 5 minutes.")
            self._job = None
            self._job_layer_ids.clear()
            return RenderResult(
                image=None,
                width=request.width,
                height=request.height,
                success=False,
                error_message="Rendering timed out after 5 minutes.",
            )

        if self._cancelled:
            self._job = None
            self._job_layer_ids.clear()
            return RenderResult(
                image=None, width=request.width, height=request.height,
                success=False,
                error_message="Rendering was cancelled because a layer was removed.",
            )

        self._job = None
        self._job_layer_ids.clear()

        # --- collect result -----------------------------------------
        image = job.renderedImage()
        if image.isNull():
            logger.error("Rendered image is null.")
            return RenderResult(
                image=None,
                width=request.width,
                height=request.height,
                success=False,
                error_message="Rendered image is null — rendering may have failed.",
            )

        if on_progress:
            on_progress("Render complete.")

        logger.info(
            f"Render complete: {image.width()}×{image.height()} "
            f"({image.format()})"
        )
        return RenderResult(
            image=image,
            width=image.width(),
            height=image.height(),
            success=True,
        )

    def cancel(self) -> None:
        """Cancel an in-progress render job, if any."""
        if self._job is not None:
            if not self._cancelled:
                self._cancelled = True
                self._job.cancel()
            logger.info("Render job cancelled.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_settings(request: RenderRequest, layers=None) -> QgsMapSettings:
        """
        Build a QgsMapSettings object from a RenderRequest.

        This is the heart of the rendering pipeline — it configures
        every aspect of QGIS's rendering engine.
        """
        settings = QgsMapSettings()

        # Layers — order matters (first = bottom)
        settings.setLayers(layers if layers is not None else request.layers)

        # Extent
        settings.setExtent(request.extent)

        # Destination CRS — QGIS will reproject layers as needed
        settings.setDestinationCrs(request.crs)

        # Output image dimensions
        settings.setOutputSize(QSize(request.width, request.height))

        # DPI for symbol/label scaling
        settings.setOutputDpi(request.dpi)

        # Background
        bg_color = (
            request.background_color
            if request.background_color is not None
            else QColor(255, 255, 255, 255)
        )
        settings.setBackgroundColor(bg_color)

        # Use anti-aliasing for better visual quality across QGIS 3 and 4
        from ..utils.compat import set_map_setting_flag
        set_map_setting_flag(settings, "Antialiasing", True)
        set_map_setting_flag(settings, "UseAdvancedEffects", True)
        set_map_setting_flag(settings, "RenderMapTile", False)

        return settings
