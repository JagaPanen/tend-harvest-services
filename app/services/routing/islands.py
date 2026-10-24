"""Indonesia island classification + ferry-aware road distance.

Straight-line / Mapbox driving across the sea understates Java↔Sumatra
(e.g. Berastagi / Karo) and Java↔Bali hops. Cross-island legs are routed
via known ferry corridors and include sea + truck queue time.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.optimization.feasibility import haversine_km

# Equivalent road km for waiting / boarding (so TSP + cost feel the ferry).
DEFAULT_AVG_SPEED_KMH = 40.0
UNKNOWN_ISLAND_PENALTY_KM = 500.0


@dataclass(frozen=True)
class FerryLink:
    """Sea link between two islands (ports as lat, lng)."""

    island_a: str
    port_a: tuple[float, float]
    island_b: str
    port_b: tuple[float, float]
    sea_km: float
    wait_hours: float


# Merak (Java) ↔ Bakauheni (Sumatra); Ketapang (Java) ↔ Gilimanuk (Bali)
FERRY_LINKS: tuple[FerryLink, ...] = (
    FerryLink(
        island_a="java",
        port_a=(-5.993, 105.928),
        island_b="sumatra",
        port_b=(-5.867, 105.753),
        sea_km=28.0,
        wait_hours=3.5,
    ),
    FerryLink(
        island_a="java",
        port_a=(-8.140, 114.397),
        island_b="bali",
        port_b=(-8.162, 114.437),
        sea_km=6.0,
        wait_hours=2.0,
    ),
)


def classify_island(lat: float, lng: float) -> str:
    """Rough island tag for Indonesia harvest corridors used in JagaPanen."""
    # Bali (Bedugul / Kintamani, etc.)
    if 114.35 <= lng <= 115.9 and -8.95 <= lat <= -8.0:
        return "bali"
    # Java (Magelang, Bandung, Malang, Semarang, …) — checked before Sumatra
    # so western tip near Merak stays on Java.
    if 105.5 <= lng < 114.4 and -9.0 <= lat <= -5.4:
        return "java"
    # Sumatra incl. Berastagi / Karo (~98.5°E, 3.2°S) and Lampung ports
    if 95.0 <= lng < 106.5 and -6.2 <= lat <= 6.5:
        return "sumatra"
    if lng >= 114.4:
        return "nusa_tenggara"
    return "other"


def same_island(lat1: float, lng1: float, lat2: float, lng2: float) -> bool:
    return classify_island(lat1, lng1) == classify_island(lat2, lng2)


def crosses_island(lat1: float, lng1: float, lat2: float, lng2: float) -> bool:
    a = classify_island(lat1, lng1)
    b = classify_island(lat2, lng2)
    if a == "other" or b == "other":
        return False
    return a != b


def _ferry_for(island_a: str, island_b: str) -> FerryLink | None:
    key = frozenset({island_a, island_b})
    for link in FERRY_LINKS:
        if frozenset({link.island_a, link.island_b}) == key:
            return link
    return None


def _ports_for_trip(
    from_island: str, to_island: str, link: FerryLink
) -> tuple[tuple[float, float], tuple[float, float]]:
    if from_island == link.island_a and to_island == link.island_b:
        return link.port_a, link.port_b
    return link.port_b, link.port_a


def expand_path_via_ferries(
    coordinates: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Insert ferry port waypoints so map polylines show the sea crossing."""
    if len(coordinates) < 2:
        return list(coordinates)
    out: list[tuple[float, float]] = [coordinates[0]]
    for a, b in zip(coordinates, coordinates[1:]):
        i1, i2 = classify_island(a[0], a[1]), classify_island(b[0], b[1])
        if i1 != i2 and i1 != "other" and i2 != "other":
            link = _ferry_for(i1, i2)
            if link is not None:
                port_dep, port_arr = _ports_for_trip(i1, i2, link)
                out.append(port_dep)
                out.append(port_arr)
        out.append(b)
    return out


def travel_leg_km(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    *,
    road_multiplier: float = 1.3,
    avg_speed_kmh: float = DEFAULT_AVG_SPEED_KMH,
) -> tuple[float, float]:
    """Road (+ ferry) distance and duration between two points.

    Same island: haversine × road multiplier.
    Cross-island: drive to departure ferry port + sea + wait + drive from arrival port.
    Wait time is also folded into distance (avg_speed × hours) so optimizers
    and Rp/km cost treat the ferry as a real penalty — Sumatra pickups worsen the plan.
    """
    i1 = classify_island(lat1, lng1)
    i2 = classify_island(lat2, lng2)

    if i1 == i2:
        dist = haversine_km(lat1, lng1, lat2, lng2) * road_multiplier
        return dist, dist / avg_speed_kmh

    link = _ferry_for(i1, i2)
    if link is None:
        # e.g. Sumatra↔Bali without a direct link: force via heavy penalty
        dist = (
            haversine_km(lat1, lng1, lat2, lng2) * road_multiplier
            + UNKNOWN_ISLAND_PENALTY_KM
        )
        return dist, dist / avg_speed_kmh + 6.0

    port_dep, port_arr = _ports_for_trip(i1, i2, link)
    road_km = (
        haversine_km(lat1, lng1, port_dep[0], port_dep[1])
        + haversine_km(port_arr[0], port_arr[1], lat2, lng2)
    ) * road_multiplier
    wait_equiv_km = link.wait_hours * avg_speed_kmh
    dist = road_km + link.sea_km + wait_equiv_km
    hours = road_km / avg_speed_kmh + link.wait_hours + (link.sea_km / 20.0)
    return dist, hours
