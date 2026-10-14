"""Deterministic extractive demo; not an LLM quality assessment."""
import asyncio
import re
from .models import (Draft, Post, Judgment, Scores, Support, TopicChoice,
                     VisualConcept, ClaimCheck, EvidenceQuote)

class DemoProvider:
    mode = 'demo'
    model = 'extractive-demo-fixture'
    rates = [0, 0]

    def __init__(self):
        self.calls = []

    async def generate(self, role, prompt, payload, schema, slot):
        await asyncio.sleep(0)
        self.calls.append({'slot': slot, 'role': role,
                           'agent': f"writer:{payload['post_type']['name']}" if role == 'writer' else role,
                           'model': self.model, 'input_tokens': 0, 'output_tokens': 0,
                           'cost_usd': 0, 'status': 'fixture', 'latency_seconds': 0})
        if role == 'research':
            return TopicChoice(kb_id=payload['candidates'][0]['id'], reason='Deterministic first unused matching KB entry')
        if role == 'writer':
            ev = payload['evidence']
            keys = list(ev)
            if payload['post_type']['min_posts'] == 1:
                return Draft(posts=[Post(text=f"{ev[keys[1]]} DM to discuss a security review.", evidence_ids=[keys[1]])])
            # Five distinct extractive facts, including expanded KB material.
            chosen = [keys[1], keys[4], keys[2], keys[5], keys[3]]
            return Draft(posts=[Post(text=ev[k], evidence_ids=[k]) for k in chosen])
        if role == 'reviewer':
            ev = payload['evidence']
            checks = []
            for unit in payload['review_units']:
                text = unit['text']
                matched = [(k, v) for k, v in ev.items() if text in v]
                cta = text in payload['approved_ctas']
                valid = bool(matched) or cta
                checks.append(ClaimCheck(unit_id=unit['unit_id'], kind='cta' if cta else 'factual',
                      supported=valid,
                      citations=[EvidenceQuote(evidence_id=matched[0][0], quote=text)] if matched else [],
                      reason='Exact fixture check' if valid else 'Not an exact extractive fixture'))
            support = []
            for i, post in enumerate(payload['draft']['posts']):
                ids = [u['unit_id'] for u in payload['review_units'] if u['post_index'] == i]
                supported = all(c.supported for c in checks if c.unit_id in ids)
                support.append(Support(post_index=i, supported=supported, reason='Fixture-only support check'))
            return Judgment(approve=all(c.supported for c in checks),
                    scores=Scores(accuracy=4, usefulness=4, clarity=4, brand_fit=4),
                    support=support, claims=checks, reasons=['Demo fixture scores, not model evaluation'])
        if role == 'visual':
            return VisualConcept(source_id=next(iter(payload['evidence'])), layout='flow', symbol='arrows')
        raise ValueError('Unsupported demo role')
