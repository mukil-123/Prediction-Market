"""USD math; Kalshi fees conservatively rounded up to a cent (not a protocol replica)."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from math import isfinite
from .schema import probability


def taker_fee(shares: float, price: float, rate: float, venue: str) -> float:
    probability(price)
    if not isfinite(shares) or shares < 0 or not isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError("Invalid shares/fee rate")
    # Remove binary floating-point cancellation at quoted decimal tick boundaries.
    decimal_price = Decimal(str(round(price, 12)))
    raw = Decimal(str(shares)) * Decimal(str(rate)) * decimal_price * (1 - decimal_price)
    if venue == "kalshi":
        return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))
    if venue == "polymarket":
        return float(raw.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP))
    raise ValueError("Unknown fee venue; no silent default")


def kelly_fraction(q: float, total_cost_per_payout: float) -> float:
    """Bankroll fraction for binary payout 1 and total-loss stake c."""
    probability(q)
    if not 0 < total_cost_per_payout < 1:
        return 0.0
    return max(0.0, (q - total_cost_per_payout) / (1 - total_cost_per_payout))


@dataclass(frozen=True)
class Economics:
    probability: float
    shares: float
    entry_price: float
    expected_payoff: float
    entry_cash: float
    fee: float
    slippage: float
    capital_at_risk: float
    gross_ev: float
    net_ev: float
    expected_return_on_risk: float


def economics(q: float, shares: float, ask: float, rate: float, venue: str, slippage_per_share: float = 0) -> Economics:
    probability(q); probability(ask)
    if shares <= 0 or not isfinite(shares) or slippage_per_share < 0 or not isfinite(slippage_per_share):
        raise ValueError("Invalid position or slippage")
    execution_price = min(1.0, ask + slippage_per_share)
    fee = taker_fee(shares, execution_price, rate, venue)
    cash = shares * ask
    slip = shares * (execution_price - ask)
    risk = cash + fee + slip
    net = shares * q - risk
    return Economics(q, shares, ask, shares*q, cash, fee, slip, risk, shares*(q-ask), net, net/risk if risk else 0)


def settlement_pnl(outcome: int, e: Economics) -> float:
    if outcome not in (0, 1):
        raise ValueError("Binary payout required")
    return outcome * e.shares - e.capital_at_risk
