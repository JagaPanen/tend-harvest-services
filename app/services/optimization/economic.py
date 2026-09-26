"""Economic Impact Calculation Engine.

Calculates the economic value of spoilage-aware routing compared to baseline.
Formulas:
- Estimated Food Loss Avoided (kg) = Baseline Expected Loss - Optimized Expected Loss
- Economic Loss Avoided (IDR) = Food Loss Avoided (kg) * Commodity Price
- Additional Logistics Cost (IDR) = Optimized Cost - Baseline Cost
- Net Value (IDR) = Economic Loss Avoided - Additional Logistics Cost
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EconomicImpact:
    baseline_loss_kg: float
    optimized_loss_kg: float
    food_loss_avoided_kg: float
    economic_loss_avoided_idr: float
    additional_logistics_cost_idr: float
    net_value_idr: float


def calculate_impact(
    baseline_risk_score: float,
    optimized_risk_score: float,
    total_volume_kg: float,
    avg_commodity_price_idr: float,
    baseline_cost_idr: float,
    optimized_cost_idr: float,
) -> EconomicImpact:
    """Calculate the economic impact of the optimized route vs baseline.
    
    For MVP, we assume Risk Score (0-100) translates directly to a percentage of
    food lost. E.g. Risk Score 80 = 80% loss.
    """
    base_loss_ratio = baseline_risk_score / 100.0
    opt_loss_ratio = optimized_risk_score / 100.0
    
    baseline_loss_kg = total_volume_kg * base_loss_ratio
    optimized_loss_kg = total_volume_kg * opt_loss_ratio
    
    food_loss_avoided = max(0.0, baseline_loss_kg - optimized_loss_kg)
    economic_loss_avoided = food_loss_avoided * avg_commodity_price_idr
    
    additional_cost = optimized_cost_idr - baseline_cost_idr
    
    net_value = economic_loss_avoided - additional_cost
    
    return EconomicImpact(
        baseline_loss_kg=baseline_loss_kg,
        optimized_loss_kg=optimized_loss_kg,
        food_loss_avoided_kg=food_loss_avoided,
        economic_loss_avoided_idr=economic_loss_avoided,
        additional_logistics_cost_idr=additional_cost,
        net_value_idr=net_value,
    )
