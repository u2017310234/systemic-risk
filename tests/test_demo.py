from pathlib import Path
import json
import pytest
from src.demo import install_demo
ROOT=Path(__file__).resolve().parents[1]


def test_real_27_bank_demo_preserves_snapshot_and_no_invented_history(tmp_path):
 p=ROOT/'examples/verified-disclosures-v23/reconstructed-snapshot.json'
 install_demo(p,tmp_path/'demo')
 assert json.loads((tmp_path/'demo/latest.json').read_text())==json.loads(p.read_text())
 assert len(list((tmp_path/'demo/history').iterdir()))==1
 assert len(list((tmp_path/'demo/banks').iterdir()))==27


def test_demo_refuses_nonempty_destination(tmp_path):
 p=ROOT/'examples/verified-disclosures-v23/reconstructed-snapshot.json'
 (tmp_path/'keep').write_text('keep')
 with pytest.raises(ValueError,match='empty'):install_demo(p,tmp_path)
 assert (tmp_path/'keep').read_text()=='keep'


def test_demo_refuses_unlabeled_snapshot(tmp_path):
 p=tmp_path/'input.json';p.write_text('{"dataset_kind":"production"}')
 with pytest.raises(ValueError):install_demo(p,tmp_path/'out')
