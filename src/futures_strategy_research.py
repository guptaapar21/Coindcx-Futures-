#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json,math
from pathlib import Path
from statistics import mean
SYMBOLS=("B-BTC_USDT","B-ETH_USDT","B-SOL_USDT","B-SUI_USDT","B-XRP_USDT","B-DOGE_USDT"); WINDOWS=(5,15,30,60,180); HORIZONS=(60,300,600,900,1800)

def rows(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def num(r,k):
    try:x=r.get(k); return float(x) if x not in (None,"") else None
    except:return None

def pct(v,q):
    a=sorted(v); pos=q*(len(a)-1); lo=int(math.floor(pos)); hi=int(math.ceil(pos)); return a[lo] if lo==hi else a[lo]+(a[hi]-a[lo])*(pos-lo)

def sim(data,capital,lo,hi,h,cost_bps):
    cash=capital; free=-10**18; trades=[]
    for t,sig,ret in data:
        if t<free:continue
        side=1 if sig>=hi else -1 if sig<=lo else 0
        if not side:continue
        gross=cash*side*ret; cost=cash*cost_bps/10000; net=gross-cost; cash+=net
        trades.append({"epoch_second":t,"side":"LONG" if side>0 else "SHORT","signal":sig,"forward_return":ret,"gross_pnl_inr":gross,"cost_inr":cost,"net_pnl_inr":net,"capital_after_inr":cash})
        free=t+h
    wins=sum(x["net_pnl_inr"]>0 for x in trades)
    return {"trades":len(trades),"wins":wins,"losses":len(trades)-wins,"win_rate":wins/len(trades) if trades else None,"gross_pnl_inr":sum(x["gross_pnl_inr"] for x in trades),"round_trip_cost_inr":sum(x["cost_inr"] for x in trades),"net_pnl_inr":sum(x["net_pnl_inr"] for x in trades),"ending_capital_inr":cash,"return_pct":(cash/capital-1)*100,"average_net_trade_inr":mean(x["net_pnl_inr"] for x in trades) if trades else None,"trade_log":trades}

def run(rs,s,w,h,capital,cost_bps):
    d=[]
    for r in rs:
        if r.get("symbol")!=s:continue
        try:t=int(r["epoch_second"])
        except:continue
        sig=num(r,f"futures_delta_ratio_{w}s"); ret=num(r,f"futures_price_return_{h}s")
        if sig is not None and ret is not None:d.append((t,sig,ret))
    d.sort()
    if len(d)<300:return {"symbol":s,"window_s":w,"horizon_s":h,"status":"insufficient_data","observations":len(d)}
    n=len(d); de=int(n*.6); ve=int(n*.8); lo=pct([x[1] for x in d[:de]],.1); hi=pct([x[1] for x in d[:de]],.9)
    return {"symbol":s,"window_s":w,"horizon_s":h,"status":"ok","observations":n,"discovery_observations":de,"validation_observations":ve-de,"holdout_observations":n-ve,"threshold_low":lo,"threshold_high":hi,"validation":sim(d[de:ve],capital,lo,hi,h,cost_bps),"holdout":sim(d[ve:],capital,lo,hi,h,cost_bps),"funding_included":False}

def result_key(r):
    h=r.get("holdout",{}); return (float(h.get("net_pnl_inr") or -10**18), float(h.get("return_pct") or -10**18))

def clean_result(r):
    h=r.get("holdout",{}); v=r.get("validation",{})
    return {"symbol":r["symbol"],"delta_window_s":r["window_s"],"horizon_s":r["horizon_s"],"observations":r.get("observations"),"holdout_trades":h.get("trades"),"holdout_win_rate":h.get("win_rate"),"holdout_gross_pnl_inr":h.get("gross_pnl_inr"),"holdout_cost_inr":h.get("round_trip_cost_inr"),"holdout_net_pnl_inr":h.get("net_pnl_inr"),"holdout_return_pct":h.get("return_pct"),"validation_trades":v.get("trades"),"validation_net_pnl_inr":v.get("net_pnl_inr")}

def build_report(rs,allr,capital,cost_bps):
    good=[x for x in allr if x["status"]=="ok"]
    good.sort(key=result_key,reverse=True)
    best_by_symbol={}
    for s in SYMBOLS:
        candidates=[x for x in good if x["symbol"]==s]
        if candidates:best_by_symbol[s]=clean_result(candidates[0])
    total_holdout_trades=sum(int(x.get("holdout",{}).get("trades",0)) for x in good)
    positive=sum(1 for x in good if (x.get("holdout",{}).get("net_pnl_inr") or 0)>0)
    max_obs=max((x.get("observations",0) for x in allr),default=0)
    min_obs=min((x.get("observations",0) for x in allr),default=0)
    warnings=[]
    if total_holdout_trades<20:warnings.append("Holdout trade count is very small; no profitability conclusion is justified.")
    if positive and positive<len(good):warnings.append("Some parameter combinations are positive on holdout, but this does not establish a durable edge across combinations or time.")
    warnings.append("Funding, spread, slippage and execution uncertainty are excluded from P&L.")
    warnings.append("Funding and mark price are captured in raw current-prices events but are not modeled in this report.")
    return {
        "report_schema_version":1,
        "report_type":"FUTURES_DELTA_RESEARCH",
        "objective":"Test whether executed aggressive Futures order flow (Delta) is associated with subsequent Futures price movement.",
        "research_status":"EXPLORATORY__NOT_PRODUCTION_STRATEGY",
        "starting_capital_inr":capital,
        "round_trip_cost_bps":cost_bps,
        "parameter_space":{"symbols":list(SYMBOLS),"delta_windows_s":list(WINDOWS),"forward_horizons_s":list(HORIZONS),"total_combinations":len(allr)},
        "sample_coverage":{"feature_rows":len(rs),"valid_combinations":len(good),"insufficient_combinations":len(allr)-len(good),"min_observations_per_combination":min_obs,"max_observations_per_combination":max_obs,"holdout_trades_across_valid_combinations":total_holdout_trades},
        "method":"Thresholds are learned from the first 60% discovery segment using the 10th/90th percentiles of Delta ratio; the next 20% is validation; the final 20% is holdout; positions are non-overlapping within each segment.",
        "headline_rule":"Holdout-first. Results with very small holdout trade counts are descriptive only.",
        "cost_and_scope":{"exchange_fee_cost_included":True,"funding_included":False,"spread_included":False,"slippage_included":False,"execution_uncertainty_included":False},
        "warnings":warnings,
        "best_holdout_results":[clean_result(x) for x in good[:15]],
        "best_by_symbol":best_by_symbol
    }

def render_markdown(report):
    p=[];p.append("# Futures Delta Research Report");p.append("")
    p.append(f"**Status:** `{report['research_status']}`  ")
    p.append(f"**Objective:** {report['objective']}");p.append("")
    sc=report["sample_coverage"]; p.append("## Coverage");p.append(f"- Feature rows: **{sc['feature_rows']:,}**");p.append(f"- Valid parameter combinations: **{sc['valid_combinations']} / {report['parameter_space']['total_combinations']}**");p.append(f"- Holdout trades across valid combinations: **{sc['holdout_trades_across_valid_combinations']}**");p.append("")
    p.append("## Method");p.append(report["method"]);p.append("")
    p.append("## Best holdout results");p.append("");p.append("| Rank | Symbol | Delta window | Horizon | Holdout trades | Win rate | Net P&L (₹) | Return |");p.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    for i,r in enumerate(report["best_holdout_results"],1):
        wr="—" if r["holdout_win_rate"] is None else f"{r['holdout_win_rate']*100:.1f}%"; ret="—" if r["holdout_return_pct"] is None else f"{r['holdout_return_pct']:.4f}%"; pnl="—" if r["holdout_net_pnl_inr"] is None else f"₹{r['holdout_net_pnl_inr']:.2f}"; p.append(f"| {i} | {r['symbol']} | {r['delta_window_s']}s | {r['horizon_s']}s | {r['holdout_trades']} | {wr} | {pnl} | {ret} |")
    p.append("");p.append("## Best by symbol");p.append("");p.append("| Symbol | Delta window | Horizon | Holdout trades | Holdout net P&L | Holdout return |");p.append("|---|---:|---:|---:|---:|---:|")
    for s in SYMBOLS:
        r=report["best_by_symbol"].get(s)
        if not r:p.append(f"| {s} | — | — | — | — | — |")
        else:p.append(f"| {s} | {r['delta_window_s']}s | {r['horizon_s']}s | {r['holdout_trades']} | ₹{r['holdout_net_pnl_inr']:.2f} | {r['holdout_return_pct']:.4f}% |")
    p.append("");p.append("## Interpretation guardrails");
    for w in report["warnings"]:p.append(f"- {w}")
    p.append("");p.append("## Data scope");p.append("Funding and mark price are captured in raw Futures current-prices events but are not modeled here. Market-wide open interest, liquidation flow, and public order lifecycle are not synthesized. See `README.md` and `FUTURES_ONLY.md` for the maintained data contract.")
    return "\n".join(p)+"\n"

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--out",required=True); ap.add_argument("--capital",type=float,default=50000); ap.add_argument("--round-trip-bps",type=float,default=11.8); a=ap.parse_args(); rs=rows(Path(a.input))
    allr=[run(rs,s,w,h,a.capital,a.round_trip_bps) for s in SYMBOLS for w in WINDOWS for h in HORIZONS]
    report=build_report(rs,allr,a.capital,a.round_trip_bps)
    Path(a.out).write_text(json.dumps({**report,"all_results":allr},indent=2))
    md=Path(a.out).with_name("futures_research_report.md"); md.write_text(render_markdown(report))
    print(json.dumps({"rows":len(rs),"valid_combinations":report["sample_coverage"]["valid_combinations"],"holdout_trades":report["sample_coverage"]["holdout_trades_across_valid_combinations"],"report":str(md)},indent=2))

if __name__=="__main__":main()
