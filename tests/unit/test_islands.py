"""Ferry-aware island distance — Berastagi/Karo (Sumatra) vs Java."""

from app.services.optimization.feasibility import haversine_km
from app.services.routing.islands import (
    classify_island,
    crosses_island,
    expand_path_via_ferries,
    travel_leg_km,
)

BERASTAGI = (-3.195, 98.508)  # Karo, Sumatra
MAGELANG = (-7.5312, 110.3541)  # Java
BANDUNG = (-6.816, 107.617)  # Java


def test_berastagi_is_sumatra():
    assert classify_island(*BERASTAGI) == "sumatra"
    assert classify_island(*MAGELANG) == "java"
    assert crosses_island(*BERASTAGI, *MAGELANG)


def test_sumatra_leg_worse_than_straight_haversine():
    ferry_km, ferry_h = travel_leg_km(*MAGELANG, *BERASTAGI)
    straight = haversine_km(*MAGELANG, *BERASTAGI) * 1.3
    assert ferry_km > straight
    assert ferry_km - straight >= 100  # Merak–Bakauheni wait + sea folded in
    assert ferry_h > straight / 40.0


def test_same_island_java_no_ferry_penalty():
    ferry_km, _ = travel_leg_km(*MAGELANG, *BANDUNG)
    straight = haversine_km(*MAGELANG, *BANDUNG) * 1.3
    assert abs(ferry_km - straight) < 1e-6


def test_expand_path_inserts_merak_bakauheni():
    path = expand_path_via_ferries([MAGELANG, BERASTAGI])
    assert len(path) == 4  # Magelang → Merak → Bakauheni → Berastagi
    assert path[0] == MAGELANG
    assert path[-1] == BERASTAGI
