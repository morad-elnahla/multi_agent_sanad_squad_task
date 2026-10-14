"""Hard quality gates; never delegated to a model."""
import re

def hard_checks(draft, post_type, rules, evidence):
    errors = []
    if not post_type.min_posts <= len(draft.posts) <= post_type.max_posts:
        errors.append(f'Expected {post_type.min_posts}..{post_type.max_posts} posts')
    texts = [p.text for p in draft.posts]
    if len(set(t.casefold().strip() for t in texts)) != len(texts):
        errors.append('Duplicate posts in piece')
    for i, post in enumerate(draft.posts):
        prefix = f'Post {i + 1}: '
        text = post.text
        if not text.strip():
            errors.append(prefix + 'empty text')
        if len(text) > post_type.max_characters:
            errors.append(prefix + 'character limit exceeded')
        if rules['ascii_only'] and not text.isascii():
            errors.append(prefix + 'non-ASCII text is outside supported X policy')
        if any(c in text for c in rules['banned_characters']):
            errors.append(prefix + 'banned punctuation or hashtag')
        if '#' in text:
            errors.append(prefix + 'hashtags are disabled')
        if any(re.search(r'(?<!\w)' + re.escape(w) + r'(?!\w)', text, re.I)
               for w in rules['banned_words']):
            errors.append(prefix + 'banned word or phrase')
        # Catch protocol URLs, bare domains and www forms. Conservatively reject
        # technical dotted identifiers unless explicitly allowlisted as links.
        urls = re.findall(r'https?://[^\s]+|www\.[^\s]+|\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?', text)
        if any(u.rstrip('.,;!?)') not in rules['allowed_links'] + rules.get('allowed_code_identifiers', []) for u in urls):
            errors.append(prefix + 'unapproved link or dotted identifier')
        if any(ref not in evidence for ref in post.evidence_ids):
            errors.append(prefix + 'unknown evidence reference')
        if text.lstrip().startswith(('=', '+', '-', '@')):
            errors.append(prefix + 'unsafe spreadsheet formula prefix')
    return errors

def decide(judgment, draft, errors, rubric):
    scores = judgment.scores.model_dump()
    indexes = [x.post_index for x in judgment.support]
    complete = sorted(indexes) == list(range(len(draft.posts)))
    reasons = list(errors)
    if not judgment.approve:
        reasons.extend(judgment.reasons or ['Reviewer explicitly rejected the piece'])
    if not complete:
        reasons.append('Reviewer did not check every post exactly once')
    reasons.extend(f'Post {s.post_index + 1}: {s.reason}'
                   for s in judgment.support if not s.supported)
    if sum(scores.values()) < rubric['minimum_total'] or min(scores.values()) < rubric['minimum_each']:
        reasons.extend(judgment.reasons or ['Rubric score below threshold'])
    return {'accepted': not reasons, 'scores': scores,
            'total': sum(scores.values()), 'reasons': list(dict.fromkeys(reasons)),
            'hard_errors': errors, 'judgment': judgment.model_dump()}
