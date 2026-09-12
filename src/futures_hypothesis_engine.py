#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from statistics import median

SYMBOLS=("B-BTC_USDT","B-ETH_USDT","B-SOL_USDT","B-SUI_USDT","B-XRP_USDT","B-DOGE_USDT")
WINDOWS=(5,15,30,60,180); HORIZONS=(60,300,600,900,1800)
MIN_DISCOVERY_BATCHES=2; MIN_DISCOVERY_TRADES=8; MIN_POSITIVE_FRACTION=.60
SURVIVE_FORWARD_BATCHES=2; ROBUST_FORWARD_BATCHES=5; ROBUST_POSITIVE_FRACTION=.70


def stable_id(scope,symbol,w,h,direction):
    raw=f"delta_tail|{scope}|{symbol}|{w}|{h}|{direction}|p10p90"
    return "HYP-"+hashlib.sha1(raw.encode()).hexdigest()[:10].upper()


def n(x):
    try:return None if x in (None,"") else float(x)
    except (TypeError,ValueError):return None


def side_records(result,batch_id,cost_bps):
    s=result.get("symbol"); w=result.get("window_s"); h=result.get("horizon_s")
    if s not in SYMBOLS or w not in WINDOWS or h not in HORIZONS:return []
    groups={"LONG":[],"SHORT":[]}
    for t in (result.get("holdout") or {}).get("trade_log") or []:
        side=t.get("side"); ret=n(t.get("forward_return")); pnl=n(t.get("net_pnl_inr"))
        if side not in groups or ret is None or pnl is None:continue
        groups[side].append((ret,pnl))
    out=[]
    for side,trades in groups.items():
        if not trades:continue
        # The existing strategy uses a fixed round-trip cost on each trade.
        net_bps=[(1 if side=="LONG" else -1)*r*10000-cost_bps for r,_ in trades]
        out.append({"batch_id":batch_id,"scope":"SYMBOL","symbol":s,"window_s":int(w),"horizon_s":int(h),
                    "direction":side,"trades":len(trades),"wins":sum(1 for _,p in trades if p>0),
                    "net_pnl_inr":sum(p for _,p in trades),"net_return_bps_sum":sum(net_bps),
                    "mean_net_bps":sum(net_bps)/len(net_bps),"median_net_bps":median(net_bps)})
    return out


def pool_records(symbol_rows,batch_id):
    g={}
    for r in symbol_rows:
        k=(r["window_s"],r["horizon_s"],r["direction"]); g.setdefault(k,[]).append(r)
    out=[]
    for (w,h,d),rs in g.items():
        if len(rs)<2:continue
        means=[float(r["mean_net_bps"]) for r in rs]
        out.append({"batch_id":batch_id,"scope":"ALL_SYMBOLS","symbol":"ALL_SYMBOLS","window_s":w,"horizon_s":h,
                    "direction":d,"trades":sum(r["trades"] for r in rs),"wins":sum(r["wins"] for r in rs),
                    "net_pnl_inr":sum(r["net_pnl_inr"] for r in rs),"net_return_bps_sum":sum(r["net_return_bps_sum"] for r in rs),
                    "mean_net_bps":sum(means)/len(means),"median_net_bps":median(means),
                    "symbol_blocks":len(rs),"positive_symbol_blocks":sum(1 for x in means if x>0)})
    return out


def load_history(path):
    if not path.exists():return []
    by_batch={}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        if r.get("batch_id"):by_batch[str(r["batch_id"])]=r
    out=[]
    for bid in sorted(by_batch):out.extend(by_batch[bid].get("records",[]))
    return out


def aggregate(rows,key):
    return sorted([r for r in rows if (r["scope"],r["symbol"],r["window_s"],r["horizon_s"],r["direction"])==key],key=lambda r:str(r["batch_id"]))


