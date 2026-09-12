import json
from pathlib import Path
from src.futures_collector import FILES, is_futures


def test_futures_collector_has_only_futures_outputs():
    assert set(FILES.values()) == {
        'futures_trades.jsonl.gz',
        'futures_price_change.jsonl.gz',
        'futures_current_prices.jsonl.gz',
        'futures_depth_snapshot.jsonl.gz',
    }
    assert is_futures({'pr': 'futures'})
    assert not is_futures({'pr': 'spot'})


def test_futures_default_batch_duration_is_120_minutes():
    cfg = json.loads(Path('config.json').read_text(encoding='utf-8'))
    assert cfg['collector']['default_duration_minutes'] == 120


def test_futures_default_workflow_duration_is_120_minutes():
    workflow = Path('.github/workflows/continuous-collector.yml').read_text(encoding='utf-8')
    assert 'default: "120"' in workflow
    assert "minutes=\"${{ inputs.duration_minutes || '120' }}\"" in workflow
    assert "duration_minutes]=\"${DURATION_MINUTES}\"" in workflow
