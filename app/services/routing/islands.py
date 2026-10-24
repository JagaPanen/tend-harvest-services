"""Indonesia island classification + ferry-aware road distance.

Phase 1 focuses on **Java** (Banten → Banyuwangi, incl. Madura) — the primary
JagaPanen harvest corridor. Other major islands are tagged with coarse boxes so
cross-island scenarios can be cancelled; finer boxes come later.

Straight-line / Mapbox driving across the sea understates Java↔Sumatra
(e.g. Berastagi / Karo) and Java↔Bali hops. Cross-island legs use ferry
corridors when distance is estimated; preview/optimize abort when pickups
span more than one island.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.optimization.feasibility import haversine_km

# ── Island ids (stable API / cancel messages) ───────────────────────────────
ISLAND_JAVA = "java"
ISLAND_SUMATRA = "sumatra"
ISLAND_BALI = "bali"
ISLAND_KALIMANTAN = "kalimantan"
ISLAND_SULAWESI = "sulawesi"
ISLAND_NUSA_TENGGARA = "nusa_tenggara"
ISLAND_PAPUA = "papua"
ISLAND_MALUKU = "maluku"
ISLAND_OTHER = "other"

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
        island_a=ISLAND_JAVA,
        port_a=(-5.993, 105.928),
        island_b=ISLAND_SUMATRA,
        port_b=(-5.867, 105.753),
        sea_km=28.0,
        wait_hours=3.5,
    ),
    FerryLink(
        island_a=ISLAND_JAVA,
        port_a=(-8.140, 114.397),
        island_b=ISLAND_BALI,
        port_b=(-8.162, 114.437),
        sea_km=6.0,
        wait_hours=2.0,
    ),
)


def is_java(lat: float, lng: float) -> bool:
    """True if the point lies on Java (incl. Madura) — primary product corridor.

    Bounding box (approx.):
      lng 105.05°E (Anyer/Merak) → 114.65°E (Banyuwangi, west of Bali ferry)
      lat  5.50°S (Jakarta north coast) → 8.85°S (south coast / Nusa Barung)

    Covers Magelang, Bandung, Semarang, Solo, Malang, Batu, Bogor, Ciamis,
    Lumajang, Mojokerto, and Madura. Excludes Lampung/Bakauheni (Sumatra)
    and Gilimanuk (Bali).
    """
    if not (105.05 <= lng <= 114.65 and -8.85 <= lat <= -5.50):
        return False
    # Sunda Strait: Bakauheni sits NW of Merak — keep it off Java
    if lng < 105.88 and lat > -5.95:
        return False
    return True


def classify_island(lat: float, lng: float) -> str:
    """Tag a WGS84 point with a major Indonesian island id.

    Order matters: Bali edge before Java; Java before Sumatra so Merak stays
    on Java and Bakauheni/Berastagi stay on Sumatra.
    """
    # Bali (Bedugul / Kintamani) — east of Java tip
    if 114.42 <= lng <= 115.75 and -8.95 <= lat <= -8.05:
        return ISLAND_BALI

    # Java first (product focus)
    if is_java(lat, lng):
        return ISLAND_JAVA

    # Sumatra incl. Berastagi/Karo (~98.5°E, 3.2°S) and Bakauheni
    if 95.0 <= lng < 106.2 and -6.15 <= lat <= 6.5:
        return ISLAND_SUMATRA

    # Coarse stubs — refine in later phases
    if 108.5 <= lng <= 119.5 and -4.5 <= lat <= 7.5 and not is_java(lat, lng):
        # Kalimantan sits north of the Java Sea; exclude already-classified Java
        if lat > -4.2:
            return ISLAND_KALIMANTAN
    if 118.5 <= lng <= 125.5 and -6.0 <= lat <= 2.0:
        return ISLAND_SULAWESI
    if 114.7 <= lng <= 127.5 and -11.0 <= lat <= -8.0:
        return ISLAND_NUSA_TENGGARA
    if 124.0 <= lng <= 141.0 and -9.0 <= lat <= 0.5:
        if lng >= 130.0:
            return ISLAND_PAPUA
        return ISLAND_MALUKU

    return ISLAND_OTHER


def same_island(lat1: float, lng1: float, lat2: float, lng2: float) -> bool:
    return classify_island(lat1, lng1) == classify_island(lat2, lng2)


def crosses_island(lat1: float, lng1: float, lat2: float, lng2: float) -> bool:
    a = classify_island(lat1, lng1)
    b = classify_island(lat2, lng2)
    if a == ISLAND_OTHER or b == ISLAND_OTHER:
        return False
    return a != b


def multi_island_cancel_message(
    labeled_points: list[tuple[str, float, float]],
) -> str | None:
    """If labeled (name, lat, lng) points span 2+ known islands, return a cancel reason.

    Phase 1 guidance: keep scenarios on **Java only** (or entirely on one other
    island). Mixing Java + Sumatra (Berastagi/Karo) or Java + Bali is rejected.
    """
    by_island: dict[str, list[str]] = {}
    for name, lat, lng in labeled_points:
        island = classify_island(lat, lng)
        if island == ISLAND_OTHER:
            continue
        by_island.setdefault(island, []).append(name)

    if len(by_island) <= 1:
        return None

    parts: list[str] = []
    for island, names in sorted(by_island.items()):
        sample = ", ".join(names[:4])
        if len(names) > 4:
            sample += f" (+{len(names) - 4} more)"
        parts.append(f"{island}: {sample}")

    return (
        "Optimization cancelled: pickups span different islands ("
        + "; ".join(parts)
        + "). Phase 1 supports one island per scenario — prefer all-Java "
        "pickups (remove Sumatra/Bali sites such as Berastagi or Bedugul)."
    )


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
        if i1 != i2 and i1 != ISLAND_OTHER and i2 != ISLAND_OTHER:
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
    """
    i1 = classify_island(lat1, lng1)
    i2 = classify_island(lat2, lng2)

    if i1 == i2:
        dist = haversine_km(lat1, lng1, lat2, lng2) * road_multiplier
        return dist, dist / avg_speed_kmh

    link = _ferry_for(i1, i2)
    if link is None:
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