def discovery_ok(recs):
    if len(recs)<MIN_DISCOVERY_BATCHES:return False
    trades=sum(int(r["trades"]) for r in recs)
    pos=sum(1 for r in recs if float(r["mean_net_bps"])>0)
    return trades>=MIN_DISCOVERY_TRADES and pos/len(recs)>=MIN_POSITIVE_FRACTION and median(float(r["mean_net_bps"]) for r in recs)>0


def build(rows):
    defs=[]
    for s in SYMBOLS:
        for w in WINDOWS:
            for h in HORIZONS:
                for d in ("LONG","SHORT"):defs.append(("SYMBOL",s,w,h,d))
    for w in WINDOWS:
        for h in HORIZONS:
            for d in ("LONG","SHORT"):defs.append(("ALL_SYMBOLS","ALL_SYMBOLS",w,h,d))
    batches=sorted({str(r["batch_id"]) for r in rows})
    result={}
    for key in defs:
        scope,s,w,h,d=key; hid=stable_id(scope,s,w,h,d); recs=aggregate(rows,key)
        first=None; forward=[]
        for bid in batches:
            prior=[r for r in recs if str(r["batch_id"])<bid]
            cur=[r for r in recs if str(r["batch_id"])==bid]
            if first is None and discovery_ok(prior):first=bid
            if first is not None and bid>=first and cur:forward.append(cur[0])
        retro={"batches":len(recs),"positive_batches":sum(1 for r in recs if float(r["mean_net_bps"])>0),
               "positive_batch_fraction":(sum(1 for r in recs if float(r["mean_net_bps"])>0)/len(recs) if recs else 0),
               "trades":sum(int(r["trades"]) for r in recs),"median_batch_mean_net_bps":(median(float(r["mean_net_bps"]) for r in recs) if recs else None),
               "net_pnl_inr":sum(float(r["net_pnl_inr"]) for r in recs),"eligible":discovery_ok(recs)}
        fp=[float(r["mean_net_bps"]) for r in forward]; pos=sum(1 for x in fp if x>0)
        fsum={"batches_tested":len(forward),"positive_batches":pos,"positive_batch_fraction":(pos/len(forward) if forward else 0),
              "trades":sum(int(r["trades"]) for r in forward),"net_pnl_inr":sum(float(r["net_pnl_inr"]) for r in forward),
              "median_batch_mean_net_bps":median(fp) if fp else None,"worst_batch_mean_net_bps":min(fp) if fp else None,
              "best_batch_mean_net_bps":max(fp) if fp else None}
        result[hid]={"hypothesis_id":hid,"scope":scope,"symbol":s,"delta_window_s":w,"horizon_s":h,"direction":d,
                     "first_forward_batch":first,"retrospective_evidence":retro,"forward_tests":forward,"forward_summary":fsum}
    # Parameter-neighbour support is deliberately simple and local.
    for h in result.values():
        support=0
        if h["scope"]=="SYMBOL":
            wi=WINDOWS.index(h["delta_window_s"]); hi=HORIZONS.index(h["horizon_s"])
            for dw in WINDOWS:
                for hh in HORIZONS:
                    if (abs(WINDOWS.index(dw)-wi)+abs(HORIZONS.index(hh)-hi))!=1:continue
                    nh=result[stable_id("SYMBOL",h["symbol"],dw,hh,h["direction"])]
                    if nh["retrospective_evidence"]["eligible"]:support+=1
        h["parameter_neighbor_support"]=support
        f=h["forward_summary"]; k=f["batches_tested"]; frac=f["positive_batch_fraction"]; med=f["median_batch_mean_net_bps"]
        h["status"]=("ROBUST" if k>=ROBUST_FORWARD_BATCHES and frac>=ROBUST_POSITIVE_FRACTION and med is not None and med>0 and support>=1 else
                      "SURVIVING" if k>=SURVIVE_FORWARD_BATCHES and frac>=MIN_POSITIVE_FRACTION and med is not None and med>0 else
                      "RETIRED" if k and (frac<.40 or pos==0 if False else False) else
                      "CANDIDATE" if k==0 else "WEAKENING")
        h["description"]=f"Extreme {'positive Delta -> SHORT' if d=='SHORT' else 'negative Delta -> LONG'} | {w}s -> {h}s | {s}"
    return result


