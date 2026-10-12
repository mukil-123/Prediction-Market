"""Conservative risk grouping until cross-event dependence is measured."""
from .schema import Market


def risk_cluster(market: Market) -> str:
    # An event ID avoids splitting siblings, but is not evidence of independence
    # from other events, instruments, dates, or venues. Milestone 1 has no such evidence.
    return "UNVALIDATED_ALL_MARKETS"
