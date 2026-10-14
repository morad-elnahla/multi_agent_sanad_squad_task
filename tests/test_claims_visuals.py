import pytest
from pipeline.models import Draft, Post, Judgment, Scores, Support, ClaimCheck, EvidenceQuote, VisualConcept
from pipeline.skills.claims import review_units, claim_checks, scope_warnings
from pipeline.skills.visuals import compose_visual
from pipeline.config import Config
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def case(text='A call can fail.', quote='A call can fail.', kind='factual'):
    draft=Draft(posts=[Post(text=text,evidence_ids=['ref'])])
    judgment=Judgment(approve=True,scores=Scores(accuracy=5,usefulness=5,clarity=5,brand_fit=5),
        support=[Support(post_index=0,supported=True,reason='ok')],reasons=[],
        claims=[ClaimCheck(unit_id='p1s1',kind=kind,supported=True,
            citations=[EvidenceQuote(evidence_id='ref',quote=quote)],reason='ok')])
    return draft,judgment

def test_exact_quote_and_coverage_pass():
    d,j=case()
    assert claim_checks(j,d,{'ref':'A call can fail.'},{})==[]

@pytest.mark.parametrize('mutation',['missing','duplicate','fakequote','unknown','uncited','noquote','question','cta','false'])
def test_grounding_gates(mutation):
    d,j=case()
    if mutation=='missing':j.claims=[]
    if mutation=='duplicate':j.claims*=2
    if mutation=='fakequote':j.claims[0].citations[0].quote='A call always fails.'
    if mutation=='unknown':j.claims[0].citations[0].evidence_id='fake'
    if mutation=='uncited':d.posts[0].evidence_ids=[]
    if mutation=='noquote':j.claims[0].citations=[]
    if mutation=='question':j.claims[0].kind='question'
    if mutation=='cta':j.claims[0].kind='cta'
    if mutation=='false':j.claims[0].supported=False
    assert claim_checks(j,d,{'ref':'A call can fail.'},{})

@pytest.mark.parametrize('text',['Contracts often skip checks.','Any caller will execute the function.','Do all state changes happen first?'])
def test_scope_flags_are_advisory_but_model_rejection_is_binding(text):
    d,j=case(text=text)
    if text.endswith('?'):j.claims[0].kind='question'
    rules={'claim_markers':['often','any','will','all']}
    assert scope_warnings(d,{'ref':'A call can fail.'},rules)
    assert claim_checks(j,d,{'ref':'A call can fail.'},rules)==[]
    j.claims[0].supported=False
    j.claims[0].reason='Unsupported expansion of source scope'
    assert claim_checks(j,d,{'ref':'A call can fail.'},rules)

def test_identifier_does_not_split_sentence():
    units=review_units(Draft(posts=[Post(text='Review tx.origin authorization. Check the caller.',evidence_ids=[])]))
    assert len(units)==2 and units[0]['text']=='Review tx.origin authorization.'

def test_visual_cannot_request_conflicting_labels():
    with pytest.raises(ValueError):VisualConcept(source_id='ref',layout='box labeled privileged function',symbol='gate')
    cfg=Config(ROOT)
    concept=VisualConcept(source_id='ref',layout='barrier',symbol='gate')
    spec=compose_visual(concept,'Access control',{'ref':'Check caller roles.'},cfg.visual_style)
    assert 'No visible text' in spec['prompt']
    assert spec['checks']['text_overlays'] is False
    with pytest.raises(ValueError):compose_visual(concept,'Access control',{},cfg.visual_style)
