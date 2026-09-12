# CoinDCX Futures Research

Dedicated Futures-only microstructure and Delta research repository.

## Objective

**Futures aggressive order flow (Delta) -> subsequent Futures price movement.**

This repository is intentionally separate from the Spot+Futures production repository. Its Actions workflows, research history, compact data and operational state are isolated at the repository boundary.

## Current pipeline

`continuous-collector.yml` -> raw Futures artifact -> exact-artifact processing -> Futures 1s/1m/3m features -> Futures Delta strategy research -> **Futures Hypothesis Engine** -> isolated compact/hypothesis history -> storage lifecycle/report.

The collector is operator-controlled. `Run workflow` accepts:

- `duration_minutes`: 5-230 minutes; default **120 minutes (2 hours)**.
- `continue_chain`: `false` for one standalone batch; `true` to automatically start the next batch after each successful raw batch.

When chaining is enabled with the default duration, the system continuously runs **2-hour Futures collection batches**. A completed raw batch is handed to processing immediately, while the next 2-hour collection starts independently. A chained run carries the selected duration forward. There is no collector cron and no GitHub supervisor/watchdog. External supervision is handled outside GitHub.

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

The processor writes:

- `futures_hypotheses.json`: machine-readable full batch results, including every parameter combination.
- `futures_research_report.md`: concise human-readable batch report.
- `futures_hypothesis_engine_report.md`: cross-batch hypothesis summary designed as the primary human-readable artifact.
- `futures_hypothesis_engine_summary.json`: machine-readable cross-batch engine output.

Funding, spread, slippage and execution uncertainty are excluded from current P&L and must be evaluated before any live conclusion.

## Futures Hypothesis Engine

The hypothesis engine is an additive layer; it does not replace the collector, feature builder or existing batch strategy research.

After every processed batch it persists compact side-specific holdout evidence in `data/research/futures_hypothesis_engine/batch_results.jsonl` and a persistent hypothesis registry in `data/research/futures_hypothesis_engine/hypothesis_registry.json`.

The engine evaluates normalized Delta-tail hypothesis families for each symbol and for an all-symbol pooled view. For each candidate it reconstructs a walk-forward history: discovery can use only batches strictly earlier than the first forward-test batch; the first eligible future batch becomes a genuine forward test; later batches remain forward evidence. New candidates discovered from the newest combined history are not credited with that same batch as forward evidence.

The engine records positive-batch fraction, trade count, median/worst/best batch net basis points, forward P&L, parameter-neighbour support and lifecycle status. Statuses are research labels only: `CANDIDATE`, `SURVIVING`, `ROBUST`, `WEAKENING`, and `RETIRED`.

The engine never auto-promotes a hypothesis to live trading. The 11.8 bps round-trip exchange-fee model is retained; spread, slippage, funding and execution uncertainty remain outside the current engine scope.

## Operational acceptance

A green code/test state is not by itself a production acceptance. A fresh batch must prove:

`correct commit -> Futures raw capture -> required streams -> exact artifact handoff -> exact artifact download/extraction -> six-symbol feature build -> valid 1s grid/depth -> strategy report -> hypothesis engine -> hypothesis history commit -> compact 1m/3m commit/push -> storage report -> next 120-minute collector cycle when chaining is enabled`

The first successful batch is an infrastructure/research acceptance test, not a profitability claim.
