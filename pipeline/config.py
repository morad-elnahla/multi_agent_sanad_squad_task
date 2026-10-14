"""Configuration is read once; an immutable snapshot is saved with each run."""
import json
import re
from pathlib import Path
from .models import Knowledge, PostType

class Config:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self._texts = {}
        for pattern in ("*.md", "*.json", "prompts/*.md", "post_types/*/*.md", "post_types/*/*.json", "pipeline/skills/*.md"):
            for path in self.root.glob(pattern):
                self._texts[path.relative_to(self.root).as_posix()] = path.read_text(encoding="utf-8-sig")
        self.brand = self.read('brand-voice.md')
        block = re.search(r'```json\s*(.*?)\s*```', self.brand, re.S)
        if not block:
            raise ValueError('brand-voice.md must contain a JSON rules block')
        self.rules = json.loads(block.group(1))
        for key in ('banned_words', 'banned_characters', 'allowed_links', 'approved_company_stats'):
            if not isinstance(self.rules.get(key), list):
                raise ValueError(f'Brand rule {key} must be a list')
        if self.rules.get('ascii_only') is not True:
            raise ValueError('This release supports conservative ASCII X text only')
        self.kb = [Knowledge.model_validate(x) for x in json.loads(self.read('kb.json'))]
        if len(self.kb) < 15 or len({k.id for k in self.kb}) != len(self.kb):
            raise ValueError('KB needs at least 15 entries with unique IDs')
        self.rubric = json.loads(self.read('rubric.json'))
        if not (0 <= self.rubric.get('minimum_total', -1) <= 20 and 0 <= self.rubric.get('minimum_each', -1) <= 5):
            raise ValueError('Invalid rubric score thresholds')
        for key in ('claim_markers', 'approved_ctas'):
            if not isinstance(self.rules.get(key), list) or not all(isinstance(x, str) for x in self.rules[key]):
                raise ValueError(f'Brand rule {key} must be a list of strings')
        self.visual_style = json.loads(self.read('visual-style.json'))
        self.types = {}
        for path in sorted((self.root / 'post_types').glob('*/type.json')):
            item = PostType.model_validate_json(path.read_text())
            if item.name != path.parent.name:
                raise ValueError('Post type name must match its directory')
            prompt = (path.parent / item.writer).resolve()
            if not prompt.is_relative_to(path.parent.resolve()):
                raise ValueError('Writer prompt must stay inside its post type directory')
            self.types[item.name] = (item, self.read(prompt.relative_to(self.root).as_posix()))

    def read(self, name):
        return self._texts[str(name).replace('\\', '/')]
