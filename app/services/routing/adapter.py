"""Routing adapter — Mapbox Directions, then OSRM, then Haversine mock.

Coordinate convention for get_route: list of (lat, lng) pairs.
"""

from __future__ import annotations
import json
import httpx
from app.core.config import settings
from app.services.routing.mock_provider import (
    MockRoutingProvider,
    RouteLeg,
    RouteResponse,
)


class RoutingAdapter:
    """Adapter for routing APIs (Mapbox → OSRM → Mock)."""

    def __init__(self):
        self.mock_provider = MockRoutingProvider()
        self._cache: dict[tuple[tuple[float, float], ...], RouteResponse] = {}

    @property
    def has_mapbox(self) -> bool:
        token = (settings.mapbox_access_token or "").strip()
        return bool(token) and token != "your_mapbox_token_here"

    async def get_route(
        self, coordinates: list[tuple[float, float]]
    ) -> RouteResponse | None:
        """Get driving route for a sequence of coordinates (lat, lng)."""
        if len(coordinates) < 2:
            return None

        cache_key = tuple(coordinates)
        if cache_key in self._cache:
            return self._cache[cache_key]

        from app.services.routing.islands import crosses_island

        # Driving APIs treat sea gaps as continuous road; force ferry-aware mock
        # whenever any leg crosses islands (e.g. Java ↔ Berastagi/Karo Sumatra).
        cross_island = any(
            crosses_island(a[0], a[1], b[0], b[1])
            for a, b in zip(coordinates, coordinates[1:])
        )

        response: RouteResponse | None = None
        if cross_island:
            response = await self.mock_provider.get_route(coordinates)
        else:
            if self.has_mapbox:
                response = await self._fetch_mapbox(coordinates)
            if response is None:
                response = await self._fetch_osrm(coordinates)
            if response is None:
                response = await self.mock_provider.get_route(coordinates)

        if response:
            self._cache[cache_key] = response
        return response

    async def _fetch_mapbox(
        self, coordinates: list[tuple[float, float]]
    ) -> RouteResponse | None:
        coord_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coord_str}"
        params = {
            "access_token": settings.mapbox_access_token,
            "geometries": "geojson",
            "overview": "full",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return None
            return self._parse_osrm_like(data["routes"][0])
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

    async def _fetch_osrm(
        self, coordinates: list[tuple[float, float]]
    ) -> RouteResponse | None:
        """Public OSRM (or configured base) when Mapbox key is missing/fails."""
        base = (settings.osrm_base_url or "").rstrip("/")
        if not base:
            return None
        coord_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
        url = f"{base}/route/v1/driving/{coord_str}"
        params = {"overview": "full", "geometries": "geojson"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return None
            return self._parse_osrm_like(data["routes"][0])
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

    def _parse_osrm_like(self, route: dict) -> RouteResponse:
        distance_km = float(route["distance"]) / 1000.0
        duration_hours = float(route["duration"]) / 3600.0
        legs = [
            RouteLeg(
                distance_km=float(leg["distance"]) / 1000.0,
                duration_hours=float(leg["duration"]) / 3600.0,
            )
            for leg in route.get("legs", [])
        ]
        geometry = json.dumps(route.get("geometry") or {})
        return RouteResponse(
            distance_km=distance_km,
            duration_hours=duration_hours,
            legs=legs,
            geometry=geometry,
        )
