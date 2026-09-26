"""Unit tests for the spoilage risk scoring engine.

Tests validate the PRD formula and edge cases using known examples:
- Tomatoes (Class A, 18h shelf life): 9h harvest + 6h transit → score ~83.33
- Zero time → score 0
- Max time → score capped at 100
- Handling factor > 1.0 accelerates spoilage
- Priority level thresholds
- Recommended max transit calculation
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.services.risk.scorer import (
    CommodityInfo,
    HarvestRiskInput,
    RiskScoreResult,
    calculate_risk_score,
    score_harvest,
    score_harvests,
    _priority_level,
    _recommended_max_transit,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

TOMATO = CommodityInfo(
    perishability_class="A",
    shelf_life_hours=18.0,
    default_price_idr_per_kg=15000.0,
)

CHILI = CommodityInfo(
    perishability_class="B",
    shelf_life_hours=36.0,
    default_price_idr_per_kg=40000.0,
)

POTATO = CommodityInfo(
    perishability_class="D",
    shelf_life_hours=480.0,
    default_price_idr_per_kg=14000.0,
)


# ── calculate_risk_score tests ───────────────────────────────────────────────

class TestCalculateRiskScore:
    """Tests for the core formula function."""

    def test_prd_example_tomato(self):
        """PRD example: tomatoes, 9h since harvest + 6h transit, 18h shelf life → ~83.33."""
        score = calculate_risk_score(
            time_since_harvest_hours=9.0,
            estimated_transit_hours=6.0,
            shelf_life_hours=18.0,
            handling_factor=1.0,
        )
        assert score == pytest.approx(83.33, abs=0.01)

    def test_zero_time(self):
        """Fresh harvest with no transit should have 0 risk."""
        score = calculate_risk_score(
            time_since_harvest_hours=0.0,
            estimated_transit_hours=0.0,
            shelf_life_hours=18.0,
            handling_factor=1.0,
        )
        assert score == 0.0

    def test_exactly_shelf_life(self):
        """When total time == shelf life, score should be 100."""
        score = calculate_risk_score(
            time_since_harvest_hours=12.0,
            estimated_transit_hours=6.0,
            shelf_life_hours=18.0,
            handling_factor=1.0,
        )
        assert score == 100.0

    def test_exceeds_shelf_life_capped(self):
        """Score must never exceed 100 even if total time > shelf life."""
        score = calculate_risk_score(
            time_since_harvest_hours=20.0,
            estimated_transit_hours=10.0,
            shelf_life_hours=18.0,
            handling_factor=1.0,
        )
        assert score == 100.0

    def test_zero_shelf_life(self):
        """Zero shelf life should return max score to prevent division by zero."""
        score = calculate_risk_score(
            time_since_harvest_hours=1.0,
            estimated_transit_hours=0.0,
            shelf_life_hours=0.0,
            handling_factor=1.0,
        )
        assert score == 100.0

    def test_handling_factor_increases_risk(self):
        """A handling factor > 1.0 should increase the risk score."""
        base = calculate_risk_score(9.0, 6.0, 18.0, 1.0)
        worse = calculate_risk_score(9.0, 6.0, 18.0, 1.2)
        assert worse > base

    def test_handling_factor_1_2_example(self):
        """With handling factor 1.2: 100 × (15/18) × 1.2 = 100.0 (capped)."""
        score = calculate_risk_score(9.0, 6.0, 18.0, 1.2)
        assert score == 100.0

    def test_low_risk_potato(self):
        """Potatoes (480h shelf life) should have very low risk for short times."""
        score = calculate_risk_score(
            time_since_harvest_hours=6.0,
            estimated_transit_hours=4.0,
            shelf_life_hours=480.0,
            handling_factor=1.0,
        )
        # 100 × (10 / 480) × 1.0 = 2.08
        assert score == pytest.approx(2.08, abs=0.01)

    def test_chili_moderate(self):
        """Chili (36h shelf life), 9h + 6h transit → 41.67."""
        score = calculate_risk_score(9.0, 6.0, 36.0, 1.0)
        assert score == pytest.approx(41.67, abs=0.01)


# ── _priority_level tests ───────────────────────────────────────────────────

class TestPriorityLevel:
    """Tests for priority level mapping."""

    def test_critical(self):
        assert _priority_level(80.0) == "critical"
        assert _priority_level(100.0) == "critical"

    def test_high(self):
        assert _priority_level(60.0) == "high"
        assert _priority_level(79.9) == "high"

    def test_medium(self):
        assert _priority_level(40.0) == "medium"
        assert _priority_level(59.9) == "medium"

    def test_low(self):
        assert _priority_level(0.0) == "low"
        assert _priority_level(39.9) == "low"


# ── _recommended_max_transit tests ───────────────────────────────────────────

class TestRecommendedMaxTransit:
    """Tests for max transit time calculation."""

    def test_fresh_tomato(self):
        """Fresh tomato (0h since harvest): max transit before score 80 = 14.4h."""
        max_t = _recommended_max_transit(0.0, 18.0, 1.0, target_score=80.0)
        assert max_t == pytest.approx(14.4, abs=0.01)

    def test_tomato_9h_since_harvest(self):
        """Tomato 9h since harvest: max transit = 14.4 - 9 = 5.4h."""
        max_t = _recommended_max_transit(9.0, 18.0, 1.0, target_score=80.0)
        assert max_t == pytest.approx(5.4, abs=0.01)

    def test_already_past_threshold(self):
        """If harvest is already past target, result should be 0."""
        max_t = _recommended_max_transit(15.0, 18.0, 1.0, target_score=80.0)
        assert max_t == 0.0

    def test_handling_factor_reduces_transit(self):
        """Higher handling factor should reduce the max transit time."""
        base = _recommended_max_transit(5.0, 18.0, 1.0, target_score=80.0)
        worse = _recommended_max_transit(5.0, 18.0, 1.3, target_score=80.0)
        assert worse < base


# ── score_harvest (integration) ──────────────────────────────────────────────

class TestScoreHarvest:
    """Tests for the full score_harvest function."""

    def test_produces_valid_result(self):
        """score_harvest should return a complete RiskScoreResult."""
        now = datetime(2026, 9, 27, 6, 0, 0, tzinfo=timezone.utc)
        harvest = HarvestRiskInput(
            harvest_id="h1",
            label="A",
            commodity=TOMATO,
            harvested_at=now - timedelta(hours=9),
            handling_factor=1.0,
            estimated_transit_hours=6.0,
        )

        result = score_harvest(harvest, reference_time=now)

        assert isinstance(result, RiskScoreResult)
        assert result.harvest_id == "h1"
        assert result.label == "A"
        assert result.perishability_class == "A"
        assert result.urgency_score == pytest.approx(83.33, abs=0.01)
        assert result.priority_level == "critical"
        assert result.time_since_harvest_hours == pytest.approx(9.0, abs=0.01)
        assert result.formula_version == "v1.0.0"
        assert "score 83.33" in result.explanation

    def test_naive_datetime_treated_as_utc(self):
        """A naive harvested_at should be treated as UTC without error."""
        now = datetime(2026, 9, 27, 6, 0, 0, tzinfo=timezone.utc)
        harvest = HarvestRiskInput(
            harvest_id="h2",
            label="B",
            commodity=TOMATO,
            harvested_at=datetime(2026, 9, 27, 3, 0, 0),  # naive
            estimated_transit_hours=0.0,
        )

        result = score_harvest(harvest, reference_time=now)
        assert result.time_since_harvest_hours == pytest.approx(3.0, abs=0.01)

    def test_future_harvest_time_gives_zero(self):
        """If harvested_at is in the future, time since harvest should be 0."""
        now = datetime(2026, 9, 27, 6, 0, 0, tzinfo=timezone.utc)
        harvest = HarvestRiskInput(
            harvest_id="h3",
            label="C",
            commodity=POTATO,
            harvested_at=now + timedelta(hours=2),
            estimated_transit_hours=0.0,
        )

        result = score_harvest(harvest, reference_time=now)
        assert result.time_since_harvest_hours == 0.0
        assert result.urgency_score == 0.0


# ── score_harvests (multiple) ────────────────────────────────────────────────

class TestScoreHarvests:
    """Tests for scoring multiple harvests at once."""

    def test_sorted_by_urgency_descending(self):
        """Results should be sorted by urgency_score, highest first."""
        now = datetime(2026, 9, 27, 6, 0, 0, tzinfo=timezone.utc)
        harvests = [
            HarvestRiskInput(
                harvest_id="low",
                label="Potato",
                commodity=POTATO,
                harvested_at=now - timedelta(hours=2),
                estimated_transit_hours=4.0,
            ),
            HarvestRiskInput(
                harvest_id="high",
                label="Tomato",
                commodity=TOMATO,
                harvested_at=now - timedelta(hours=9),
                estimated_transit_hours=6.0,
            ),
            HarvestRiskInput(
                harvest_id="mid",
                label="Chili",
                commodity=CHILI,
                harvested_at=now - timedelta(hours=9),
                estimated_transit_hours=6.0,
            ),
        ]

        results = score_harvests(harvests, reference_time=now)

        assert len(results) == 3
        assert results[0].harvest_id == "high"  # tomato highest risk
        assert results[1].harvest_id == "mid"   # chili medium risk
        assert results[2].harvest_id == "low"   # potato lowest risk
        assert results[0].urgency_score > results[1].urgency_score > results[2].urgency_score
