import io
import json
import shutil
import time
import zipfile
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from pipeline.ui_files import save_config, zip_run
from pipeline.config import Config

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def project(tmp_path,monkeypatch):
    target=tmp_path/'project'
    shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','output','__pycache__','.pytest_cache','.venv'))
    monkeypatch.setenv('SANAD_PROJECT_ROOT',str(target))
    return target

def test_app_demo_runs_and_displays_results(project):
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
    assert not at.exception
    next(b for b in at.button if b.label=='Run pipeline').click().run()
    job=at.session_state['job']
    until=time.monotonic()+10
    while not job.done and time.monotonic()<until:time.sleep(.02)
    assert job.done and job.summary['pieces_shipped']==6
    at.run()
    assert not at.exception
    assert any(m.label=='Shipped' and m.value=='6' for m in at.metric)
    assert any(c.value for c in at.code)
    assert (job.output/'posts.csv').is_file()

def test_app_live_requires_key_without_sending_request(project,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
    next(r for r in at.radio if r.label=='Mode').set_value('Live').run()
    next(b for b in at.button if b.label=='Run pipeline').click().run()
    assert not at.exception
    assert any('OPENAI_API_KEY' in e.value for e in at.error)

def test_invalid_config_edit_does_not_overwrite(project):
    old=(project/'kb.json').read_bytes()
    with pytest.raises(ValueError):save_config(project,'kb.json','invalid JSON')
    assert (project/'kb.json').read_bytes()==old
    with pytest.raises(ValueError):save_config(project,'../outside','.env')

def test_config_is_immutable_during_run(project):
    config=Config(project)
    original=config.read('prompts/reviewer.md')
    (project/'prompts/reviewer.md').write_text('Changed during the run')
    assert config.read('prompts/reviewer.md')==original

def test_download_zip_excludes_secrets(tmp_path):
    (tmp_path/'posts.csv').write_text('Post Text,Image\n')
    (tmp_path/'.env').write_text('PRIVATE=secret')
    z=zipfile.ZipFile(io.BytesIO(zip_run(tmp_path)))
    assert len(z.namelist())==1 and z.namelist()[0].endswith('posts.csv')


def test_history_filters_latest_live_run(project):
    shutil.copytree(ROOT/'output/live-week-latest', project/'output/live-week-latest')
    shutil.copytree(ROOT/'output/sample-week', project/'output/sample-week')
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
    assert not at.exception
    assert any(m.label=='Shipped' and m.value=='5' for m in at.metric)
    search=next(x for x in at.text_input if x.label=='Find a piece')
    search.set_value('Reentrancy').run()
    assert not at.exception
    assert len(at.code)==5
    next(x for x in at.text_input if x.label=='Find a piece').set_value('no-matching-piece').run()
    assert any('No matching content' in x.value for x in at.info)
