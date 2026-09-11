from pathlib import Path
from src.futures_collector import FILES, is_futures

def test_futures_collector_has_only_futures_outputs():
    assert set(FILES.values()) == {'futures_trades.jsonl.gz','futures_price_change.jsonl.gz','futures_current_prices.jsonl.gz','futures_depth_snapshot.jsonl.gz'}
    assert is_futures({'pr':'futures'})
    assert not is_futures({'pr':'spot'})
