"""Small, independently estimated PM-C1 calibration baseline."""
from dataclasses import dataclass
from math import sqrt
from .schema import probability


def bucket(p: float, bins: int = 20) -> int:
    probability(p)
    if bins < 1:
        raise ValueError("Positive bin count required")
    return min(int(p * bins), bins - 1)


def wilson(successes: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = successes / n
    d = 1 + z*z/n
    centre = (p + z*z/(2*n))/d
    half = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return max(0, centre-half), min(1, centre+half)


@dataclass(frozen=True)
class Forecast:
    probability: float
    lower: float
    upper: float
    sample_size: int


class BinCalibration:
    def __init__(self, bins: int = 20, prior_strength: float = 20) -> None:
        if bins < 1 or prior_strength <= 0:
            raise ValueError("Invalid calibration settings")
        self.bins, self.prior_strength = bins, prior_strength
        self.counts = [0] * bins
        self.wins = [0] * bins
        self.fitted = False

    def fit(self, pairs: list[tuple[float, int]]) -> "BinCalibration":
        self.counts = [0] * self.bins; self.wins = [0] * self.bins
        for p, y in pairs:
            if y not in (0, 1):
                raise ValueError("Binary label required")
            i = bucket(p, self.bins); self.counts[i] += 1; self.wins[i] += y
        self.fitted = True
        return self

    def predict(self, p: float) -> Forecast:
        if not self.fitted:
            raise ValueError("Model not fitted")
        i = bucket(p, self.bins); n = self.counts[i]; wins = self.wins[i]
        q = (wins + self.prior_strength*p)/(n + self.prior_strength)
        # An empirical bin interval, NOT a posterior/individual-event confidence claim.
        lo, hi = wilson(wins, n)
        return Forecast(q, min(lo, q), max(hi, q), n)

    def payload(self) -> dict:
        return {"bins": self.bins, "prior_strength": self.prior_strength, "counts": self.counts, "wins": self.wins}
