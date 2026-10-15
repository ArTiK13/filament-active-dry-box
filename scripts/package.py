#!/usr/bin/env python3
"""Package source and current verified CAD output; exclude caches and stale renders."""
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cad'))

from drybox_cad.project import OUTPUT_ROOT
from verify_delivery import audit


def main():
    audit()
    report = json.loads((OUTPUT_ROOT / 'verification.json').read_text())
    files = [ROOT / name for name in ('.gitignore', '.gitattributes', 'Makefile', 'README.md')]
    for directory in ('cad', 'docs', 'electronics', 'firmware', 'scripts'):
        files.extend(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix in ('.py', '.md', '.json', '.txt', '.png'))
    for part in report['parts']:
        files.extend(OUTPUT_ROOT / part[key] for key in ('step', 'stl'))
    files.extend(OUTPUT_ROOT / state['assembly']['path'] for state in report['states'].values())
    files.extend(OUTPUT_ROOT / name for name in report['templates'])
    files.extend(OUTPUT_ROOT / entry['path'] for entry in report['renders'])
    files.extend(OUTPUT_ROOT / name for name in
                 ('verification.json', 'print_manifest.json', 'parameters_resolved.json'))
    files = sorted(set(files))
    manifest = {str(p.relative_to(ROOT)): {
        'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()
    } for p in files}
    manifest_path = OUTPUT_ROOT / 'artifact_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2))
    archive_path = ROOT / 'dist' / 'filament-active-dry-box-v1.zip'
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path, 'w', compression=ZIP_DEFLATED) as archive:
        for path in [*files, manifest_path]:
            archive.write(path, str(path.relative_to(ROOT)))
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None, 'ZIP CRC failure'
        assert len(archive.namelist()) == len(manifest) + 1
        for name, entry in manifest.items():
            data = archive.read(name)
            assert len(data) == entry['bytes']
            assert hashlib.sha256(data).hexdigest() == entry['sha256'], name
    print(f'PASS: {archive_path} ({len(manifest) + 1} files; CRC and SHA-256 verified)')


if __name__ == '__main__':
    main()
