"""Audit the current build without replacing its recorded source fingerprints."""
import hashlib
import json
import xml.etree.ElementTree as ET

import ezdxf

from drybox_cad.project import OUTPUT_ROOT, RENDER_NAMES, source_hashes


def audit():
    report_path = OUTPUT_ROOT / 'verification.json'
    report = json.loads(report_path.read_text())
    assert report['status'] in (
        'geometry_and_export_checks_passed', 'passed_geometry_exports_and_visual_review'
    ), 'Build did not finish successfully'
    assert report['source_sha256'] == source_hashes(), 'CAD sources changed; rebuild first'

    template_dir = OUTPUT_ROOT / 'exports' / 'templates'
    dxfs = sorted(template_dir.glob('*.dxf'))
    svgs = sorted(template_dir.glob('*.svg'))
    assert len(dxfs) == len(svgs) == 12, 'Expected 12 complete DXF/SVG template pairs'
    assert {p.stem for p in dxfs} == {p.stem for p in svgs}
    checks = []
    for path in dxfs:
        doc = ezdxf.readfile(path)
        assert doc.units == 4, (path, 'DXF must declare millimetres')
        assert len(doc.modelspace()) > 0
        checks.append({'path': str(path.relative_to(OUTPUT_ROOT)),
                       'roundtrip': True, 'units': 'mm'})
    for path in svgs:
        attributes = ET.parse(path).getroot().attrib
        assert attributes['width'].endswith('mm') and attributes['height'].endswith('mm')
        assert '100 mm' in path.read_text()

    assert len(report['parts']) == report['unique_print_designs'] == 29
    for part in report['parts']:
        for key in ('step', 'stl'):
            assert (OUTPUT_ROOT / part[key]).is_file(), part[key]
    for state in report['states'].values():
        assert (OUTPUT_ROOT / state['assembly']['path']).is_file()
    renders = report['renders']
    if renders:
        assert {r['path'] for r in renders} == {f'renders/{n}' for n in RENDER_NAMES}
        for entry in renders:
            path = OUTPUT_ROOT / entry['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], path
    if report['status'] == 'passed_geometry_exports_and_visual_review':
        assert renders and all(r['native_view_image_inspected'] for r in renders)

    report['template_checks'] = checks
    report_path.write_text(json.dumps(report, indent=2))
    print('PASS: source fingerprints, 29 part exports, assemblies, 12 template pairs and render hashes')


if __name__ == '__main__':
    audit()
