#!/usr/bin/env python3
from __future__ import annotations

import argparse, gzip, importlib.metadata, json, signal, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import socketio

FILES={"new-trade":"futures_trades.jsonl.gz","price-change":"futures_price_change.jsonl.gz","current-prices":"futures_current_prices.jsonl.gz","depth-snapshot":"futures_depth_snapshot.jsonl.gz"}

def iso_now(): return datetime.now(timezone.utc).isoformat()

def load_config(p=Path(__file__).resolve().parents[1]/"config.json"): return json.loads(p.read_text(encoding="utf-8"))

class Writer:
    def __init__(self,p): self.p=p; p.parent.mkdir(parents=True,exist_ok=True); self.fh=gzip.open(p,"at",encoding="utf-8"); self.n=0
    def write(self,x): self.fh.write(json.dumps(x,separators=(",",":"),ensure_ascii=False)+"\n"); self.n+=1; self.fh.flush() if self.n%500==0 else None
    def close(self): self.fh.flush(); self.fh.close()

def data_of(x):
    raw=x if isinstance(x,dict) else {"_raw":x}; d=raw.get("data")
    if isinstance(d,dict): return raw,d
    if isinstance(d,str):
        try:
            y=json.loads(d)
            if isinstance(y,dict): return raw,y
        except Exception: pass
    return raw,raw

def is_futures(d): return str(d.get("pr","")).lower() in {"f","futures"}

def resolve(session,cfg):
    r=session.get(cfg["coindcx"]["base_api"]+"/exchange/v1/markets_details",timeout=30); r.raise_for_status(); items=r.json()
    available={str(x.get("pair")) for x in items if isinstance(x,dict) and x.get("pair")}
    out={}
    for x in cfg["coindcx"]["futures_symbols"]:
        if x["pair"] not in available: raise RuntimeError(f"Futures pair unavailable: {x['pair']}")
        out[x["name"]]=x["pair"]
    return out

