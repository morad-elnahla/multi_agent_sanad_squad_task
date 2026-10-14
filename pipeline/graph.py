"""A separately invoked LangGraph per slot; state never leaks between pieces."""
import asyncio
import json
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .models import Draft, Judgment, TopicChoice, VisualConcept
from .providers import ProviderFailure
from .skills.knowledge import evidence_for, provenance_for
from .skills.claims import review_units, claim_checks, scope_warnings
from .skills.visuals import compose_visual
from .skills.brand import hard_checks, decide
from .artifacts import write_json, now

class PieceState(TypedDict, total=False):
    slot: dict
    candidates: list
    topic: str
    research: dict
    evidence: dict
    draft: dict
    drafts: list
    reviews: list
    attempt: int
    accepted: bool
    status: str
    reasons: list
    visual_path: str
    visual: dict

class PieceGraph:
    def __init__(self, config, provider, output, events, notify=None):
        self.notify = notify or (lambda event: None)
        self.config, self.provider, self.output, self.events = config, provider, output, events
        self.by_id = {k.id: k for k in config.kb}
        graph = StateGraph(PieceState)
        for name in ('research', 'write', 'review', 'visual'):
            graph.add_node(name, self.guard(name, getattr(self, name)))
        graph.add_edge(START, 'research')
        graph.add_conditional_edges('research', lambda s: END if s.get('status') == 'failed' else 'write')
        graph.add_conditional_edges('write', lambda s: END if s.get('status') == 'failed' else 'review')
        graph.add_conditional_edges('review', self.after_review)
        graph.add_edge('visual', END)
        self.graph = graph.compile()

    def guard(self, name, fn):
        async def wrapped(state):
            slot = state['slot']['id']
            event = {'slot': slot, 'stage': name, 'event': 'start', 'time': now()}
            self.events.append(event)
            self.notify(event)
            try:
                update = await fn(state)
            except Exception as exc:
                # No raw provider exception text: it can contain sensitive data.
                detail = str(exc) if isinstance(exc, ProviderFailure) else type(exc).__name__
                update = {'status': 'failed', 'reasons': [f'{name} failed: {detail}']}
            merged = {**state, **update}
            write_json(self.output / 'pieces' / slot / 'state.json', 'piece_state', merged)
            event = {'slot': slot, 'stage': name, 'event': 'end', 'time': now(),
                     'status': merged.get('status', 'running')}
            self.events.append(event)
            self.notify(event)
            return update
        return wrapped

    @staticmethod
    def after_review(state):
        if state.get('status') in ('failed', 'dropped'):
            return END
        return 'visual' if state['accepted'] else 'write'

    async def call(self, role, instructions, payload, schema, state):
        return await self.provider.generate(role, instructions, payload, schema, state['slot']['id'])

    async def research(self, state):
        if not state['candidates']:
            return {'status': 'failed', 'reasons': ['No matching or unused KB source for the requested topic']}
        choice = await self.call('research', self.config.read('prompts/research.md'),
                                 {'focus': state['slot']['focus'], 'candidates': state['candidates']},
                                 TopicChoice, state)
        if choice.kb_id not in {c['id'] for c in state['candidates']}:
            raise ValueError('Research returned a source outside its candidates')
        entry = self.by_id[choice.kb_id]
        evidence = evidence_for(entry)
        return {'topic': entry.name, 'evidence': evidence,
                'research': {'kb_id': entry.id, 'source': f'kb:{entry.id}',
                             'background_url': entry.source_url,
                             'source_mode': 'local curated KB, not a live URL fetch',
                             'reason': choice.reason, 'evidence': evidence,
                             'provenance': provenance_for(entry)},
                'attempt': 0, 'drafts': [], 'reviews': [], 'status': 'running'}

    async def write(self, state):
        post_type, instructions = self.config.types[state['slot']['type']]
        draft = await self.call('writer', instructions,
             {'topic': state['topic'], 'post_type': post_type.model_dump(),
              'brand': self.config.brand, 'evidence': state['evidence'],
              'approved_ctas': self.config.rules.get('approved_ctas', []),
              'image_brief': self.config.read('pipeline/skills/image_brief.md'),
              'previous_draft': state.get('draft'),
              'feedback': state['reviews'][-1]['reasons'] if state['reviews'] else []}, Draft, state)
        attempt = state['attempt'] + 1
        value = draft.model_dump()
        return {'draft': value, 'attempt': attempt,
                'drafts': state['drafts'] + [{'attempt': attempt, 'draft': value}]}

    async def review(self, state):
        draft = Draft.model_validate(state['draft'])
        post_type = self.config.types[state['slot']['type']][0]
        # Rebuild evidence independently rather than trusting writer output.
        evidence = evidence_for(self.by_id[state['research']['kb_id']])
        errors = hard_checks(draft, post_type, self.config.rules, evidence)
        warnings = scope_warnings(draft, evidence, self.config.rules)
        judgment = await self.call('reviewer', self.config.read('prompts/reviewer.md'),
             {'draft': state['draft'], 'evidence': evidence, 'brand': self.config.brand,
              'rubric': self.config.rubric, 'hard_errors': errors,
              'review_units': review_units(draft),
              'scope_warnings': warnings,
              'approved_ctas': self.config.rules.get('approved_ctas', [])}, Judgment, state)
        errors.extend(claim_checks(judgment, draft, evidence, self.config.rules))
        report = decide(judgment, draft, errors, self.config.rubric)
        report['scope_warnings'] = warnings
        report['attempt'] = state['attempt']
        accepted = report['accepted']
        dropped = not accepted and state['attempt'] >= 2
        return {'accepted': accepted, 'reviews': state['reviews'] + [report],
                'status': 'dropped' if dropped else 'running',
                'reasons': report['reasons']}

    async def visual(self, state):
        # Only expose sources actually cited by the accepted piece.
        cited = {ref for p in state['draft']['posts'] for ref in p['evidence_ids']}
        evidence = {key: value for key, value in state['evidence'].items() if key in cited}
        concept = await self.call('visual', self.config.read('prompts/visual.md'),
             {'topic': state['topic'], 'draft': state['draft'], 'evidence': evidence,
              'image_brief': self.config.read('pipeline/skills/image_brief.md')}, VisualConcept, state)
        visual = compose_visual(concept, state['topic'], evidence, self.config.visual_style)
        relative = f"visuals/{state['slot']['id']}.json"
        write_json(self.output / relative, 'image_spec', visual)
        return {'visual': visual, 'visual_path': relative, 'status': 'shipped', 'reasons': []}

    async def run(self, slot, candidates):
        return await self.graph.ainvoke({'slot': slot.model_dump(), 'candidates': candidates},
                                       config={'recursion_limit': 20})
