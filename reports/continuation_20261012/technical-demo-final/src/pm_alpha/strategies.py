"""Independent strategy registry; unimplemented branches cannot emit signals."""
from dataclasses import dataclass
from typing import Protocol
from .models import Forecast


class ProbabilityStrategy(Protocol):
    version: str
    def forecast(self,market_probability:float)->Forecast: ...


@dataclass(frozen=True)
class Gates:
    timestamp_valid: bool = False
    realistic_execution: bool = False
    positive_net_lower_ci: bool = False
    superior_forecasts: bool = False
    drawdown_acceptable: bool = False
    temporal_robustness: bool = False
    parameter_robustness: bool = False
    monte_carlo_survival: bool = False
    untouched_oos: bool = False
    forward_shadow: bool = False
    compliance: bool = False


STATES=("IDEA","DATA_CHECK","BACKTEST","VALIDATION","OOS","SHADOW","LIVE_SMALL","PROMOTED","RETIRED")


def transition(current:str,target:str,g:Gates)->str:
    if current not in STATES or target not in STATES:raise ValueError("Unknown strategy state")
    if current=="RETIRED":raise ValueError("Retired versions cannot be revived")
    if target=="RETIRED":return target
    if STATES.index(target)!=STATES.index(current)+1:raise ValueError("No skipped gates")
    required={"DATA_CHECK":True,"BACKTEST":g.timestamp_valid,
              "VALIDATION":g.timestamp_valid and g.realistic_execution and g.positive_net_lower_ci,
              "OOS":g.superior_forecasts and g.temporal_robustness and g.parameter_robustness,
              "SHADOW":g.untouched_oos and g.drawdown_acceptable and g.monte_carlo_survival,
              "LIVE_SMALL":False, # Deliberately unavailable in milestone 1.
              "PROMOTED":all(vars(g).values())}
    if not required[target]:raise ValueError("Acceptance gate failed or live milestone unavailable")
    return target


PLACEHOLDERS={"PM-W1":"DATA_CHECK: original timestamped forecast vintages required",
              "PM-S1":"IDEA: objective event model and data feasibility pending",
              "PM-M1":"IDEA: executable depth and latency evidence pending",
              "PM-A1":"IDEA: optional only; no model API dependency"}
