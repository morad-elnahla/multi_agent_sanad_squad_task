"""Deterministic review coverage and evidence-quote checks, not semantic proof."""
import re


def review_units(draft):
    """Split at sentence/semicolon boundaries; dotted identifiers stay intact."""
    return [{'unit_id': f'p{i + 1}s{j + 1}', 'post_index': i, 'text': text}
            for i, post in enumerate(draft.posts)
            for j, text in enumerate(re.split(r'(?<=[.!?;])\s+', post.text.strip())) if text]


def scope_warnings(draft, evidence, rules):
    """Flag wording for semantic review; lexical mismatch is not falsity."""
    warnings = []
    for unit in review_units(draft):
        refs = draft.posts[unit['post_index']].evidence_ids
        source_text = ' '.join(evidence.get(ref, '') for ref in refs)
        for marker in rules.get('claim_markers', []):
            pattern = r'(?<!\w)' + re.escape(marker) + r'(?!\w)'
            if re.search(pattern, unit['text'], re.I) and not re.search(pattern, source_text, re.I):
                warnings.append({'unit_id': unit['unit_id'], 'marker': marker,
                                 'message': 'Assess meaning in context; word absence is not a rejection reason.'})
    return warnings


def claim_checks(judgment, draft, evidence, rules):
    units = {u['unit_id']: u for u in review_units(draft)}
    claims = judgment.claims
    errors = []
    if sorted(c.unit_id for c in claims) != sorted(units):
        errors.append('Reviewer must check each supplied sentence unit exactly once')
    for claim in claims:
        unit = units.get(claim.unit_id)
        if unit is None:
            continue
        prefix = f"{claim.unit_id}: "
        if not claim.supported:
            errors.append(prefix + claim.reason)
        if claim.kind == 'factual' and not claim.citations:
            errors.append(prefix + 'Factual claim has no evidence quote')
        if claim.kind == 'question' and not unit['text'].rstrip().endswith('?'):
            errors.append(prefix + 'Statement incorrectly classified as a question')
        if claim.kind == 'cta' and unit['text'] not in rules.get('approved_ctas', []):
            errors.append(prefix + 'CTA is not in the approved non-factual CTA list')
        for citation in claim.citations:
            source = evidence.get(citation.evidence_id)
            if source is None or citation.quote not in source or len(citation.quote) < min(12, len(source)):
                errors.append(prefix + 'Evidence quote is not an exact substring of its source')
            if citation.evidence_id not in draft.posts[unit['post_index']].evidence_ids:
                errors.append(prefix + 'Reviewer citation missing from writer evidence_ids')
    return list(dict.fromkeys(errors))
