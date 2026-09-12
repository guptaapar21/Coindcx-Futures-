# CoinDCX Futures-only Research

This repository is intentionally independent of `coindcx-delta-research`.

## Objective
**Futures aggressive order flow (Delta) -> subsequent Futures price movement.**

## Data contract
Only public CoinDCX Futures streams are captured: trades, price changes, current prices, and per-instrument orderbook snapshots. No Spot websocket is opened and no Spot raw files are part of this repository's production batch contract.

## Collector operating model
Collection is operator-controlled through `.github/workflows/futures-manual-collector.yml`. A manual `Run workflow` supplies:
- `duration_minutes`: 5-230 minutes, default 30.
- `continue_chain`: false for one standalone batch; true to automatically start the next batch after each successful batch.

A chained run carries the selected duration forward to every subsequent batch. There is no collector cron and no GitHub supervisor/watchdog. External supervision is handled at the ChatGPT scheduler level.

## Research contract
The feature builder creates an explicit continuous wall-clock 1-second grid per Futures symbol. Missing seconds have zero new flow while the last observed Futures trade price is carried forward. Forward labels target exact future seconds rather than the next observed row.

Delta windows: 5/15/30/60/180 seconds. Forward horizons: 60/300/600/900/1800 seconds.

## Backtest
Thresholds are learned only from the first 60% discovery segment. The next 20% is validation and the final 20% is holdout. Positions are non-overlapping within each segment. Headline reporting is holdout-first.

Default starting capital: INR 50,000. Default exchange-cost assumption: 11.8 bps round trip. Funding, spread, slippage and execution uncertainty remain outside the current P&L and must be added before any live conclusion.

## Storage
This repository uses Futures-prefixed Actions artifacts and its own Futures compact research paths. Raw artifact rotation is repository-local; repository-wide Actions usage is still visible to housekeeping because GitHub storage accounting is not branch-local.

## Acceptance rule
A green code/test state is not a production acceptance. A fresh batch must prove: correct commit -> Futures raw capture -> exact artifact handoff/download/extraction -> six-symbol feature build -> valid depth -> strategy run -> isolated compact commit/push -> storage report -> next Futures collector cycle when chaining is enabled.
