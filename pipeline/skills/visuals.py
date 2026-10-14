"""Compose a spec from typed visual choices; no free-form label instructions."""

def compose_visual(concept, topic, evidence, brief):
    if concept.source_id not in evidence:
        raise ValueError('Visual concept references an unknown source')
    layouts = brief['layouts']
    symbols = brief['symbols']
    if concept.layout not in layouts or concept.symbol not in symbols:
        raise ValueError('Visual choice is not approved')
    prompt = ' '.join([brief['style'], f'Conceptual topic: {topic}.',
                       layouts[concept.layout], symbols[concept.symbol], brief['text_policy']])
    return {'prompt': prompt,
            'alt_text': f"Conceptual illustration about {topic}: {layouts[concept.layout]} {symbols[concept.symbol]}",
            'artifact_type': 'written_image_spec', 'width': 1600, 'height': 900,
            'source_ids': [concept.source_id], 'concept': concept.model_dump(),
            'checks': {'valid_source': True, 'approved_layout': True,
                       'approved_symbol': True, 'text_overlays': False},
            'evidence_context': evidence[concept.source_id]}
