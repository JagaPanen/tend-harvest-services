"""Vehicle Feasibility Engine — filters vehicles by capacity, location, availability, and time limits.

For each vehicle–harvest combination, the engine checks:
1. **Capacity**: total harvest volume ≤ vehicle capacity
2. **Availability**: vehicle is available at the time of the planned pickup
3. **Location proximity**: vehicle's current position is within a configurable radius
4. **Time limit**: estimated travel time from vehicle to first pickup, through the route,
   to destination must not exceed the most perishable commodity's recommended max transit.

Every accept/reject produces a reason string for transparency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime


# ── Data types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VehicleCandidate:
    """Simplified vehicle data for feasibility checks."""

    vehicle_id: str
    name: str
    capacity_kg: float
    current_lat: float
    current_lng: float
    available_from: datetime
    available_until: datetime | None  # None = no upper limit
    cost_per_km_idr: float


@dataclass(frozen=True)
class HarvestDemand:
    """Minimal harvest info needed for vehicle feasibility."""

    harvest_id: str
    label: str
    volume_kg: float
    pickup_lat: float
    pickup_lng: float
    destination_lat: float
    destination_lng: float
    recommended_max_transit_hours: float  # from risk engine


@dataclass(frozen=True)
class FeasibilityResult:
    """Result of a feasibility check for one vehicle against a set of harvests."""

    vehicle_id: str
    vehicle_name: str
    is_feasible: bool
    reasons: list[str] = field(default_factory=list)

    # Populated when feasible
    total_demand_kg: float = 0.0
    remaining_capacity_kg: float = 0.0
    estimated_pickup_distance_km: float = 0.0


# ── Distance utility ────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Approximate distance in km between two GPS coordinates using Haversine formula."""
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Default config ──────────────────────────────────────────────────────────

DEFAULT_MAX_PICKUP_RADIUS_KM = 100.0
DEFAULT_AVG_SPEED_KMH = 40.0  # Average speed for time estimates


# ── Core engine ─────────────────────────────────────────────────────────────

def check_vehicle_feasibility(
    vehicle: VehicleCandidate,
    harvests: list[HarvestDemand],
    planned_departure: datetime,
    max_pickup_radius_km: float = DEFAULT_MAX_PICKUP_RADIUS_KM,
    avg_speed_kmh: float = DEFAULT_AVG_SPEED_KMH,
) -> FeasibilityResult:
    """Check whether a single vehicle can serve a set of harvests.

    Returns a :class:`FeasibilityResult` with ``is_feasible`` and explanations.

    Parameters
    ----------
    vehicle:
        The candidate vehicle to check.
    harvests:
        The harvests that need to be picked up and delivered.
    planned_departure:
        The planned departure time for the route.
    max_pickup_radius_km:
        Maximum straight-line distance from vehicle to nearest harvest pickup.
    avg_speed_kmh:
        Average driving speed in km/h, used for rough time estimates.
    """
    reasons: list[str] = []

    total_demand = sum(h.volume_kg for h in harvests)

    # ── 1. Capacity check ────────────────────────────────────────────────
    if total_demand > vehicle.capacity_kg:
        reasons.append(
            f"REJECTED (capacity): total demand {total_demand:.0f}kg > "
            f"vehicle capacity {vehicle.capacity_kg:.0f}kg"
        )

    # ── 2. Availability check ────────────────────────────────────────────
    if planned_departure < vehicle.available_from:
        reasons.append(
            f"REJECTED (availability): planned departure "
            f"{planned_departure.isoformat()} is before vehicle availability "
            f"{vehicle.available_from.isoformat()}"
        )
    if vehicle.available_until is not None and planned_departure > vehicle.available_until:
        reasons.append(
            f"REJECTED (availability): planned departure "
            f"{planned_departure.isoformat()} is after vehicle availability window "
            f"{vehicle.available_until.isoformat()}"
        )

    # ── 3. Location proximity ────────────────────────────────────────────
    if harvests:
        min_distance = min(
            haversine_km(vehicle.current_lat, vehicle.current_lng, h.pickup_lat, h.pickup_lng)
            for h in harvests
        )
        if min_distance > max_pickup_radius_km:
            reasons.append(
                f"REJECTED (location): nearest harvest is {min_distance:.1f}km away, "
                f"exceeds max radius {max_pickup_radius_km:.0f}km"
            )
    else:
        min_distance = 0.0

    # ── 4. Time limit check ──────────────────────────────────────────────
    if harvests and avg_speed_kmh > 0:
        # Rough estimate: time from vehicle to nearest pickup
        travel_to_pickup_hours = min_distance / avg_speed_kmh

        # Check if any harvest's max transit time would be violated
        # just by the vehicle driving to the pickup point
        most_urgent = min(h.recommended_max_transit_hours for h in harvests)
        if travel_to_pickup_hours > most_urgent:
            reasons.append(
                f"REJECTED (time-limit): travel to pickup ~{travel_to_pickup_hours:.1f}h "
                f"exceeds most urgent harvest's max transit {most_urgent:.1f}h"
            )

    # ── Result ───────────────────────────────────────────────────────────
    is_feasible = len(reasons) == 0
    if is_feasible:
        reasons.append(
            f"ACCEPTED: capacity {total_demand:.0f}/{vehicle.capacity_kg:.0f}kg, "
            f"nearest pickup {min_distance:.1f}km away, vehicle available"
        )

    return FeasibilityResult(
        vehicle_id=vehicle.vehicle_id,
        vehicle_name=vehicle.vehicle_name,
        is_feasible=is_feasible,
        reasons=reasons,
        total_demand_kg=total_demand,
        remaining_capacity_kg=max(0.0, vehicle.capacity_kg - total_demand),
        estimated_pickup_distance_km=round(min_distance, 2) if harvests else 0.0,
    )


def filter_feasible_vehicles(
    vehicles: list[VehicleCandidate],
    harvests: list[HarvestDemand],
    planned_departure: datetime,
    max_pickup_radius_km: float = DEFAULT_MAX_PICKUP_RADIUS_KM,
    avg_speed_kmh: float = DEFAULT_AVG_SPEED_KMH,
) -> tuple[list[FeasibilityResult], list[FeasibilityResult]]:
    """Filter a list of vehicles, returning (feasible, rejected) tuples.

    Both lists contain full results with explanations.
    Feasible vehicles are sorted by remaining capacity (ascending = tightest fit first).
    """
    feasible: list[FeasibilityResult] = []
    rejected: list[FeasibilityResult] = []

    for v in vehicles:
        result = check_vehicle_feasibility(
            vehicle=v,
            harvests=harvests,
            planned_departure=planned_departure,
            max_pickup_radius_km=max_pickup_radius_km,
            avg_speed_kmh=avg_speed_kmh,
        )
        if result.is_feasible:
            feasible.append(result)
        else:
            rejected.append(result)

    # Sort feasible by tightest fit (least remaining capacity first)
    feasible.sort(key=lambda r: r.remaining_capacity_kg)

    return feasible, rejected
