"""Mock routing provider for deterministic testing.

Returns distances via ferry-aware travel legs (haversine + island ferries)
with a road detour multiplier and average speed for duration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.services.routing.islands import expand_path_via_ferries, travel_leg_km


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

            dist, time = travel_leg_km(
                lat1,
                lng1,
                lat2,
                lng2,
                road_multiplier=self.detour_multiplier,
                avg_speed_kmh=self.avg_speed_kmh,
            )

            legs.append(RouteLeg(distance_km=dist, duration_hours=time))
            total_dist += dist
            total_time += time

        # GeoJSON with ferry ports inserted so the FE map shows island hops clearly
        path = expand_path_via_ferries(coordinates)
        line = {
            "type": "LineString",
            "coordinates": [[lng, lat] for lat, lng in path],
        }
        return RouteResponse(
            distance_km=total_dist,
            duration_hours=total_time,
            legs=legs,
            geometry=json.dumps(line),
        )