class Collector:
    def __init__(self,cfg,out,duration):
        self.cfg=cfg; self.out=out; self.duration=max(5.0,float(duration)*60); self.stop_event=False; self.session=requests.Session(); self.sio=socketio.Client(reconnection=cfg["collector"].get("reconnect",True),reconnection_attempts=cfg["collector"].get("max_reconnect_attempts",12),logger=False,engineio_logger=False); self.books={}; self.w={}; self.count=Counter(); self.errors=[]; self.unknown=Counter(); self.connections=[]; self.pairs=set(); self.started=0; self.started_monotonic=time.monotonic(); self.last_event_monotonic=self.started_monotonic; self.last_event_utc=iso_now(); self.heartbeats=0
        self._handlers()
    def writer(self,k):
        if k not in self.w: self.w[k]=Writer(self.out/FILES[k])
        return self.w[k]
    def err(self,c,e): self.errors.append({"time_utc":iso_now(),"context":c,"error":str(e)}); print(self.errors[-1],flush=True)
    def mark_event(self): self.last_event_monotonic=time.monotonic(); self.last_event_utc=iso_now()
    def emit_record(self,k,resp,pair=None):
        raw,d=data_of(resp)
        if k in {"new-trade","price-change","depth-snapshot"} and not is_futures(d): return
        now=int(time.time()*1000); ex=d.get("T",d.get("ts"))
        rec={"received_at_utc":datetime.fromtimestamp(now/1000,tz=timezone.utc).isoformat(),"received_at_ms":now,"received_at_ns":time.time_ns(),"event":k,"market":"futures","exchange_timestamp_ms":ex,"pair":d.get("s") or pair,"raw":raw}
        self.writer(k).write(rec); self.count[k]+=1; self.mark_event()
    def _handlers(self):
        @self.sio.event
        def connect():
            self.connections.append({"time_utc":iso_now(),"state":"connected","market":"futures"})
            for ch in self.channels:
                try: self.sio.emit("join",{"channelName":ch})
                except Exception as e: self.err("join",e)
        @self.sio.event
        def disconnect(): self.connections.append({"time_utc":iso_now(),"state":"disconnected","market":"futures"})
        @self.sio.on("new-trade")
        def trade(r): self.emit_record("new-trade",r)
        @self.sio.on("price-change")
        def price(r): self.emit_record("price-change",r)
        @self.sio.on("currentPrices@futures#update")
        def cp(r): self.current(r)
        @self.sio.on("currentPrices@futures#snapshot")
        def cps(r): self.current(r)
        @self.sio.on("*")
        def unknown(e,*a):
            if e not in {"new-trade","price-change","currentPrices@futures#update","currentPrices@futures#snapshot","connect","disconnect","connect_error"}: self.unknown[e]+=1
    def current(self,r):
        raw,d=data_of(r); prices=d.get("prices") if isinstance(d,dict) else None
        if not isinstance(prices,dict): return
        sel={str(k):v for k,v in prices.items() if str(k) in self.pairs}
        if not sel: return
        now=int(time.time()*1000); self.writer("current-prices").write({"received_at_utc":datetime.fromtimestamp(now/1000,tz=timezone.utc).isoformat(),"received_at_ms":now,"received_at_ns":time.time_ns(),"event":"current-prices","market":"futures","exchange_timestamp_ms":d.get("ts"),"stream_timestamp_ms":d.get("pST"),"version":d.get("vs"),"pairs":sel}); self.count["current-prices"]+=1; self.mark_event()
    def start_books(self):
        url=self.cfg["coindcx"]["futures_socket_url"]; depth=int(self.cfg["coindcx"].get("futures_orderbook_depth",50)); kw={"reconnection":True,"reconnection_attempts":12,"logger":False,"engineio_logger":False}
        for pair in sorted(self.pairs):
            s=socketio.Client(**kw)
            @s.event
            def connect(s=s,pair=pair):
                try: s.emit("join",{"channelName":f"{pair}@orderbook@{depth}-futures"})
                except Exception as e: self.err(f"book_join:{pair}",e)
            @s.on("depth-snapshot")
            def depth_evt(r,pair=pair): self.emit_record("depth-snapshot",r,pair)
            try: s.connect(url,transports=["websocket"],wait_timeout=30); self.started+=1; self.books[pair]=s
            except Exception as e: self.err(f"book_connect:{pair}",e)
    def heartbeat(self):
        self.heartbeats += 1
        hb={"time_utc":iso_now(),"state":"heartbeat","market":"futures","elapsed_seconds":round(time.monotonic()-self.started_monotonic,3),"last_event_utc":self.last_event_utc,"seconds_since_event":round(time.monotonic()-self.last_event_monotonic,3),"event_counts":dict(self.count),"book_sockets_started":self.started,"socket_connected":bool(self.sio.connected)}
        self.connections.append(hb); print(json.dumps(hb,separators=(",",":")),flush=True)
    def run(self,pairs):
        self.out.mkdir(parents=True,exist_ok=True); self.pairs=set(pairs.values()); self.channels=["currentPrices@futures@rt"]+[f"{p}@trades-futures" for p in sorted(self.pairs)]+[f"{p}@prices-futures" for p in sorted(self.pairs)]; signal.signal(signal.SIGINT,lambda *_: setattr(self,"stop_event",True)); signal.signal(signal.SIGTERM,lambda *_: setattr(self,"stop_event",True)); heartbeat_s=max(5.0,float(self.cfg["collector"].get("heartbeat_seconds",60))); next_hb=time.monotonic()+heartbeat_s
        self.sio.connect(self.cfg["coindcx"]["futures_socket_url"],transports=["websocket"],wait_timeout=30); self.start_books(); end=time.monotonic()+self.duration
        while not self.stop_event and time.monotonic()<end:
            self.sio.sleep(0.25)
            now=time.monotonic()
            if now>=next_hb:
                self.heartbeat(); next_hb=now+heartbeat_s
        try:self.sio.disconnect()
        except Exception:pass
        for s in self.books.values():
            try:s.disconnect()
            except Exception:pass
        for w in self.w.values(): w.close()
        manifest={"schema_version":2,"market_mode":"FUTURES_ONLY","batch_id":self.out.name,"created_utc":iso_now(),"requested_duration_seconds":self.duration,"futures_pairs":pairs,"futures_streams":list(FILES),"futures_orderbook_channel_depth":int(self.cfg["coindcx"].get("futures_orderbook_depth",50)),"python_socketio_version":importlib.metadata.version("python-socketio"),"join_channels":self.channels,"book_sockets_started":self.started,"event_counts":dict(self.count),"unknown_events":dict(self.unknown),"errors":self.errors,"heartbeat_count":self.heartbeats,"first_event_utc":self.connections[0]["time_utc"] if self.connections else None,"last_event_utc":self.last_event_utc,"data_not_captured":["Spot websocket streams","individual order lifecycle/order-group events (not exposed by the captured public Futures feeds)","open interest","funding","liquidation events","separate mark/index price stream"],"notes":["No Spot websocket is opened.","Futures orderbooks are full per-instrument snapshots.","OI is not synthesized.","Heartbeat telemetry is emitted at the configured interval without altering the raw market files."]}
        (self.out/"manifest.json").write_text(json.dumps(manifest,indent=2)); required=list(FILES); missing=[k for k in required if self.count.get(k,0)==0]; q={"status":"PASS" if not missing and not self.errors else "PASS_WITH_ERRORS" if not missing else "FAIL_MISSING_STREAM","market_mode":"FUTURES_ONLY","required_event_counts":{k:int(self.count.get(k,0)) for k in required},"missing_required_streams":missing,"errors_count":len(self.errors),"heartbeat_count":self.heartbeats,"futures_pairs":pairs}; (self.out/"data_quality.json").write_text(json.dumps(q,indent=2)); return 0 if not missing else 3

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--duration-minutes",type=float); ap.add_argument("--out",required=True); a=ap.parse_args(); c=load_config(); d=a.duration_minutes or c["collector"]["default_duration_minutes"]; col=Collector(c,Path(a.out),d); return col.run(resolve(col.session,c))
if __name__=="__main__": raise SystemExit(main())
