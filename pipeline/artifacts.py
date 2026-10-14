"""Versioned JSON artifacts, atomic local writes and scheduler export."""
import csv
import json
import os
from pathlib import Path
from datetime import datetime, timezone

SCHEMA_VERSION = '1.1'

def now():
    return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, kind: str, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps({'schema_version': SCHEMA_VERSION,
                                    'kind': kind, 'data': data}, indent=2,
                                   ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)

def export_csv(path, results):
    """One row per piece; blank lines separate tweets. No universal thread CSV exists."""
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['Post Text', 'Image'])
        writer.writeheader()
        for item in results:
            if item['status'] != 'shipped':
                continue
            writer.writerow({'Post Text': '\n\n'.join(p['text'] for p in item['draft']['posts']),
                             'Image': item['visual_path']})
