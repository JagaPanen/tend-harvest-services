"""Mock routing provider for deterministic testing.

Returns fixed distances based on Haversine calculation with a multiplier to simulate
real-world road detours, plus a fixed average speed for duration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RouteLeg:
    distance_km: float
    duration_hours: float


@dataclass
class RouteResponse:
    distance_km: float
    duration_hours: float
    legs: list[RouteLeg]
    geometry: str = "mock_polyline"


class MockRoutingProvider:
    """A deterministic routing provider for tests."""

    def __init__(self, avg_speed_kmh: float = 40.0, detour_multiplier: float = 1.3):
        self.avg_speed_kmh = avg_speed_kmh
        self.detour_multiplier = detour_multiplier

    def _haversine_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lng / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    async def get_route(
        self, coordinates: list[tuple[float, float]]
    ) -> RouteResponse | None:
        """Calculate a mock route through the given coordinates."""
        if len(coordinates) < 2:
            return None

        legs = []
        total_dist = 0.0
        total_time = 0.0

        for i in range(len(coordinates) - 1):
            lat1, lng1 = coordinates[i]
            lat2, lng2 = coordinates[i + 1]
            
            dist = self._haversine_km(lat1, lng1, lat2, lng2) * self.detour_multiplier
            time = dist / self.avg_speed_kmh
            
            legs.append(RouteLeg(distance_km=dist, duration_hours=time))
            total_dist += dist
            total_time += time

        return RouteResponse(
            distance_km=total_dist,
            duration_hours=total_time,
            legs=legs,
            geometry=f"mock_route_{len(coordinates)}_pts",
        )
