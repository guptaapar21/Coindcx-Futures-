import gzip,json
from pathlib import Path
from src import futures_research

def write(path,rows):
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r)+'\n')

def test_grid_and_fixed_horizon(tmp_path: Path):
    b=tmp_path/'b';b.mkdir()
    write(b/'futures_trades.jsonl.gz',[
      {'raw':{'data':{'pr':'futures','s':'B-BTC_USDT','T':1000,'p':'100','q':'1','m':False}}},
      {'raw':{'data':{'pr':'futures','s':'B-BTC_USDT','T':3000,'p':'102','q':'2','m':False}}},
    ])
    rows=futures_research.build_rows(b); btc=[r for r in rows if r['symbol']=='B-BTC_USDT']
    assert [r['epoch_second'] for r in btc]==[1,2,3]
    assert btc[1]['futures_trade_count']==0
    assert btc[1]['close']==100.0
    assert btc[0]['futures_price_return_60s'] is None

def test_3m_aggregation_is_180_seconds():
    rows=[{'symbol':'B-BTC_USDT','epoch_second':x,'open':100+x,'high':100+x,'low':100+x,'close':100+x,'futures_trade_count':1,'futures_delta_qty':1.0,'futures_total_qty':2.0} for x in range(180)]
    out=futures_research.aggregate(rows,180)
    assert len(out)==1
    assert out[0]['epoch']==0
