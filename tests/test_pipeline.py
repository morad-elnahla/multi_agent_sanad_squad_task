import asyncio
import csv
import json
from pathlib import Path
import pytest
from pipeline.config import Config
from pipeline.demo import DemoProvider
from pipeline.models import Plan, Slot, Draft, Post, Judgment, Scores, Support
from pipeline.orchestrator import run_week, apply_overrides, allocate_candidates, usage_summary
from pipeline.skills.brand import hard_checks, decide

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def config():
    return Config(ROOT)

def plan(*slots):
    return Plan(slots=[Slot(id=s[0], type=s[1], focus=s[2]) for s in slots])

def run(tmp_path, config, provider=None, items=None, concurrency=3):
    output = tmp_path / 'run'
    result = asyncio.run(run_week(items or Plan.model_validate_json((ROOT/'plan.json').read_text()),
                                 config, provider or DemoProvider(), output, concurrency))
    return result, output

def load(output, name):
    return json.loads((output/name).read_text())['data']

def test_complete_week(config, tmp_path):
    result, output = run(tmp_path, config)
    assert result['pieces_shipped'] == 6
    assert result['usage']['calls'] == 24
    assert result['usage']['cost_usd'] == 0
    with (output/'posts.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 6 and set(rows[0]) == {'Post Text','Image'}
    assert len(rows[0]['Post Text'].split('\n\n')) == 5
    assert all((output/r['Image']).is_file() for r in rows)
    assert len(load(output, 'research_log.json')) == 6
    assert len(load(output, 'review_report.json')) == 6
    assert len(load(output, 'final_content.json')) == 6

class RejectOnce(DemoProvider):
    def __init__(self, always=False):
        super().__init__()
        self.writes = 0
        self.always = always
        self.feedback_seen = None

    async def generate(self, role, prompt, payload, schema, slot):
        value = await super().generate(role, prompt, payload, schema, slot)
        if role == 'writer':
            self.writes += 1
            self.feedback_seen = payload['feedback']
            if self.always or self.writes == 1:
                value.posts[0].text += ' #unsafe'
        return value

def test_rejection_retries_once_with_feedback(config,tmp_path):
    provider = RejectOnce()
    result, output = run(tmp_path, config, provider, plan(('a','tech-thread','reentrancy')))
    assert result['pieces_shipped'] == 1 and provider.writes == 2
    assert provider.feedback_seen
    reports = load(output,'review_report.json')[0]['reviews']
    assert not reports[0]['accepted'] and reports[1]['accepted']
    assert len(list((output/'visuals').glob('*'))) == 1

def test_second_rejection_drops_without_visual(config,tmp_path):
    provider = RejectOnce(always=True)
    result, output = run(tmp_path, config, provider, plan(('a','tech-thread','reentrancy')))
    assert result['pieces_dropped'] == 1 and provider.writes == 2
    assert not (output/'visuals').exists()
    assert not any(c['role']=='visual' for c in provider.calls)
    assert load(output,'final_content.json') == []

class FailStage(DemoProvider):
    def __init__(self, stage):
        super().__init__()
        self.stage=stage
    async def generate(self, role, prompt, payload, schema, slot):
        if role == self.stage and slot == 'bad':
            raise TimeoutError('test failure')
        return await super().generate(role,prompt,payload,schema,slot)

@pytest.mark.parametrize('stage',['research','writer','reviewer','visual'])
def test_failure_isolation(config,tmp_path,stage):
    result, output = run(tmp_path,config,FailStage(stage),plan(
        ('bad','tech-thread','reentrancy'),('good','marketing','oracle manipulation')))
    assert result['pieces_shipped']==1 and result['pieces_dropped']==1
    assert load(output,'final_content.json')[0]['slot_id']=='good'
    assert result['dropped'][0]['status']=='failed'

def test_unknown_source_and_post_type_are_isolated(config,tmp_path):
    result,_=run(tmp_path,config,items=plan(('bad','tech-thread','not a real vulnerability'),
        ('unknown','new-type','reentrancy'),('good','marketing','reentrancy')))
    assert result['pieces_shipped']==1 and result['pieces_dropped']==2

def test_overrides_and_duplicate_ids():
    p=plan(('a','tech-thread',''))
    assert apply_overrides(p,['a=oracle manipulation']).slots[0].focus=='oracle manipulation'
    assert p.slots[0].focus==''
    with pytest.raises(ValueError): apply_overrides(p,['missing=reentrancy'])
    with pytest.raises(ValueError): apply_overrides(p,['bad'])
    with pytest.raises(ValueError): plan(('a','marketing',''),('a','marketing',''))

def test_empty_slots_deduplicate(config):
    p=Plan.model_validate_json((ROOT/'plan.json').read_text())
    candidates=allocate_candidates(p,config.kb)
    assert len({v[0]['id'] for v in candidates.values()}) == 6

@pytest.mark.parametrize('text,reference',[
    ('hello — world','valid'),('hello #audit','valid'),('revolutionary audit','valid'),
    ('x'*281,'valid'),('Visit https://evil.example','valid'),('Visit evil.com','valid'),
    ('hello','made-up'),('=IMPORTDATA("x")','valid'),('hello 💥','valid')])
def test_hard_rules(config,text,reference):
    d=Draft(posts=[Post(text=text,evidence_ids=[reference])])
    assert hard_checks(d,config.types['marketing'][0],config.rules,{'valid':'text'})

def test_valid_code_identifier(config):
    d=Draft(posts=[Post(text='Review tx.origin authorization.',evidence_ids=['ref'])])
    assert hard_checks(d,config.types['marketing'][0],config.rules,{'ref':'text'})==[]

@pytest.mark.parametrize('case',['hard','low_score','unsupported','missing','explicit_reject','duplicate'])
def test_model_cannot_bypass_gates(config,case):
    d=Draft(posts=[Post(text='Example',evidence_ids=[])])
    j=Judgment(approve=True,scores=Scores(accuracy=5,usefulness=5,clarity=5,brand_fit=5),
               support=[Support(post_index=0,supported=True,reason='ok')],reasons=[])
    errors=[]
    if case=='hard': errors=['Banned punctuation']
    if case=='low_score': j.scores.accuracy=1
    if case=='unsupported': j.support[0].supported=False
    if case=='missing': j.support=[]
    if case=='explicit_reject': j.approve=False
    if case=='duplicate': j.support.append(j.support[0])
    assert not decide(j,d,errors,config.rubric)['accepted']

class ConcurrencyProbe(DemoProvider):
    def __init__(self):
        super().__init__();self.active=0;self.peak=0
    async def generate(self,*args):
        self.active+=1;self.peak=max(self.peak,self.active)
        try:
            await asyncio.sleep(.005)
            return await super().generate(*args)
        finally: self.active-=1

def test_work_is_parallel_but_bounded(config,tmp_path):
    provider=ConcurrencyProbe()
    run(tmp_path,config,provider,concurrency=2)
    assert provider.peak==2

def test_existing_run_cannot_be_overwritten(config,tmp_path):
    run(tmp_path,config)
    with pytest.raises(FileExistsError): run(tmp_path,config)

def test_unknown_usage_is_not_reported_as_free():
    provider=DemoProvider()
    provider.calls=[{'input_tokens':None,'output_tokens':None,'cost_usd':None}]
    summary=usage_summary(provider)
    assert summary['cost_usd'] is None and not summary['token_totals_complete']

def test_file_based_post_type_extension(config,tmp_path):
    import shutil
    root=tmp_path/'config'
    shutil.copytree(ROOT,root,ignore=shutil.ignore_patterns('.git','output','__pycache__','.pytest_cache'))
    new=root/'post_types'/'short-note';new.mkdir()
    (new/'type.json').write_text(json.dumps({'name':'short-note','min_posts':1,'max_posts':1,'max_characters':280,'writer':'writer.md'}))
    (new/'writer.md').write_text('Write one useful note with cited evidence.')
    result,_=run(tmp_path,Config(root),items=plan(('a','short-note','reentrancy')))
    assert result['pieces_shipped']==1
