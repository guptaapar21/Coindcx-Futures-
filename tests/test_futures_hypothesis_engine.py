import json
from pathlib import Path
from src import futures_hypothesis_engine as he


def make_result(symbol, value, batch):
    # 8 profitable trades per side so discovery gates are satisfied.
    trades=[]
    for i in range(8):
        trades.append({"side":"LONG","forward_return":value/10000,"net_pnl_inr":500.0,"gross_pnl_inr":559.0,"cost_inr":59.0})
        trades.append({"side":"SHORT","forward_return":-value/10000,"net_pnl_inr":500.0,"gross_pnl_inr":559.0,"cost_inr":59.0})
    return {"symbol":symbol,"window_s":30,"horizon_s":600,"status":"ok","holdout":{"trade_log":trades}}


def test_walk_forward_uses_only_prior_batches():
    rows=[]
    for bid,val in [("B1",20),("B2",25),("B3",30)]:
        rows.extend(he.side_records(make_result("B-BTC_USDT",val,bid),bid,11.8))
    rows.sort(key=lambda r:r["batch_id"])
    data=he.build(rows)
    hid=he.stable_id("SYMBOL","B-BTC_USDT",30,600,"LONG")
    h=data[hid]
    assert h["first_forward_batch"] == "B3"
    assert [r["batch_id"] for r in h["forward_tests"]] == ["B3"]
    assert h["retrospective_evidence"]["eligible"] is True


def test_pooling_creates_all_symbol_record():
    bid="B1"
    sym=[]
    for s in ("B-BTC_USDT","B-ETH_USDT"):
        sym.extend(he.side_records(make_result(s,20,bid),bid,11.8))
    pooled=he.pool_records(sym,bid)
    assert pooled
    assert any(r["scope"]=="ALL_SYMBOLS" and r["window_s"]==30 and r["horizon_s"]==600 for r in pooled)


def test_description_uses_numeric_window_and_horizon_values():
    rows=[]
    for bid,val in [("B1",20),("B2",25),("B3",30)]:
        rows.extend(he.side_records(make_result("B-BTC_USDT",val,bid),bid,11.8))
    data=he.build(rows)
    hid=he.stable_id("SYMBOL","B-BTC_USDT",30,600,"LONG")
    assert data[hid]["description"] == "Extreme negative Delta -> LONG | 30s -> 600s | B-BTC_USDT"


def test_retires_when_forward_positive_fraction_falls_below_40_percent():
    rows=[]
    for bid,val in [("B1",20),("B2",25),("B3",-20),("B4",-20),("B5",-20)]:
        rows.extend(he.side_records(make_result("B-BTC_USDT",val,bid),bid,11.8))
    data=he.build(rows)
    hid=he.stable_id("SYMBOL","B-BTC_USDT",30,600,"LONG")
    h=data[hid]
    assert h["first_forward_batch"] == "B3"
    assert [r["batch_id"] for r in h["forward_tests"]] == ["B3","B4","B5"]
    assert h["forward_summary"]["positive_batch_fraction"] == 0
    assert h["status"] == "RETIRED"
