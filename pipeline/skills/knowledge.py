"""Shared by research and review: resolve evidence from the same KB snapshot."""
import re

def search_kb(kb, focus):
    if not focus.strip():
        return list(kb)
    words = set(re.findall(r'[a-z0-9]+', focus.lower()))
    # Exact phrase or all requested words; never silently fall back on a miss.
    return [k for k in kb if words <= set(re.findall(
        r'[a-z0-9]+', f'{k.id} {k.name} {k.category}'.lower()))]

def evidence_for(entry):
    evidence = {f'kb:{entry.id}:{field}': getattr(entry, field)
                for field in ('name', 'description', 'root_cause', 'mitigation')}
    evidence.update({f'kb:{entry.id}:fact:{f.id}': f.text for f in entry.facts})
    return evidence

def provenance_for(entry):
    sources = {key: entry.source_url for key in evidence_for(entry)}
    sources.update({f'kb:{entry.id}:fact:{f.id}': f.source_url for f in entry.facts})
    return sources
