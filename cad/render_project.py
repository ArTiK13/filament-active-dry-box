"""Render the current, already verified geometry; does not imply visual approval."""
import hashlib
import json

from drybox_cad.parameters import Parameters
from drybox_cad.project import OUTPUT_ROOT, PARAMETERS_FILE, RENDER_NAMES, source_hashes
from drybox_cad.render import render_all


def main():
    report_path = OUTPUT_ROOT / 'verification.json'
    report = json.loads(report_path.read_text())
    if report['source_sha256'] != source_hashes():
        raise SystemExit('CAD sources changed. Run cad/build.py before rendering.')
    p = Parameters(**json.loads(PARAMETERS_FILE.read_text()))
    p.validate()
    # Invalidate previous visual evidence before a potentially partial render.
    report['renders'] = []
    report['status'] = 'geometry_and_export_checks_passed'
    report_path.write_text(json.dumps(report, indent=2))
    render_all(p, OUTPUT_ROOT / 'renders')
    report['renders'] = [
        {'path': f'renders/{name}',
         'sha256': hashlib.sha256((OUTPUT_ROOT / 'renders' / name).read_bytes()).hexdigest(),
         'native_view_image_inspected': False}
        for name in RENDER_NAMES
    ]
    report_path.write_text(json.dumps(report, indent=2))
    print('Six geometry renders written. Visual inspection is a separate step.', flush=True)


if __name__ == '__main__':
    main()