def report_md(rep):
    p=["# Futures Hypothesis Engine Report","",f"**Status:** `{rep['engine_status']}`  ",f"**Current batch:** `{rep['current_batch_id']}`  ",
       f"**Batches observed:** **{rep['batch_count']}**  ",f"**Hypotheses evaluated:** **{rep['hypotheses_evaluated']}**","",
       "## Executive summary","",f"- Retrospective candidates: **{rep['retrospective_candidates']}**",f"- Current `SURVIVING` / `ROBUST`: **{rep['forward_survivors']}**",f"- Existing hypotheses forward-tested on current batch: **{rep['current_batch_forward_tests']}**","",
       "## Forward survivors","","| Rank | Hypothesis | Forward batches | Positive | Median net bp | Worst bp | Trades | Status |","|---:|---|---:|---:|---:|---:|---:|---|"]
    surv=sorted(rep["all_hypotheses"],key=lambda x:(x["status"] not in ("ROBUST","SURVIVING"),-x["forward_summary"]["positive_batch_fraction"],-(x["forward_summary"]["median_batch_mean_net_bps"] or -999),-x["forward_summary"]["trades"]))
    for i,h in enumerate([x for x in surv if x["status"] in ("ROBUST","SURVIVING")][:20],1):
        f=h["forward_summary"];p.append(f"| {i} | {h['description']} | {f['batches_tested']} | {f['positive_batch_fraction']*100:.0f}% | {(f['median_batch_mean_net_bps'] or 0):.3f} | {(f['worst_batch_mean_net_bps'] or 0):.3f} | {f['trades']} | **{h['status']}** |")
    if not any(x["status"] in ("ROBUST","SURVIVING") for x in rep["all_hypotheses"]):p.append("| — | No hypothesis has enough genuine forward evidence yet | — | — | — | — | — | CANDIDATE |")
    p += ["","## Current-batch forward tests","","| Hypothesis | First forward batch | Current net bp | Trades | Result |","|---|---|---:|---:|---|"]
    cur=[]
    for h in rep["all_hypotheses"]:
        for r in h["forward_tests"]:
            if str(r["batch_id"])==rep["current_batch_id"]:cur.append((h,r));break
    cur.sort(key=lambda x:float(x[1]["mean_net_bps"]),reverse=True)
    for h,r in cur[:20]:p.append(f"| {h['description']} | {h['first_forward_batch']} | {float(r['mean_net_bps']):.3f} | {r['trades']} | {'POSITIVE' if float(r['mean_net_bps'])>0 else 'NEGATIVE'} |")
    if not cur:p.append("| — | — | — | — | No prior candidate tested on this batch |")
    p += ["","## Combined-history candidates","","| Rank | Hypothesis | Historical batches | Positive | Median net bp | Trades |","|---:|---|---:|---:|---:|---:|"]
    retro=sorted(rep["all_hypotheses"],key=lambda x:(not x["retrospective_evidence"]["eligible"],-x["retrospective_evidence"]["positive_batch_fraction"],-(x["retrospective_evidence"]["median_batch_mean_net_bps"] or -999)))
    for i,h in enumerate([x for x in retro if x["retrospective_evidence"]["eligible"]][:20],1):
        e=h["retrospective_evidence"];p.append(f"| {i} | {h['description']} | {e['batches']} | {e['positive_batch_fraction']*100:.0f}% | {(e['median_batch_mean_net_bps'] or 0):.3f} | {e['trades']} |")
    p += ["","## Batch evidence for leading hypotheses",""]
    for h in [x for x in surv if x["retrospective_evidence"]["eligible"]][:10]:
        p += [f"### {h['hypothesis_id']} — {h['description']}","","| Batch | Net bp | Trades |","|---|---:|---:|"]
        seen=set()
        for r in h["forward_tests"]:
            seen.add(r["batch_id"]);p.append(f"| {r['batch_id']} | {float(r['mean_net_bps']):.3f} | {r['trades']} |")
        if not seen:p.append("| No forward tests | — | — |")
        p.append("")
    p += ["## Guardrails","","- Discovery for a forward batch uses only strictly earlier batches.","- A newly discoverable hypothesis is not credited with the batch that made it discoverable.","- Delta-tail definitions use the same 10th/90th percentile contract as the existing batch research.","- Current modeled cost is 11.8 bps round trip; spread, slippage, funding and execution uncertainty remain excluded.","- No live-trading promotion is performed by this engine."]
    return "\n".join(p)+"\n"


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--input",required=True);ap.add_argument("--batch-id",required=True);ap.add_argument("--history",default="data/research/futures_hypothesis_engine/batch_results.jsonl");ap.add_argument("--registry",default="data/research/futures_hypothesis_engine/hypothesis_registry.json");ap.add_argument("--out-dir");ap.add_argument("--round-trip-bps",type=float,default=11.8);a=ap.parse_args()
    payload=json.loads(Path(a.input).read_text(encoding="utf-8")); allr=payload.get("all_results") or []
    sym=[]
    for r in allr:sym.extend(side_records(r,a.batch_id,a.round_trip_bps))
    cur=sym+pool_records(sym,a.batch_id); hp=Path(a.history); previous=load_history(hp)
    rows=[r for r in previous if str(r.get("batch_id"))!=a.batch_id]+cur; rows.sort(key=lambda r:(str(r["batch_id"]),r["scope"],r["symbol"],r["window_s"],r["horizon_s"],r["direction"]))
    data=build(rows); survivors=sum(1 for h in data.values() if h["status"] in ("SURVIVING","ROBUST")); candidates=sum(1 for h in data.values() if h["retrospective_evidence"]["eligible"])
    current_tests=sum(1 for h in data.values() if any(str(r["batch_id"])==a.batch_id for r in h["forward_tests"]))
    rep={"schema_version":1,"engine":"FUTURES_HYPOTHESIS_ENGINE","engine_status":"EXPLORATORY__NO_AUTO_LIVE_PROMOTION","current_batch_id":a.batch_id,"batch_count":len({r["batch_id"] for r in rows}),"batches_observed":sorted({str(r["batch_id"]) for r in rows}),"hypotheses_evaluated":len(data),"retrospective_candidates":candidates,"forward_survivors":survivors,"current_batch_forward_tests":current_tests,"all_hypotheses":list(data.values())}
    hp.parent.mkdir(parents=True,exist_ok=True)
    records_by_batch={}
    for r in rows:records_by_batch.setdefault(str(r["batch_id"]),[]).append(r)
    hp.write_text("\n".join(json.dumps({"batch_id":b,"records":records_by_batch[b]},sort_keys=True) for b in sorted(records_by_batch))+"\n",encoding="utf-8")
    rp=Path(a.registry);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps({"schema_version":1,"updated_at_utc":datetime.now(timezone.utc).isoformat(),"hypotheses":data},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    out=Path(a.out_dir) if a.out_dir else Path(a.input).parent;out.mkdir(parents=True,exist_ok=True);(out/"futures_hypothesis_engine_report.md").write_text(report_md(rep),encoding="utf-8");(out/"futures_hypothesis_engine_summary.json").write_text(json.dumps(rep,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:rep[k] for k in ("engine","current_batch_id","batch_count","hypotheses_evaluated","retrospective_candidates","forward_survivors","current_batch_forward_tests")},indent=2))

if __name__=="__main__":main()
