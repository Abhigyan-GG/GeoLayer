"""
GeoSpatial Tools — Geocoder.

Abstracted geocoding interface with a Nominatim implementation.
Supports forward geocoding, reverse geocoding, direct coordinate input,
caching, rate-limit awareness, and configurable timeouts.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils.constants import (
    COORDINATE_REGEX,
    GEOCODER_MAX_RETRIES,
    GEOCODER_RATE_LIMIT_S,
    GEOCODER_TIMEOUT_S,
    GEOCODER_USER_AGENT,
    NOMINATIM_REVERSE_URL,
    NOMINATIM_URL,
)
from ..utils.plugin_logger import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GeocodingResult:
    """
    A single geocoding result.

    Attributes:
        latitude: WGS 84 latitude.
        longitude: WGS 84 longitude.
        display_name: Human-readable location description.
        source: Geocoder backend that produced this result.
        confidence: Quality score 0–1 (None if unavailable).
        bbox: Bounding box [south, north, west, east] (None if unavailable).
        raw: Raw provider response for debugging.
    """

    latitude: float
    longitude: float
    display_name: str = ""
    source: str = ""
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None
    raw: Dict = field(default_factory=dict)


@dataclass
class GeocodingError:
    """Represents a geocoding failure."""

    message: str
    recoverable: bool = True


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class Geocoder(ABC):
    """
    Abstract geocoding interface.

    Subclass and implement ``geocode`` / ``reverse_geocode`` to add
    new geocoding backends without changing any UI code.
    """

    @abstractmethod
    def geocode(self, query: str) -> List[GeocodingResult]:
        """
        Forward geocode: address/place name → coordinates.

        Args:
            query: Human-readable location string.

        Returns:
            List of results, best first. Empty on failure.
        """

    @abstractmethod
    def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[GeocodingResult]:
        """
        Reverse geocode: coordinates → place name.

        Args:
            latitude: WGS 84 latitude.
            longitude: WGS 84 longitude.

        Returns:
            Best result, or None if nothing found.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the geocoding provider."""


# ---------------------------------------------------------------------------
# Coordinate parser (no network required)
# ---------------------------------------------------------------------------

_COORD_RE = re.compile(COORDINATE_REGEX)


def parse_coordinates(text: str) -> Optional[GeocodingResult]:
    """
    Try to interpret *text* as direct lat/lon coordinates.

    Accepted formats:
        28.6315, 77.2167
        28.6315 77.2167
        28.6315; 77.2167

    Returns:
        GeocodingResult if parseable, else None.
    """
    match = _COORD_RE.match(text.strip())
    if not match:
        return None

    try:
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
    except (ValueError, TypeError):
        return None

    if not (-90.0 <= lat <= 90.0):
        return None
    if not (-180.0 <= lon <= 180.0):
        return None

    return GeocodingResult(
        latitude=lat,
        longitude=lon,
        display_name=f"{lat:.6f}, {lon:.6f}",
        source="direct_input",
        confidence=1.0,
    )


# ---------------------------------------------------------------------------
# Nominatim implementation
# ---------------------------------------------------------------------------

class NominatimGeocoder(Geocoder):
    """
    Geocoder backed by OpenStreetMap's Nominatim API.

    Respects the Nominatim usage policy:
    - Includes a descriptive User-Agent.
    - Enforces ≥1 s between requests.
    - Supports configurable timeout and retries.

    Note: Nominatim usage policy limits automated bulk geocoding.
    This geocoder is intended for interactive, user-initiated searches.
    """

    def __init__(
        self,
        url: str = NOMINATIM_URL,
        reverse_url: str = NOMINATIM_REVERSE_URL,
        user_agent: str = GEOCODER_USER_AGENT,
        timeout: int = GEOCODER_TIMEOUT_S,
        max_retries: int = GEOCODER_MAX_RETRIES,
        rate_limit: float = GEOCODER_RATE_LIMIT_S,
    ) -> None:
        self._url = url
        self._reverse_url = reverse_url
        self._user_agent = user_agent
        self._timeout = timeout
        self._max_retries = max_retries
        self._rate_limit = rate_limit
        self._last_request_time: float = 0.0
        self._cache: Dict[str, List[GeocodingResult]] = {}

    @property
    def name(self) -> str:
        return "Nominatim (OpenStreetMap)"

    # ------------------------------------------------------------------
    # Forward geocoding
    # ------------------------------------------------------------------

    def geocode(self, query: str) -> List[GeocodingResult]:
        """
        Geocode an address or place name.

        First tries to parse direct coordinates. If that fails,
        queries Nominatim.

        Args:
            query: Location string.

        Returns:
            List of GeocodingResult, best first.
        """
        query = query.strip()
        if not query:
            return []

        # Try direct coordinate parsing first — no network needed
        direct = parse_coordinates(query)
        if direct is not None:
            logger.info(f"Parsed direct coordinates: {direct.latitude}, {direct.longitude}")
            return [direct]

        # Check cache
        cache_key = query.lower()
        if cache_key in self._cache:
            logger.debug(f"Geocode cache hit for '{query}'")
            return self._cache[cache_key]

        # Build request
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "addressdetails": "1",
            "limit": "5",
        })
        url = f"{self._url}?{params}"

        data = self._fetch(url)
        if data is None:
            return []

        try:
            items = json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"Failed to parse Nominatim response: {exc}")
            return []

        results = []
        for item in items:
            try:
                result = GeocodingResult(
                    latitude=float(item["lat"]),
                    longitude=float(item["lon"]),
                    display_name=item.get("display_name", ""),
                    source=self.name,
                    confidence=self._importance_to_confidence(
                        item.get("importance")
                    ),
                    bbox=self._parse_bbox(item.get("boundingbox")),
                    raw=item,
                )
                results.append(result)
            except (KeyError, ValueError, TypeError) as exc:
                logger.debug(f"Skipping malformed result: {exc}")

        # Cache successful results
        if results:
            self._cache[cache_key] = results

        logger.info(
            f"Geocoded '{query}' → {len(results)} result(s)"
        )
        return results

    # ------------------------------------------------------------------
    # Reverse geocoding
    # ------------------------------------------------------------------

    def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[GeocodingResult]:
        """
        Reverse geocode coordinates to a place name.

        Args:
            latitude: WGS 84 latitude.
            longitude: WGS 84 longitude.

        Returns:
            GeocodingResult or None.
        """
        params = urllib.parse.urlencode({
            "lat": str(latitude),
            "lon": str(longitude),
            "format": "json",
            "addressdetails": "1",
        })
        url = f"{self._reverse_url}?{params}"

        data = self._fetch(url)
        if data is None:
            return None

        try:
            item = json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"Failed to parse reverse geocode response: {exc}")
            return None

        if "error" in item:
            logger.warning(f"Reverse geocode error: {item['error']}")
            return None

        try:
            return GeocodingResult(
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
                display_name=item.get("display_name", ""),
                source=self.name,
                raw=item,
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error(f"Failed to parse reverse geocode result: {exc}")
            return None

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> Optional[str]:
        """
        Fetch a URL with rate-limiting, retries, and timeout.

        Returns:
            Response body as string, or None on failure.
        """
        self._enforce_rate_limit()

        for attempt in range(1, self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": self._user_agent},
                )
                with urllib.request.urlopen(
                    req, timeout=self._timeout
                ) as resp:
                    self._last_request_time = time.monotonic()
                    return resp.read().decode("utf-8")

            except urllib.error.HTTPError as exc:
                logger.warning(
                    f"Geocoder HTTP {exc.code} (attempt {attempt}/{self._max_retries})"
                )
                if attempt < self._max_retries:
                    time.sleep(self._rate_limit)
            except urllib.error.URLError as exc:
                logger.warning(
                    f"Geocoder network error: {exc.reason} "
                    f"(attempt {attempt}/{self._max_retries})"
                )
                if attempt < self._max_retries:
                    time.sleep(self._rate_limit)
            except Exception as exc:
                logger.error(f"Geocoder unexpected error: {exc}")
                return None

        logger.error(f"Geocoder request failed after {self._max_retries} attempts")
        return None

    def _enforce_rate_limit(self) -> None:
        """Sleep if needed to respect Nominatim's rate limit."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._rate_limit:
            wait = self._rate_limit - elapsed
            logger.debug(f"Rate-limiting: sleeping {wait:.2f}s")
            time.sleep(wait)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _importance_to_confidence(importance) -> Optional[float]:
        """Convert Nominatim's importance (0–1) to a confidence score."""
        if importance is None:
            return None
        try:
            return max(0.0, min(1.0, float(importance)))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_bbox(bbox_list) -> Optional[List[float]]:
        """
        Parse Nominatim's boundingbox list [south, north, west, east]
        into floats.
        """
        if not bbox_list or len(bbox_list) != 4:
            return None
        try:
            return [float(v) for v in bbox_list]
        except (ValueError, TypeError):
            return None
