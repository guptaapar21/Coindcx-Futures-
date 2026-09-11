#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

def read(path):
    if not path.exists(): return []
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def rewrite(rows,epoch_key,horizons=(60,180,300,600,900,1800)):
    by=defaultdict(dict)
    for r in rows:
        try:by[r["symbol"]][int(r[epoch_key])]=r
        except:pass
    for mp in by.values():
        for e,r in mp.items():
            try:p0=float(r.get("close"));
            except: p0=None
            for h in horizons:
                p1=None
                if e+h in mp:
                    try:p1=float(mp[e+h].get("close"))
                    except:p1=None
                r[f"forward_return_{h}s"]=(p1/p0-1) if p0 and p1 else ""
    return [r for mp in by.values() for r in mp.values()]
def merge(incoming,root,key):
    root.mkdir(parents=True,exist_ok=True); old=[]
    for p in root.glob("20??-??.csv"): 
        with p.open(encoding="utf-8",newline="") as f:old.extend(csv.DictReader(f))
    allr={(r["symbol"],r[key]):r for r in old}
    allr.update({(r["symbol"],r[key]):r for r in incoming}); rows=rewrite(list(allr.values()),key); months=defaultdict(list)
    for r in rows:months[datetime.fromtimestamp(int(r[key]),timezone.utc).strftime("%Y-%m")].append(r)
    for m,rs in months.items():
        path=root/f"{m}.csv"; fields=sorted({k for r in rs for k in r})
        with path.open("w",encoding="utf-8",newline="") as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(sorted(rs,key=lambda r:(r["symbol"],int(r[key]))))
    (root/"index.json").write_text(json.dumps({"schema_version":1,"epoch_key":key,"months":sorted(months),"forward_label_horizons_seconds":[60,180,300,600,900,1800]},indent=2))
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--batch",required=True);ap.add_argument("--dest-root",required=True);ap.add_argument("--dest-root-3m",required=True);a=ap.parse_args();b=Path(a.batch); mins=read(b/"features_1m.csv.gz"); threes=read(b/"features_3m.csv.gz"); merge(mins,Path(a.dest_root),"minute_epoch"); merge(threes,Path(a.dest_root_3m),"three_minute_epoch")
if __name__=="__main__":main()
