"""Island classification — Java-first corridor + cross-island cancel."""

from app.services.optimization.feasibility import haversine_km
from app.services.routing.islands import (
    ISLAND_BALI,
    ISLAND_JAVA,
    ISLAND_SUMATRA,
    classify_island,
    crosses_island,
    expand_path_via_ferries,
    is_java,
    multi_island_cancel_message,
    travel_leg_km,
)

# Java corridor samples (seed / FE presets)
JAVA_SITES: list[tuple[float, float, str]] = [
    (-7.5312, 110.3541, "Desa Sawangan / Magelang"),
    (-7.74, 110.9, "Nguter–Ganden / Sukoharjo"),
    (-6.816, 107.617, "Lembang / Bandung"),
    (-7.16, 107.57, "Pangalengan / Bandung"),
    (-7.87, 112.528, "Batu / Malang"),
    (-8.037, 112.785, "Poncokusumo / Malang"),
    (-7.2186, 110.3694, "Bandungan / Semarang"),
    (-7.5186, 110.5189, "Cepogo / Boyolali"),
    (-7.625, 112.907, "Trawas / Mojokerto"),
    (-7.983, 112.63, "Karangploso / Malang"),
    (-8.15, 113.22, "Lumajang highland"),
    (-7.55, 110.82, "Colomadu / Karanganyar"),
    (-6.73, 107.04, "Cisarua / Bogor"),
    (-7.33, 108.22, "Ciamis highland"),
    (-6.943, 107.576, "Pasar Induk Caringin"),
    (-7.834, 110.3912, "Pasar Induk Giwangan"),
    (-7.302, 112.737, "Pasar Induk Wonokromo"),
    (-6.272, 106.87, "Pasar Induk Kramat Jati"),
    (-5.993, 105.928, "Merak ferry (Java)"),
]

BERASTAGI = (-3.195, 98.508)  # Karo, Sumatra
MAGELANG = (-7.5312, 110.3541)
BANDUNG = (-6.816, 107.617)
BEDUGUL = (-8.275, 115.166)
BAKAUHENI = (-5.867, 105.753)


def test_all_java_seed_sites_classify_as_java():
    for lat, lng, label in JAVA_SITES:
        assert is_java(lat, lng), label
        assert classify_island(lat, lng) == ISLAND_JAVA, label


def test_berastagi_is_sumatra_not_java():
    assert not is_java(*BERASTAGI)
    assert classify_island(*BERASTAGI) == ISLAND_SUMATRA
    assert crosses_island(*BERASTAGI, *MAGELANG)


def test_bedugul_is_bali_not_java():
    assert not is_java(*BEDUGUL)
    assert classify_island(*BEDUGUL) == ISLAND_BALI


def test_bakauheni_is_sumatra_merak_is_java():
    assert classify_island(*BAKAUHENI) == ISLAND_SUMATRA
    assert classify_island(-5.993, 105.928) == ISLAND_JAVA


def test_sumatra_leg_worse_than_straight_haversine():
    ferry_km, ferry_h = travel_leg_km(*MAGELANG, *BERASTAGI)
    straight = haversine_km(*MAGELANG, *BERASTAGI) * 1.3
    assert ferry_km > straight
    assert ferry_km - straight >= 100
    assert ferry_h > straight / 40.0


def test_same_island_java_no_ferry_penalty():
    ferry_km, _ = travel_leg_km(*MAGELANG, *BANDUNG)
    straight = haversine_km(*MAGELANG, *BANDUNG) * 1.3
    assert abs(ferry_km - straight) < 1e-6


def test_expand_path_inserts_merak_bakauheni():
    path = expand_path_via_ferries([MAGELANG, BERASTAGI])
    assert len(path) == 4
    assert path[0] == MAGELANG
    assert path[-1] == BERASTAGI


def test_multi_island_cancels_java_plus_berastagi():
    msg = multi_island_cancel_message(
        [
            ("H1 Magelang", *MAGELANG),
            ("H8 Berastagi / Karo", *BERASTAGI),
        ]
    )
    assert msg is not None
    assert "cancelled" in msg.lower()
    assert ISLAND_SUMATRA in msg
    assert ISLAND_JAVA in msg


def test_same_island_java_harvests_ok():
    labeled = [(label, lat, lng) for lat, lng, label in JAVA_SITES[:6]]
    assert multi_island_cancel_message(labeled) is None
