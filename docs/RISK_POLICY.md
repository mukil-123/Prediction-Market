# Risk and payout equations

For a YES purchase paying $1 when Y=1, q is forecast probability, a is the executable ask, N is payout shares, F is entry fee, and S is reserved execution slippage in dollars:

```
E[payout]       = N*q
gross EV       = N*(q-a)
capital at risk= N*a + F + S
net EV         = N*q - (N*a+F+S)
return on risk = net EV / capital at risk
realized P&L   = N*Y - (N*a+F+S)
uncertainty EV = q_lower - (a + F/N + S/N), per $1 payout share
```

The required lower-bound excess is a proposed $0.02 per $1 payout share. It is not a 2% return on stake. Spread is paid by purchasing at ask; do not subtract it twice from an ask-based EV. Buying NO later requires its own executable ask, not an invented `1 - YES ask`. Selling before settlement requires executable bid and another fee; v0.1 is YES-only hold-to-settlement.

Official fee snapshots reviewed October 1, 2026:

- Polymarket describes `N*rate*p*(1-p)` on applicable taker markets, market-specific parameters, and rounding to five decimal places. Category tables are not a substitute for a timestamped market fee schedule. More complex fee exponents are rejected by the adapter.
- Kalshi's current July 7, 2026 schedule describes a taker multiplier on `0.07*N*p*(1-p)` and combined-cost rounding to a centicent. **The implementation deliberately rounds estimated Kalshi fees upward to a whole cent**, a conservative upper bound rather than exact venue replication. Its simulation rate is effective rate including any multiplier, which must be verified separately; default overrides are not guessed. Exact combined-cost/sub-cent rounding remains a future adapter task.

Sources: [Polymarket fees](https://docs.polymarket.com/trading/fees), [Kalshi current schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf). Venue/deposit/currency-conversion fees for eventual live operation are separate.

Binary Kelly stake fraction for all-in per-share cost c is `(q-c)/(1-c)` when positive. Sizing uses 10% of that value, further capped by:

| Constraint | Maximum |
|---|---:|
| Normal independent position worst-case loss, including fees | 0.25% |
| Absolute code ceiling | 0.50% |
| Correlated worst-case cluster | 1.00% |
| Proposed total portfolio gross loss cap | 2.00% |

In this milestone all markets share an unvalidated correlation group, so the effective combined cap is 1%. Event identities alone do not establish cross-event or cross-platform independence. Caps use available cash as the sizing bankroll while positions remain open, which is conservative; no unsettled winnings are counted.

Sizes floor to a step; below-minimum orders are skipped. Kalshi research uses whole-share minimum and step 1 as a conservative policy assumption, **not a verified universal venue minimum**. Polymarket live book metadata/minimum must be obtained. Never increase a size to reach a venue minimum.

Example: one whole share at $0.50, effective 0.07 fee, plus $0.005 slippage reserve costs about $0.525 using the conservative fee bound. A 0.25% cap requires about $210 to permit even that order. That is only an execution-size illustration; it establishes neither an adequate income bankroll nor a trading recommendation. Fractional sizes or different prices alter it and must be verified.

No martingale, grid, double-after-loss, outcome chasing, leverage or AI overrides. Code refuses higher hard-cap configuration. Risk-policy changes must be explicit source changes, reviewed as a new version; agents are instructed not to change their own caps.

Monte Carlo: at least 10,000 contiguous-block bootstrap paths for promoted strategies; probability of 10/20/30% drawdown, expected and p95 max drawdown, longest losing streak, tail final loss, 99% loss ruin proxy, and underwater duration in trades. The implemented statistics are conditional on sampled returns. No trading-time/year or recovery guarantee can be inferred from a trade-index bootstrap. Promotion additionally needs marked intratrade drawdowns, event-dependence stress and preregistered calendar horizons.
