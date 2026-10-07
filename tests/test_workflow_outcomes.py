from datetime import date
import json
from unittest.mock import patch
import pytest
from src.config import cfg
from src import workflow_run
from src.operational import DataUnavailable,PublicationRejected

@pytest.mark.parametrize('error',[DataUnavailable('Yahoo unavailable'),PublicationRejected('coverage insufficient')])
def test_operational_skip_is_normal_and_preserves_pointer(monkeypatch,tmp_path,error):
    pointer=tmp_path/'current.json';pointer.write_text('{"run":"old"}')
    output=tmp_path/'output';summary=tmp_path/'summary'
    monkeypatch.setenv('GITHUB_OUTPUT',str(output));monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    with patch('src.workflow_run.run_pipeline',side_effect=error):
        result=workflow_run.execute(date(2026,10,7))
    assert result['status']=='skipped' and not result['published']
    assert pointer.read_text()=='{"run":"old"}'
    assert 'published=false' in output.read_text() and 'ready=false' in output.read_text()
    assert 'not a successful live-data validation' in summary.read_text()


def test_programming_error_is_not_hidden(monkeypatch,tmp_path):
    monkeypatch.setenv('GITHUB_OUTPUT',str(tmp_path/'output'))
    with patch('src.workflow_run.run_pipeline',side_effect=TypeError('bug')):
        with pytest.raises(TypeError):workflow_run.execute()
    assert 'status=failed' in (tmp_path/'output').read_text()


def test_publish_enables_commit(monkeypatch,tmp_path):
    output=tmp_path/'output';monkeypatch.setenv('GITHUB_OUTPUT',str(output))
    with patch('src.workflow_run.run_pipeline'):
        assert workflow_run.execute()['published']
    assert 'published=true' in output.read_text()


def test_actual_no_prices_pipeline_skips_and_keeps_demo(monkeypatch,tmp_path):
    from src.pipeline import run_pipeline
    monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
    monkeypatch.setattr(cfg,'fundamentals_policy','verified')
    (tmp_path/'latest.json').write_text('{"date":"2025-05-16"}')
    with patch('src.pipeline.process_bank',return_value=None):
        result=workflow_run.execute()
    assert result['status']=='skipped'
    assert not (tmp_path/'current.json').exists()
    assert json.loads((tmp_path/'latest.json').read_text())['date']=='2025-05-16'
    assert json.loads((tmp_path/'last-attempt.json').read_text())['decision']=='rejected'
