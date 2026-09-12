# CoinDCX Futures Research

Dedicated Futures-only microstructure and Delta research repository.

Objective: **Futures aggressive order flow (Delta) -> subsequent Futures price movement.**

This repository is intentionally separate from the Spot+Futures production repository so its Actions workflows, research history, and operational state are isolated at the repository boundary.

## Current pipeline

`continuous-collector.yml` -> raw Futures artifact -> exact-artifact processing -> Futures 1s/1m/3m features -> Futures Delta strategy research -> isolated compact research -> storage housekeeping.

The collector is intentionally operator-controlled. `Run workflow` accepts a batch duration from 5-230 minutes (default 30) and an explicit `continue_chain` toggle. With chaining off, exactly one batch is collected. With chaining on, each successful batch dispatches the next batch with the same duration.

There is no collector cron and no GitHub supervisor/watchdog. Monitoring/supervision is handled outside GitHub.

## Captured market data

The production raw batch contract captures four public Futures market-data streams for the six canonical symbols:

- Futures trades
- Futures price-change events
- Futures current-prices real-time events
- Futures 50-level orderbook snapshots

The trade feed provides executed price/quantity and maker/taker information used to construct aggressive buy/sell flow and Delta. The orderbook snapshots provide depth/imbalance/microprice/spread features. The current-prices feed is captured raw and contains Futures fields including mark price and funding-rate fields, but the present feature builder does not yet promote those fields into the research feature set.

## Deliberately outside the current research contract

Market-wide open interest, market-wide liquidation flow, and order submission/cancellation lifecycle are not part of the current public raw-data contract. CoinDCX documentation exposes authenticated account/position/order/transaction endpoints, but those are account-specific rather than a public market-wide event stream. They are therefore not silently synthesized into the core Delta dataset.

Funding and mark price are different: CoinDCX's public Futures current-prices feed exposes them, so they are **fetchable** and already present in the captured raw current-prices stream. They are simply not yet used as modeled features/P&L adjustments. Funding should be incorporated before conclusions on multi-hour/overnight holding; mark price is useful for additional Futures context and risk analysis.

The core objective does not require every available Futures field. The first-stage research is intentionally centered on executed aggressive flow, orderbook state, and subsequent price movement. Additional context should be added only when it improves the research question and can be measured without introducing look-ahead or synthetic market-wide data.

## Research contract

The feature builder creates a continuous wall-clock 1-second grid per Futures symbol. Missing seconds have zero new flow while the last observed Futures trade price is carried forward. Forward labels target exact future seconds rather than the next observed row.

Delta windows: 5/15/30/60/180 seconds. Forward horizons: 60/300/600/900/1800 seconds.

Thresholds are learned only from the first 60% discovery segment. The next 20% is validation and the final 20% is holdout. Positions are non-overlapping within each segment. Headline reporting is holdout-first.

## Cost model

Current strategy backtests use 11.8 bps round-trip exchange-fee cost (5 bps taker per side plus 18% GST on fees). Funding, spread, slippage and execution effects are not yet included in P&L and must be evaluated before any live conclusion.

## Operational acceptance

The first successful batch is an infrastructure/research acceptance test, not a profitability claim. A production-accepted batch must prove correct commit -> Futures raw capture -> exact artifact handoff/download/extraction -> six-symbol feature build -> valid depth -> strategy run -> isolated compact commit/push -> storage report -> next Futures collector cycle when chaining is enabled.
