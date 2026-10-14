"""Rebuild checked-in JSON Schema contracts after changing Pydantic models."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import Plan, Knowledge, PostType, TopicChoice, Draft, Judgment, Visual, VisualConcept
for model in (Plan, Knowledge, PostType, TopicChoice, Draft, Judgment, Visual, VisualConcept):
    (ROOT/'schemas'/f'{model.__name__}.schema.json').write_text(
        json.dumps(model.model_json_schema(), indent=2) + '\n')
(ROOT/'schemas'/'artifact.schema.json').write_text(json.dumps({
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    'title':'RunArtifact', 'type':'object', 'additionalProperties':False,
    'required':['schema_version','kind','data'],
    'properties':{'schema_version':{'enum':['1.0','1.1']}, 'kind':{'enum':[
        'plan','input_snapshot','resolved_plan','research_log','drafts','review_report',
        'final_content','run_summary','usage','events','piece_state','image_spec']},
        'data':{'type':['object','array']}}
}, indent=2)+'\n')
