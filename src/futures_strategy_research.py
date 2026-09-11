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
    if len(d)<300:return {"symbol":s,"window_s":w,"horizon_s":h,"status":"insufficient_data"}
    n=len(d); de=int(n*.6); ve=int(n*.8); lo=pct([x[1] for x in d[:de]],.1); hi=pct([x[1] for x in d[:de]],.9)
    return {"symbol":s,"window_s":w,"horizon_s":h,"status":"ok","discovery_observations":de,"validation_observations":ve-de,"holdout_observations":n-ve,"threshold_low":lo,"threshold_high":hi,"validation":sim(d[de:ve],capital,lo,hi,h,cost_bps),"holdout":sim(d[ve:],capital,lo,hi,h,cost_bps),"funding_included":False}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--out",required=True); ap.add_argument("--capital",type=float,default=50000); ap.add_argument("--round-trip-bps",type=float,default=11.8); a=ap.parse_args(); rs=rows(Path(a.input))
    allr=[run(rs,s,w,h,a.capital,a.round_trip_bps) for s in SYMBOLS for w in WINDOWS for h in HORIZONS]; good=[x for x in allr if x["status"]=="ok"]; good.sort(key=lambda x:x["holdout"]["net_pnl_inr"],reverse=True)
    payload={"schema_version":3,"objective":"Futures Delta -> Futures price","starting_capital_inr":a.capital,"round_trip_cost_bps":a.round_trip_bps,"windows_s":list(WINDOWS),"horizons_s":list(HORIZONS),"method":"10th/90th thresholds learned on first 60%; separate 20% validation and 20% holdout; non-overlapping positions","funding_included":False,"funding_note":"Funding is excluded because it is not captured by the raw collector.","top_holdout_results":good[:25],"all_results":allr}; Path(a.out).write_text(json.dumps(payload,indent=2)); print(json.dumps({"rows":len(rs),"top":good[:5]},indent=2))
if __name__=="__main__":main()
