#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
WINDOWS=(5,15,30,60,180); HORIZONS=(60,300,600,900,1800); SYMBOLS=("B-BTC_USDT","B-ETH_USDT","B-SOL_USDT","B-SUI_USDT","B-XRP_USDT","B-DOGE_USDT")
def read(path):
    if not path.exists(): return
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f:
            try:
                x=json.loads(line); yield x if isinstance(x,dict) else {}
            except json.JSONDecodeError: continue
def data(x):
    r=x.get("raw",x); d=r.get("data") if isinstance(r,dict) else None
    if isinstance(d,dict): return r,d
    if isinstance(d,str):
        try:y=json.loads(d); return r,y if isinstance(y,dict) else r
        except Exception: pass
    return r,r if isinstance(r,dict) else {}
def canon(x):
    s=str(x or "").upper(); m={"BTCUSDT":"B-BTC_USDT","B-BTCUSDT":"B-BTC_USDT","ETHUSDT":"B-ETH_USDT","B-ETHUSDT":"B-ETH_USDT","SOLUSDT":"B-SOL_USDT","B-SOLUSDT":"B-SOL_USDT","SUIUSDT":"B-SUI_USDT","B-SUIUSDT":"B-SUI_USDT","XRPUSDT":"B-XRP_USDT","B-XRPUSDT":"B-XRP_USDT","DOGEUSDT":"B-DOGE_USDT","B-DOGEUSDT":"B-DOGE_USDT"}; return m.get(s,s or None)
def ts(r,d):
    try:return int(d.get("T",d.get("ts",r.get("exchange_timestamp_ms",r.get("received_at_ms")))) )//1000
    except Exception:return None
def f(x):
    try:return float(x)
    except Exception:return None
def rolling(vals,epochs,w):
    out=[0.0]*len(vals); pref=[0.0]
    for x in vals: pref.append(pref[-1]+x)
    l=0
    for i,t in enumerate(epochs):
        while l<=i and epochs[l]<t-w+1:l+=1
        out[i]=pref[i+1]-pref[l]
    return out
def book(d):
    def side(k,rev):
        x=d.get(k); a=[]
        if isinstance(x,dict):
            for p,q in x.items():
                pp,qq=f(p),f(q)
                if pp is not None and qq is not None and qq>0:a.append((pp,qq))
        return sorted(a,reverse=rev)
    bids,asks=side("bids",True),side("asks",False); out={"futures_book_valid":False,"futures_book_features_status":"FUTURES_DEPTH_SNAPSHOT"}
    for n in (1,5,10,20):out.update({f"futures_book_bid_qty_{n}":None,f"futures_book_ask_qty_{n}":None,f"futures_book_imbalance_{n}":None})
    if not bids or not asks:return out
    bb,bq=bids[0]; ba,aq=asks[0]; mid=(bb+ba)/2; out.update({"futures_book_valid":True,"futures_best_bid":bb,"futures_best_ask":ba,"futures_mid_price":mid,"futures_spread_abs":ba-bb,"futures_spread_bps":(ba-bb)/mid*10000 if mid else None,"futures_microprice":(ba*bq+bb*aq)/(bq+aq) if bq+aq else mid})
    for n in (1,5,10,20):
        b=sum(q for _,q in bids[:n]); a=sum(q for _,q in asks[:n]); out[f"futures_book_bid_qty_{n}"]=b; out[f"futures_book_ask_qty_{n}"]=a; out[f"futures_book_imbalance_{n}"]=(b-a)/(b+a) if b+a else None
    return out
