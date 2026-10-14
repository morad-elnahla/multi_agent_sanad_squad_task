"""Replay recorded handoffs without API calls; no new live success implied."""
import json
from pathlib import Path
import pytest
from pipeline.models import Draft, Judgment
from pipeline.skills.claims import claim_checks, scope_warnings

CASES=json.loads((Path(__file__).parent/'fixtures/live-review-regression.json').read_text())

@pytest.mark.parametrize('entry',CASES,ids=lambda e:e['slot'])
def test_recorded_final_reviews(entry):
    draft=Draft.model_validate(entry['draft'])
    judgment=Judgment.model_validate(entry['judgment'])
    rules={'claim_markers':['any','never','will']}
    errors=claim_checks(judgment,draft,entry['evidence'],rules)
    if entry['slot']=='thread_1':
        # The live reviewer approved; only the removed lexical veto rejected it.
        assert judgment.approve and not errors
        assert scope_warnings(draft,entry['evidence'],rules)
    else:
        # Actual model rejections and missing quotes must not be bypassed.
        assert not judgment.approve and errors

@pytest.mark.parametrize(('text','source'),[
    ('Later logic may rely on an operation that never completed.',
     'Later logic may rely on an operation that did not complete.'),
    ('How will you verify role assignment?',
     'Role assignment is permission-sensitive.')])
def test_valid_paraphrase_does_not_require_matching_words(text,source):
    from test_claims_visuals import case
    draft,judgment=case(text,source,'question' if text.endswith('?') else 'factual')
    rules={'claim_markers':['never','will']}
    assert scope_warnings(draft,{'ref':source},rules)
    assert claim_checks(judgment,draft,{'ref':source},rules)==[]
