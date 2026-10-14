"""Plan handling, bounded concurrency, collection and observability."""
import asyncio
import hashlib
from pathlib import Path
from .artifacts import write_json, export_csv, now
from .graph import PieceGraph
from .skills.knowledge import search_kb


def apply_overrides(plan, overrides):
    result = plan.model_copy(deep=True)
    by_id = {s.id: s for s in result.slots}
    for value in overrides:
        if '=' not in value:
            raise ValueError('Overrides must use SLOT=TOPIC')
        slot, topic = value.split('=', 1)
        if slot not in by_id:
            raise ValueError(f'Unknown override slot: {slot}')
        if len(topic) > 200:
            raise ValueError('Override topic exceeds 200 characters')
        by_id[slot].focus = topic.strip()
    return result


def allocate_candidates(plan, kb):
    """Reserve explicit topics first, then distinct empty-slot candidates in order."""
    reserved = {k.id for s in plan.slots if s.focus.strip() for k in search_kb(kb, s.focus)}
    allocated = {}
    for slot in plan.slots:
        if slot.focus.strip():
            candidates = search_kb(kb, slot.focus)
        else:
            candidates = [k for k in kb if k.id not in reserved][:1]
            reserved.update(k.id for k in candidates)
        allocated[slot.id] = [k.model_dump() for k in candidates]
    return allocated


def usage_summary(provider):
    calls = provider.calls
    cost_known = all(c['cost_usd'] is not None for c in calls)
    return {'model': provider.model, 'calls': len(calls),
            'rate_limit_responses': sum(c.get('status') == 'rate_limited' for c in calls),
            'provider_settings': provider.settings_snapshot() if hasattr(provider, 'settings_snapshot') else None,
            'input_tokens_recorded': sum(c['input_tokens'] or 0 for c in calls),
            'output_tokens_recorded': sum(c['output_tokens'] or 0 for c in calls),
            'token_totals_complete': all(c['input_tokens'] is not None and c['output_tokens'] is not None for c in calls),
            'cost_usd': round(sum(c['cost_usd'] for c in calls), 8) if cost_known else None,
            'cost_status': ('known: no model calls' if provider.mode == 'demo' else 'estimated at configured token rates') if cost_known else 'unknown: rates or provider usage missing',
            'rates_usd_per_million': {'input': provider.rates[0], 'output': provider.rates[1]}}


async def run_week(plan, config, provider, output: Path, concurrency=3, notify=None):
    if concurrency < 1 or concurrency > 20:
        raise ValueError('Concurrency must be between 1 and 20')
    # Never merge runs or silently overwrite evidence from a previous run.
    output.mkdir(parents=True, exist_ok=False)
    started = now()
    events = []
    write_json(output / 'input_plan.json', 'plan', plan.model_dump())
    snapshots = {}
    for pattern in ('brand-voice.md','kb.json','rubric.json','visual-style.json','prompts/*.md',
                    'post_types/*/*.md','post_types/*/*.json','pipeline/skills/*.md'):
        for path in config.root.glob(pattern):
            relative = str(path.relative_to(config.root))
            text = config.read(path.relative_to(config.root).as_posix())
            snapshots[relative] = {'sha256': hashlib.sha256(text.encode()).hexdigest(), 'content': text}
    write_json(output / 'input_snapshot.json', 'input_snapshot', snapshots)
    graph = PieceGraph(config, provider, output, events, notify=notify)
    candidates = allocate_candidates(plan, config.kb)
    semaphore = asyncio.Semaphore(concurrency)

    async def work(slot):
        async with semaphore:
            if slot.type not in config.types:
                return {'slot': slot.model_dump(), 'status': 'failed', 'reasons': ['Unknown post type']}
            try:
                return await graph.run(slot, candidates[slot.id])
            except Exception as exc:
                return {'slot': slot.model_dump(), 'status': 'failed',
                        'reasons': [f'Piece execution failed: {type(exc).__name__}']}

    results = await asyncio.gather(*(work(slot) for slot in plan.slots))
    shipped = [r for r in results if r['status'] == 'shipped']
    rejected = [r for r in results if r['status'] != 'shipped']
    write_json(output / 'resolved_plan.json', 'resolved_plan', [
        {**r['slot'], 'topic': r.get('topic'), 'source': r.get('research', {}).get('source'),
         'status': r['status']} for r in results])
    for filename, kind, field in [('research_log.json','research_log','research'),
                                 ('drafts.json','drafts','drafts'),
                                 ('review_report.json','review_report','reviews')]:
        write_json(output / filename, kind, [
            {'slot_id': r['slot']['id'], 'status': r['status'], field: r.get(field),
             'reasons': r.get('reasons', [])} for r in results])
    write_json(output / 'final_content.json', 'final_content', [
        {'slot_id': r['slot']['id'], 'type': r['slot']['type'], 'topic': r['topic'],
         'posts': r['draft']['posts'], 'image_spec': r['visual_path']} for r in shipped])
    export_csv(output / 'posts.csv', results)
    write_json(output / 'events.json', 'events', events)
    write_json(output / 'usage.json', 'usage', provider.calls)
    summary = {'started_at': started, 'finished_at': now(), 'mode': provider.mode,
               'demo_notice': 'Fixture output; no live model evaluation' if provider.mode == 'demo' else None,
               'pieces_requested': len(results), 'pieces_shipped': len(shipped),
               'pieces_dropped': len(rejected),
               'dropped': [{'slot_id': r['slot']['id'], 'status': r['status'], 'reasons': r['reasons']} for r in rejected],
               'usage': usage_summary(provider),
               'export_contract': 'One row per piece; blank-line-separated thread; Image is a local spec path, not rendered media.'}
    write_json(output / 'run_summary.json', 'run_summary', summary)
    return summary
