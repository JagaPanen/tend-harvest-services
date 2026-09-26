"""Load Consolidation Engine — evaluates grouping multiple harvests.

Determines if multiple harvests can be safely consolidated into a single vehicle route.
Checks:
1. **Capacity**: combined volume ≤ vehicle capacity
2. **Detour limit**: the total estimated distance is within acceptable bounds compared to direct routes
3. **Spoilage limit**: the estimated total time (transit + loading) does not exceed the most
   perishable commodity's recommended max transit time.

Produces human-readable explanations for accepted/rejected combinations.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from app.services.optimization.feasibility import (
    DEFAULT_AVG_SPEED_KMH,
    HarvestDemand,
    VehicleCandidate,
    haversine_km,
)


@dataclass(frozen=True)
class ConsolidationResult:
    """Result of evaluating a specific group of harvests for a vehicle."""

    vehicle_id: str
    harvest_ids: tuple[str, ...]
    is_feasible: bool
    reasons: list[str] = field(default_factory=list)

    total_volume_kg: float = 0.0
    estimated_distance_km: float = 0.0
    estimated_duration_hours: float = 0.0


def _estimate_route_distance(
    start_lat: float, start_lng: float, pickups: list[tuple[float, float]], destinations: list[tuple[float, float]]
) -> float:
    """Estimate total route distance using greedy nearest-neighbor for pickups then destinations.
    
    This is a rough proxy used to quickly reject bad consolidations.
    Route: Vehicle -> all Pickups -> all Destinations.
    """
    total_distance = 0.0
    current_lat, current_lng = start_lat, start_lng

    # Visit all pickups greedily
    unvisited_pickups = list(pickups)
    while unvisited_pickups:
        nearest = min(
            unvisited_pickups,
            key=lambda loc: haversine_km(current_lat, current_lng, loc[0], loc[1]),
        )
        total_distance += haversine_km(current_lat, current_lng, nearest[0], nearest[1])
        current_lat, current_lng = nearest
        unvisited_pickups.remove(nearest)

    # Visit all destinations greedily
    unvisited_dests = list(destinations)
    while unvisited_dests:
        nearest = min(
            unvisited_dests,
            key=lambda loc: haversine_km(current_lat, current_lng, loc[0], loc[1]),
        )
        total_distance += haversine_km(current_lat, current_lng, nearest[0], nearest[1])
        current_lat, current_lng = nearest
        unvisited_dests.remove(nearest)

    return total_distance


def evaluate_consolidation(
    vehicle: VehicleCandidate,
    harvests: list[HarvestDemand],
    avg_speed_kmh: float = DEFAULT_AVG_SPEED_KMH,
    loading_time_hours_per_pickup: float = 0.5,
    max_detour_multiplier: float = 1.5,
) -> ConsolidationResult:
    """Evaluate if a group of harvests can be consolidated into the given vehicle.

    Parameters
    ----------
    vehicle:
        The vehicle carrying the load.
    harvests:
        List of harvests to consider consolidating.
    avg_speed_kmh:
        Average speed for time estimation.
    loading_time_hours_per_pickup:
        Fixed time added for each pickup stop.
    max_detour_multiplier:
        How much longer the consolidated route can be compared to the direct route
        to the farthest pickup + destination.
    """
    reasons: list[str] = []
    harvest_ids = tuple(h.harvest_id for h in harvests)

    if not harvests:
        return ConsolidationResult(
            vehicle_id=vehicle.vehicle_id,
            harvest_ids=harvest_ids,
            is_feasible=False,
            reasons=["REJECTED: Empty harvest list"],
        )

    # ── 1. Capacity Check ────────────────────────────────────────────────
    total_volume = sum(h.volume_kg for h in harvests)
    if total_volume > vehicle.capacity_kg:
        reasons.append(
            f"REJECTED (capacity): total volume {total_volume:.0f}kg exceeds "
            f"vehicle capacity {vehicle.capacity_kg:.0f}kg"
        )

    # ── 2. Time & Detour Estimation ──────────────────────────────────────
    pickups = [(h.pickup_lat, h.pickup_lng) for h in harvests]
    destinations = [(h.destination_lat, h.destination_lng) for h in harvests]
    
    est_distance = _estimate_route_distance(
        vehicle.current_lat, vehicle.current_lng, pickups, destinations
    )
    
    # Compare against direct distances to see if detour is too large
    # Direct distance = Vehicle -> Pickup -> Destination
    max_direct_dist = 0.0
    for h in harvests:
        dist = haversine_km(vehicle.current_lat, vehicle.current_lng, h.pickup_lat, h.pickup_lng)
        dist += haversine_km(h.pickup_lat, h.pickup_lng, h.destination_lat, h.destination_lng)
        max_direct_dist = max(max_direct_dist, dist)

    if max_direct_dist > 0 and est_distance > max_direct_dist * max_detour_multiplier:
        reasons.append(
            f"REJECTED (detour): estimated route {est_distance:.1f}km is too long "
            f"compared to max direct route {max_direct_dist:.1f}km (>{max_detour_multiplier}x)"
        )

    # ── 3. Spoilage Time Limit Check ─────────────────────────────────────
    if avg_speed_kmh > 0:
        est_transit_time = est_distance / avg_speed_kmh
        total_loading_time = len(harvests) * loading_time_hours_per_pickup
        total_time = est_transit_time + total_loading_time

        most_urgent = min(h.recommended_max_transit_hours for h in harvests)
        
        if total_time > most_urgent:
            reasons.append(
                f"REJECTED (spoilage): total estimated time {total_time:.1f}h "
                f"exceeds most urgent harvest's max transit {most_urgent:.1f}h"
            )
            
    else:
        total_time = 0.0

    is_feasible = len(reasons) == 0
    if is_feasible:
        labels = "+".join(h.label for h in harvests)
        reasons.append(
            f"ACCEPTED: {labels} consolidated. Total volume {total_volume:.0f}kg, "
            f"est distance {est_distance:.1f}km, est time {total_time:.1f}h."
        )

    return ConsolidationResult(
        vehicle_id=vehicle.vehicle_id,
        harvest_ids=harvest_ids,
        is_feasible=is_feasible,
        reasons=reasons,
        total_volume_kg=total_volume,
        estimated_distance_km=round(est_distance, 2),
        estimated_duration_hours=round(total_time, 2),
    )


def generate_candidate_groups(
    harvests: list[HarvestDemand], max_group_size: int = 3
) -> list[tuple[HarvestDemand, ...]]:
    """Generate all possible combinations of harvests up to max_group_size.
    
    Includes single items, pairs, triplets, etc.
    """
    candidates = []
    # Size 1 to max_group_size
    for size in range(1, min(len(harvests), max_group_size) + 1):
        for combo in itertools.combinations(harvests, size):
            candidates.append(combo)
    return candidates