def build_rows(batch):
    trades=defaultdict(dict); books=defaultdict(dict)
    for z in read(batch/"futures_trades.jsonl.gz"):
        r,d=data(z); s=canon(d.get("s") or r.get("pair")); t=ts(r,d); p,q=f(d.get("p")),f(d.get("q"))
        if s not in SYMBOLS or t is None or p is None or q is None: continue
        b=trades[s].setdefault(t,{"count":0,"buy":0.0,"sell":0.0,"total":0.0,"last":None}); b["count"]+=1; b["total"]+=q; b["last"]=p
        if d.get("m"): b["sell"]+=q
        else: b["buy"]+=q
    for z in read(batch/"futures_depth_snapshot.jsonl.gz"):
        r,d=data(z); s=canon(d.get("s") or r.get("pair")); t=ts(r,d)
        if s in SYMBOLS and t is not None: books[s][t]=book(d)
    rows=[]
    for s in SYMBOLS:
        event_epochs=sorted(set(trades[s])|set(books[s]));
        if not event_epochs: continue
        start,end=min(event_epochs),max(event_epochs); epochs=list(range(start,end+1)); price=None; base={}
        for t in epochs:
            b=trades[s].get(t,{})
            if b.get("last") is not None:price=float(b["last"])
            base[t]={"symbol":s,"epoch_second":t,"utc_second":datetime.fromtimestamp(t,timezone.utc).isoformat(),"open":price,"high":price,"low":price,"close":price,"futures_trade_count":int(b.get("count",0)),"futures_aggressive_buy_qty":float(b.get("buy",0)),"futures_aggressive_sell_qty":float(b.get("sell",0)),"futures_delta_qty":float(b.get("buy",0))-float(b.get("sell",0)),"futures_total_qty":float(b.get("total",0)),"futures_last_trade_price":price,"futures_book_features_status":"FUTURES_DEPTH_SNAPSHOT"}; base[t].update(books[s].get(t,{}))
        for t,r in base.items():
            for h in HORIZONS:
                p1=base.get(t+h,{}).get("close"); r[f"futures_price_return_{h}s"]=(p1/r["close"]-1) if p1 is not None and r.get("close") else None
        for w in WINDOWS:
            buy=rolling([base[t]["futures_aggressive_buy_qty"] for t in epochs],epochs,w); sell=rolling([base[t]["futures_aggressive_sell_qty"] for t in epochs],epochs,w); total=rolling([base[t]["futures_total_qty"] for t in epochs],epochs,w); cnt=rolling([base[t]["futures_trade_count"] for t in epochs],epochs,w)
            for i,t in enumerate(epochs):
                r=base[t]; r[f"futures_buy_qty_{w}s"]=buy[i]; r[f"futures_sell_qty_{w}s"]=sell[i]; r[f"futures_delta_qty_{w}s"]=buy[i]-sell[i]; r[f"futures_delta_ratio_{w}s"]=(buy[i]-sell[i])/total[i] if total[i] else None; r[f"futures_activity_{w}s"]=cnt[i]
        rows.extend(base[t] for t in epochs)
    return rows
def aggregate(rows,bucket):
    if not rows:return []
    inkey="epoch_second" if "epoch_second" in rows[0] else "minute_epoch" if "minute_epoch" in rows[0] else "epoch"
    g=defaultdict(list)
    for r in rows:
        e=int(r[inkey]); g[(r["symbol"],e-e%bucket)].append(r)
    out=[]
    for (s,b),rs in sorted(g.items()):
        close=[r for r in rs if r.get("close") is not None]
        if not close:continue
        row={"symbol":s,"epoch":b,"utc":datetime.fromtimestamp(b,timezone.utc).isoformat(),"open":close[0]["open"],"high":max(r["high"] for r in close),"low":min(r["low"] for r in close),"close":close[-1]["close"],"trade_count":sum(int(r["futures_trade_count"]) for r in rs),"futures_delta_qty":sum(float(r["futures_delta_qty"]) for r in rs),"futures_total_qty":sum(float(r["futures_total_qty"]) for r in rs),"futures_book_valid_seconds":sum(bool(r.get("futures_book_valid")) for r in rs)}; row["futures_delta_ratio"]=row["futures_delta_qty"]/row["futures_total_qty"] if row["futures_total_qty"] else None
        for k in ("futures_book_imbalance_1","futures_book_imbalance_5","futures_book_imbalance_10","futures_book_imbalance_20","futures_spread_bps","futures_microprice"):
            v=[float(r[k]) for r in rs if r.get(k) is not None]; row[k+"_mean"]=sum(v)/len(v) if v else None
        out.append(row)
    return out
def write(rows,path):
    path.parent.mkdir(parents=True,exist_ok=True); fields=sorted({k for r in rows for k in r}) if rows else ["symbol"]
    with gzip.open(path,"wt",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--batch",required=True);a=ap.parse_args();b=Path(a.batch);rows=build_rows(b);mins=aggregate(rows,60);threes=aggregate(mins,180)
    for r in mins:r["minute_epoch"]=r.pop("epoch");r["minute_utc"]=r.pop("utc")
    for r in threes:r["three_minute_epoch"]=r.pop("epoch");r["three_minute_utc"]=r.pop("utc")
    write(rows,b/"features_1s.csv.gz");write(mins,b/"features_1m.csv.gz");write(threes,b/"features_3m.csv.gz");
    (b/"research_summary.json").write_text(json.dumps({"schema_version":4,"market_mode":"FUTURES_ONLY","rows_1s":len(rows),"rows_1m":len(mins),"rows_3m":len(threes),"symbols":sorted({r["symbol"] for r in rows}),"windows_seconds":list(WINDOWS),"forward_horizons_seconds":list(HORIZONS),"time_grid":"continuous_1_second_wall_clock_per_symbol"},indent=2));print(json.dumps({"rows_1s":len(rows),"rows_1m":len(mins),"rows_3m":len(threes)}))
if __name__=="__main__":main()
