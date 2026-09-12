# CoinDCX Futures Research

Dedicated Futures-only microstructure and Delta research repository.

## Objective

**Futures aggressive order flow (Delta) -> subsequent Futures price movement.**

This repository is intentionally separate from the Spot+Futures production repository. Its Actions workflows, research history, compact data and operational state are isolated at the repository boundary.

## Current pipeline

`continuous-collector.yml` -> raw Futures artifact -> exact-artifact processing -> Futures 1s/1m/3m features -> Futures Delta strategy research -> isolated compact history -> storage lifecycle/report.

The collector is operator-controlled. `Run workflow` accepts:

- `duration_minutes`: 5-230 minutes; default 30.
- `continue_chain`: `false` for one standalone batch; `true` to automatically start the next batch after each successful raw batch.

A chained run carries the selected duration forward. There is no collector cron and no GitHub supervisor/watchdog. External supervision is handled outside GitHub.

## Captured market data

Each production batch captures four public CoinDCX Futures market-data streams for the six canonical instruments:

- Futures trades
- Futures price-change events
- Futures current-prices events
- Futures 50-level orderbook snapshots

Trade events provide executed price/quantity and maker/taker information used to construct aggressive buy/sell flow and Delta. Orderbook snapshots provide best bid/ask, spread, microprice and depth-imbalance features. The current-prices stream is preserved raw and includes Futures fields such as mark price and funding-rate fields.

## Data scope and deliberate exclusions

The first research stage is deliberately centered on **executed aggressive flow + contemporaneous orderbook state + subsequent price movement**. It does not try to synthesize every possible Futures market variable.

**Captured but not yet modeled:** funding-rate fields and mark price from the public current-prices stream. They are available in raw data but are not currently promoted into the feature set or P&L model. Funding should be evaluated before multi-hour/overnight conclusions; mark price is useful for additional Futures context and risk analysis.

**Not part of the verified public market-wide contract:** market-wide open interest, market-wide liquidation flow, and market-wide order submission/cancellation lifecycle. Account-level order/position/transaction interfaces must not be mistaken for a public market-wide event tape. These quantities are not silently synthesized into the core Delta series.

This distinction is intentional: absence from the modeled dataset does not mean a field is unknowable. A field is either captured and explicitly unused, or omitted because a verified public market-wide source has not been established.

## Research contract

The feature builder creates an explicit continuous wall-clock 1-second grid per Futures symbol. Missing seconds have zero new flow while the last observed Futures trade price is carried forward. Forward labels target exact future seconds rather than the next observed row.

At 1-second resolution it computes trade count, aggressive buy/sell quantity, Delta quantity, total quantity, Delta ratio, activity, and Futures orderbook features. It also writes 1-minute and 3-minute aggregates.

Delta windows: 5/15/30/60/180 seconds.

Forward horizons: 60/300/600/900/1800 seconds.

## Strategy research and reporting

For every symbol x Delta-window x forward-horizon combination, thresholds are learned only from the first 60% discovery segment using the 10th/90th percentiles of Delta ratio. The next 20% is validation and the final 20% is holdout. Positions are non-overlapping within each segment.

Default starting capital: INR 50,000.

Default exchange-fee assumption: 11.8 bps round trip.

The processor writes two complementary reports:

- `futures_hypotheses.json`: machine-readable full results, including every parameter combination.
- `futures_research_report.md`: concise human-readable report with coverage, best holdout results and interpretation guardrails.

The report is **holdout-first** and explicitly labels small-sample results as exploratory. A positive holdout result with very few trades is not treated as proof of a durable strategy.

Funding, spread, slippage and execution uncertainty are excluded from current P&L and must be evaluated before any live conclusion.

## Operational acceptance

A green code/test state is not by itself a production acceptance. A fresh batch must prove:

`correct commit -> Futures raw capture -> required streams -> exact artifact handoff -> exact artifact download/extraction -> six-symbol feature build -> valid 1s grid/depth -> strategy report -> compact 1m/3m commit/push -> storage report -> next collector cycle when chaining is enabled`

The first successful batch is an infrastructure/research acceptance test, not a profitability claim.
