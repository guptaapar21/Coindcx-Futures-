# CoinDCX Futures-only Research

This repository is intentionally independent of `coindcx-delta-research`.

## Objective

**Futures aggressive order flow (Delta) -> subsequent Futures price movement.**

The first research stage is designed to answer one clean question: whether executed aggressive Futures flow, together with contemporaneous orderbook state, contains predictive information about subsequent Futures price movement after the specified exchange-fee cost.

## Data contract

Only public CoinDCX Futures market-data streams are part of the production raw batch contract:

1. `futures_trades.jsonl.gz`
2. `futures_price_change.jsonl.gz`
3. `futures_current_prices.jsonl.gz`
4. `futures_depth_snapshot.jsonl.gz`

No Spot websocket is opened and no Spot raw files belong in a production batch.

Canonical symbols:

`B-BTC_USDT`, `B-ETH_USDT`, `B-SOL_USDT`, `B-SUI_USDT`, `B-XRP_USDT`, `B-DOGE_USDT`

The collector preserves raw exchange payloads together with local receive timestamps and exchange timestamps. The current-prices stream is captured raw and contains Futures fields including funding-rate fields and mark price.

## Collector operating model

Collection is operator-controlled through `.github/workflows/continuous-collector.yml`.

Manual `Run workflow` inputs:

- `duration_minutes`: 5-230 minutes; default 30.
- `continue_chain`: `false` for a single standalone batch; `true` to continue automatically after each successful raw batch.

When chaining is enabled, the selected duration is carried in the repository-dispatch payload to the next collector run. There is no collector cron and no GitHub supervisor/watchdog. External supervision is handled outside GitHub.

## Feature contract

The feature builder creates a continuous wall-clock 1-second grid independently for each Futures symbol.

For an empty second:

- new flow is zero;
- the last observed Futures trade price is carried forward;
- the row remains present in the grid.

Forward labels target exact future seconds rather than the next observed row.

At 1-second resolution the builder computes:

- trade count;
- aggressive buy quantity;
- aggressive sell quantity;
- Delta quantity;
- total quantity;
- Delta ratio;
- activity;
- best bid / best ask;
- spread in absolute and bps terms;
- microprice;
- 1/5/10/20-level book quantities and imbalance.

It also creates 1-minute and 3-minute aggregates.

Delta windows: **5, 15, 30, 60, 180 seconds**.

Forward horizons: **60, 300, 600, 900, 1800 seconds**.

## Strategy research contract

For every symbol x Delta-window x forward-horizon combination:

1. Observations are sorted by epoch second.
2. The first 60% is discovery.
3. The 10th and 90th Delta-ratio percentiles are learned only from discovery.
4. The next 20% is validation.
5. The final 20% is holdout.
6. Positions are non-overlapping within each segment.
7. Exchange cost is applied to each simulated round trip.
8. Headline ranking is based on holdout net P&L, with sample-size warnings shown separately.

Default starting capital: **INR 50,000**.

Default exchange-fee assumption: **11.8 bps round trip**.

## Reporting contract

Each processed batch writes:

- `futures_hypotheses.json` — machine-readable full result set for all parameter combinations, plus a clean top-level summary, coverage and warnings.
- `futures_research_report.md` — human-readable summary showing research status, data coverage, best holdout results, best result per symbol and interpretation guardrails.

A result is **not** considered a production strategy merely because it has positive holdout P&L. Small holdout trade counts are explicitly treated as descriptive only. The report is intended to prevent a single lucky trade or tiny sample from being mistaken for evidence of a durable edge.

## Data deliberately outside the modeled layer

### Captured but currently unused

**Funding-rate fields and mark price** are preserved in the raw current-prices stream but are not currently promoted into the modeled feature set or P&L. This keeps the first-stage experiment focused on aggressive flow, book state and subsequent price movement. Funding should be included before making multi-hour or overnight conclusions; mark price can be evaluated as additional Futures context/risk information.

### Not established as public market-wide event streams

**Market-wide open interest, market-wide liquidation flow, and market-wide order submission/cancellation lifecycle** are not currently part of the verified public market-wide raw contract. Account-level order/position/transaction interfaces are not equivalent to a market-wide public event tape. These measures are therefore not synthesized into the core Delta series.

The repository distinguishes these cases explicitly: a field is either captured and deliberately unused, or excluded because a verified public market-wide source has not been established.

## Cost and execution scope

Current P&L includes the specified exchange-fee cost only.

The following are excluded and must be evaluated before any live conclusion:

- funding;
- bid/ask spread crossing beyond the fee-only abstraction;
- slippage;
- execution latency and fill uncertainty;
- other live-market execution effects.

## Storage and state

Raw and processed artifacts use Futures-specific names and isolated Futures compact-history paths. The repository maintains protected batch state and emits a storage report during processing. Raw Actions artifact rotation is repository-local; GitHub's storage accounting remains repository-wide.

## Acceptance rule

A fresh production-accepted batch must demonstrate:

`correct commit -> Futures raw capture -> all required streams -> exact artifact handoff -> exact artifact download/extraction -> six-symbol 1s feature build -> valid depth -> strategy report -> isolated 1m/3m compact commit/push -> storage report -> next collector cycle when chaining is enabled`

A green test workflow is necessary but not sufficient. The first successful end-to-end batch is an infrastructure/research acceptance test, not a profitability claim.
