# CoinDCX Futures Research

Dedicated Futures-only microstructure and Delta research repository.

Objective: **Futures aggressive order flow (Delta) -> subsequent Futures price movement.**

This repository is intentionally separate from the Spot+Futures production repository so its Actions workflows, research history, and operational state are isolated at the repository boundary.

## Pipeline

`continuous-collector.yml` -> raw Futures artifact -> exact-artifact processing -> Futures 1s/1m/3m features -> Futures Delta strategy research -> isolated compact research -> storage housekeeping.

The first successful batch is an infrastructure/research acceptance test, not a profitability claim.

## Cost model

Current strategy backtests use 11.8 bps round-trip exchange-fee cost (5 bps taker per side plus 18% GST on fees). Funding, spread, slippage and execution effects are not yet included in P&L and must be evaluated before any live conclusion.
