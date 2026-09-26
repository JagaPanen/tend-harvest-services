"""Mapbox Directions API Adapter.

Fetches route distance, duration, and geometry from Mapbox.
Falls back to the mock provider if the API token is not configured or in tests.
Caches responses in memory for the duration of an optimization run to avoid
repeated identical requests.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.services.routing.mock_provider import MockRoutingProvider, RouteResponse, RouteLeg


class RoutingAdapter:
    """Adapter for routing APIs (Mapbox + Mock fallback)."""

    def __init__(self):
        self.mock_provider = MockRoutingProvider()
        self.use_mock = not bool(settings.mapbox_access_token)
        # Simple in-memory cache: tuple of (lat, lng) -> RouteResponse
        self._cache: dict[tuple[tuple[float, float], ...], RouteResponse] = {}

    async def get_route(
        self, coordinates: list[tuple[float, float]]
    ) -> RouteResponse | None:
        """Get driving route for a sequence of coordinates (lat, lng).
        
        Uses cache if identical coordinate sequence was requested before.
        """
        if len(coordinates) < 2:
            return None

        # Cache key must be hashable
        cache_key = tuple(coordinates)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.use_mock:
            response = await self.mock_provider.get_route(coordinates)
        else:
            response = await self._fetch_mapbox(coordinates)
            if not response:
                # Fallback to mock on API failure
                response = await self.mock_provider.get_route(coordinates)

        if response:
            self._cache[cache_key] = response

        return response

    async def _fetch_mapbox(
        self, coordinates: list[tuple[float, float]]
    ) -> RouteResponse | None:
        """Fetch route from Mapbox Directions API."""
        # Mapbox expects longitude,latitude
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

            if data["code"] != "Ok" or not data.get("routes"):
                return None

            route = data["routes"][0]
            
            # Mapbox returns distance in meters, duration in seconds
            distance_km = route["distance"] / 1000.0
            duration_hours = route["duration"] / 3600.0

            legs = []
            for leg in route["legs"]:
                legs.append(
                    RouteLeg(
                        distance_km=leg["distance"] / 1000.0,
                        duration_hours=leg["duration"] / 3600.0,
                    )
                )

            # Geometry is a GeoJSON LineString dict
            import json
            geometry = json.dumps(route["geometry"])

            return RouteResponse(
                distance_km=distance_km,
                duration_hours=duration_hours,
                legs=legs,
                geometry=geometry,
            )
            
        except (httpx.RequestError, httpx.HTTPStatusError, KeyError):
            return None
