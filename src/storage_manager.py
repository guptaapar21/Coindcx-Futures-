#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
import requests
API="https://api.github.com"
def hdr(t):return {"Accept":"application/vnd.github+json","Authorization":f"Bearer {t}","X-GitHub-Api-Version":"2022-11-28"}
def artifacts(s,o,r,t):
    out=[];page=1
    while True:
        x=s.get(f"{API}/repos/{o}/{r}/actions/artifacts",headers=hdr(t),params={"per_page":100,"page":page},timeout=30);x.raise_for_status(); a=x.json().get("artifacts",[]);out.extend(a)
        if len(a)<100:break
        page+=1
    return [x for x in out if not x.get("expired")]
def parse_repo():
    x=os.environ["GITHUB_REPOSITORY"];return x.split("/",1)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--force",action="store_true");a=ap.parse_args(); token=os.environ.get("GITHUB_TOKEN");
    if not token:raise RuntimeError("GITHUB_TOKEN required")
    owner,repo=parse_repo();s=requests.Session();ars=artifacts(s,owner,repo,token); raw=[x for x in ars if str(x.get("name","")).startswith("coindcx-futures-raw-")]; total=sum(int(x.get("size_in_bytes",0)) for x in ars); budget=500*1024*1024;pct=100*total/budget if budget else 0;should=a.force or pct>=70
    report={"checked_utc":datetime.now(timezone.utc).isoformat(),"repository":f"{owner}/{repo}","all_artifact_count":len(ars),"futures_raw_artifact_count":len(raw),"all_artifact_bytes":total,"budget_bytes":budget,"all_artifact_storage_percent":pct,"archive_policy":"Only coindcx-futures-raw-* artifacts are eligible for rotation; repository-wide usage determines when rotation starts.","should_archive":should,"selected":[]}
    # Keep housekeeping repository-local: this repo rotates only its own Futures artifacts.
    eligible=sorted(raw,key=lambda x:x.get("created_at") or "")
    if should:
        running=total;target=.5*budget
        for x in eligible:
            if running<=target:break
            report["selected"].append(x["name"]);running-=int(x.get("size_in_bytes",0))
    Path("storage_report.json").write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=="__main__":main()
