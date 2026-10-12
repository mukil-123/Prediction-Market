"""Deterministic caps; unknown event relationships must share a conservative cluster."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from math import isfinite
from .costs import economics, kelly_fraction

NORMAL_CAP = 0.0025
HARD_CAP = 0.005
CLUSTER_CAP = 0.01


@dataclass(frozen=True)
class RiskPolicy:
    normal_position_fraction: float = NORMAL_CAP
    hard_position_fraction: float = HARD_CAP
    cluster_fraction: float = CLUSTER_CAP
    portfolio_fraction: float = 0.02
    fractional_kelly: float = 0.10

    def __post_init__(self) -> None:
        vals = (self.normal_position_fraction, self.hard_position_fraction, self.cluster_fraction, self.portfolio_fraction, self.fractional_kelly)
        if any(not isfinite(x) or x <= 0 for x in vals):
            raise ValueError("Invalid risk policy")
        if self.normal_position_fraction > NORMAL_CAP or self.hard_position_fraction > HARD_CAP or self.cluster_fraction > CLUSTER_CAP:
            raise ValueError("Hard risk parameters cannot be increased through configuration")
        if self.normal_position_fraction > self.hard_position_fraction or self.fractional_kelly > 1 or self.portfolio_fraction > 0.02:
            raise ValueError("Unsafe risk policy")


def size_position(bankroll: float, cash: float, q: float, ask: float, fee_rate: float,
                  venue: str, depth_shares: float, minimum_shares: float, step: float,
                  cluster_exposure: float = 0, total_exposure: float = 0,
                  slippage: float = 0, policy: RiskPolicy = RiskPolicy()) -> float:
    vals = (bankroll, cash, depth_shares, minimum_shares, step, cluster_exposure, total_exposure)
    if any(not isfinite(v) or v < 0 for v in vals) or minimum_shares <= 0 or step <= 0:
        raise ValueError("Invalid sizing input")
    if bankroll <= 0 or cash <= 0 or not 0 < ask < 1:
        return 0.0
    one = economics(q, 1, ask, fee_rate, venue, slippage)
    # Fee rounding makes this conservative for multishare positions.
    budget = min(cash, bankroll * policy.normal_position_fraction, bankroll * policy.hard_position_fraction,
                 max(0, bankroll * policy.cluster_fraction - cluster_exposure),
                 max(0, bankroll * policy.portfolio_fraction - total_exposure),
                 bankroll * policy.fractional_kelly * kelly_fraction(q, one.capital_at_risk))
    shares = float((Decimal(str(min(depth_shares, budget / one.capital_at_risk))) / Decimal(str(step))).to_integral_value(rounding=ROUND_FLOOR) * Decimal(str(step)))
    if shares < minimum_shares:
        return 0.0
    actual = economics(q, shares, ask, fee_rate, venue, slippage)
    return shares if actual.capital_at_risk <= budget + 1e-10 else 0.0
