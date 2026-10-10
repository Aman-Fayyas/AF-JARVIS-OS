"""Create a verified source ZIP. Exclude builds, caches, keys, DBs and weights."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1] if len(sys.argv) > 1 else root.parent / 'AF-JARVIS-OS-v0.1-alpha-source.zip').resolve()
files = []
for path in sorted(root.rglob('*')):
    if not path.is_file():
        continue
    rel = path.relative_to(root)
    if path.name == 'SOURCE-MANIFEST.json':
        continue
    if any(part in {'__pycache__', '.git', '.venv'} for part in rel.parts):
        continue
    if rel.parts[0] == 'build' and rel != Path('build/README.md'):
        continue
    if path.suffix in {'.pyc', '.key', '.hash', '.sqlite3', '.gguf', '.iso'}:
        continue
    files.append(path)
manifest = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
(root / 'SOURCE-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
files = [p for p in files if p.name != 'SOURCE-MANIFEST.json'] + [root / 'SOURCE-MANIFEST.json']
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        archive.write(path, root.name + '/' + str(path.relative_to(root)))
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    for name, digest in manifest.items():
        assert hashlib.sha256(archive.read(root.name + '/' + name)).hexdigest() == digest
print(json.dumps({'file': str(output), 'files': len(files), 'size_bytes': output.stat().st_size,
                  'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'zip_integrity': 'passed'}))
