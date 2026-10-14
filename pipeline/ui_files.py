"""Local UI file operations; restrict edits and exports to project-owned paths."""
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from .config import Config

EDITABLE = ('brand-voice.md', 'kb.json', 'rubric.json', 'prompts/reviewer.md',
            'prompts/research.md', 'prompts/visual.md',
            'post_types/tech-thread/writer.md', 'post_types/marketing/writer.md')


def save_config(root, name, text):
    if name not in EDITABLE:
        raise ValueError('File is not an editable configuration file')
    root = Path(root).resolve()
    # Validate all files together in a temporary configuration before committing.
    current = Config(root)
    with tempfile.TemporaryDirectory() as folder:
        temp = Path(folder)
        for key, content in current._texts.items():
            path = temp / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text if key == name else content, encoding='utf-8')
        Config(temp)
    target = root / name
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, target)


def load_artifact(folder, filename, default=None):
    path = Path(folder) / filename
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding='utf-8-sig'))['data']


def zip_run(folder):
    folder = Path(folder).resolve()
    allowed = {'.json', '.csv', '.md', '.png', '.jpg', '.webp'}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in allowed and path.resolve().is_relative_to(folder):
                z.write(path, (Path(folder.name) / path.relative_to(folder)).as_posix())
    return buffer.getvalue()
