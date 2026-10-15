#!/usr/bin/env python3
"""Build both valve retention prototypes without changing the baseline CAD model."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/filament-mpl')
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
from zipfile import ZIP_DEFLATED, ZipFile

import cadquery as cq
import numpy as np

import build as baseline
from drybox_cad.parameters import Parameters
from drybox_cad.project import REPO_ROOT, PARAMETERS_FILE, source_hashes
from drybox_cad.model import Part, Valve, rotate_x, reference_bin, valve_to_leg, valve_to_outlet, valve_to_heater
from drybox_cad.retention import RetentionParameters, RetainedValve, variant_assembly

ROOT = REPO_ROOT / 'build' / 'cad-variants'


def load(kind):
    data = json.loads((REPO_ROOT / 'cad' / 'variants' / f'{kind}.json').read_text())
    assert data['kind'] == kind
    return RetentionParameters(**data['parameters'])


def fingerprints():
    hashes = source_hashes()
    for f in sorted((REPO_ROOT / 'cad' / 'variants').glob('*.json')):
        hashes[str(f.relative_to(REPO_ROOT))] = hashlib.sha256(f.read_bytes()).hexdigest()
    return hashes


def local_parts(v, angle, input_angle=None):
    return {k: Part(k, s, t, m, c, f'valve{v.n}_{k}')
            for k, (s, t, m, c) in v.components(angle, input_angle).items()}


def clearance(a, b, limit=1e-3):
    aa, bb = baseline.bounds(a), baseline.bounds(b)
    if any(min(aa[k + 3], bb[k + 3]) - max(aa[k], bb[k]) < 1e-6 for k in range(3)):
        return
    volume = a.intersect(b).Volume()
    assert volume < limit, f'intersection {volume:.6g} mm3'


def hardware_checks(parts):
    # Threaded engagement and stock servo internals are deliberately not simulated.
    allowed = {('drive_pin', 'latch_rotor')}
    count = 0
    for a in parts.values():
        if a.kind != 'purchased_reference':
            continue
        for b in parts.values():
            if b.kind != 'print':
                continue
            if (a.name, b.name) in allowed or (a.name.endswith('stop_screw') and b.name == 'coaxial_mount'):
                continue
            try:
                clearance(a.shape, b.shape)
            except AssertionError as e:
                raise AssertionError((a.name, b.name, str(e)))
            count += 1
    if 'extension_spring_envelope' in parts:
        for name in ('drive_pin', 'rotor_retainer', 'servo_envelope'):
            try:
                clearance(parts['extension_spring_envelope'].shape, parts[name].shape)
            except AssertionError as e:
                raise AssertionError(('spring envelope', name, str(e)))
    return count


def mechanics(v):
    p, q = v.p, v.q
    parts = local_parts(v, 0)
    density = q.polymer_density_g_cm3
    moving = ['flap', 'latch_rotor', 'drive_pin']
    if v.kind == 'magnetic':
        moving += ['steel_keeper', 'keeper_cap']
    masses = []
    for name in moving:
        item = parts[name]
        rho = 7.85 if name in ('steel_keeper', 'drive_pin') else density
        masses.append((item.shape.Volume() * rho / 1e6, np.array(item.shape.Center().toTuple())))
    mass = sum(m for m, _ in masses)
    centre = sum(m * c for m, c in masses) / mass - np.array(v.pivot)
    data = {'mass_basis': 'solid polymer at assumed density, plus smooth steel envelopes; not measured',
            'polymer_density_g_cm3': density, 'moving_mass_estimate_g': mass * 1000,
            'drive_contact_angle_deg': v.engagement_angle,
            'servo_command_relative_to_closed_deg': {
                'close_then_park': [-v.engagement_angle, 0],
                'open_then_park': [p.open_angle + v.engagement_angle, p.open_angle]},
            'orientations': {}}
    for label, gravity in [('bin', np.array([0, -9.80665, 0])),
                           ('exhaust', np.array([0, 0, -9.80665])),
                           ('heater', np.array([-9.80665, 0, 0]))]:
        rows = []
        for angle in np.linspace(0, p.open_angle, 165):
            a = math.radians(-angle)
            c = centre.copy()
            c[1:] = [centre[1] * math.cos(a) - centre[2] * math.sin(a),
                     centre[1] * math.sin(a) + centre[2] * math.cos(a)]
            gt = -np.cross(c, mass * gravity)[0]  # opening-positive N mm
            if v.kind == 'spring':
                torque, length, force = v.spring_torque(angle)
                rows.append({'angle_deg': float(angle), 'spring_n_mm': torque, 'gravity_n_mm': float(gt),
                             'net_n_mm': float(torque + gt), 'eye_length_mm': length, 'spring_force_n': force})
            else:
                rows.append({'angle_deg': float(angle), 'gravity_n_mm': float(gt)})
        item = {'gravity_peak_n_mm': max(abs(r['gravity_n_mm']) for r in rows)}
        if v.kind == 'spring':
            assert rows[0]['net_n_mm'] < 0 and rows[-1]['net_n_mm'] > 0, (v.n, label, rows[0], rows[-1])
            assert min(r['eye_length_mm'] for r in rows) > q.spring_free_eye_length
            peak = max(abs(r['net_n_mm']) for r in rows) / 1000
            item.update({'closed_net_toward_stop_n_mm': -rows[0]['net_n_mm'],
                         'open_net_toward_stop_n_mm': rows[-1]['net_n_mm'],
                         'ideal_servo_peak_nm_without_seal_friction': peak,
                         'ideal_servo_peak_kgf_cm': peak / .0980665,
                         'eye_length_range_mm': [min(r['eye_length_mm'] for r in rows), max(r['eye_length_mm'] for r in rows)],
                         'force_range_n': [min(r['spring_force_n'] for r in rows), max(r['spring_force_n'] for r in rows)]})
        else:
            assumed = 2 * q.assumed_force_per_magnet_n * q.magnet_radius
            item.update({'force_assumption_per_magnet_n_NOT_VENDOR_SPEC': q.assumed_force_per_magnet_n,
                         'nominal_attraction_moment_n_mm': assumed,
                         'minimum_total_open_catch_force_n_under_gravity_only': max(0, -rows[-1]['gravity_n_mm']) / q.magnet_radius,
                         'conservative_release_torque_nm_without_seal_friction': (assumed + item['gravity_peak_n_mm']) / 1000,
                         'actual_magnet_force_and_capture_range': 'must measure at actual gap; no field simulation performed'})
        data['orientations'][label] = item
    return data


def check_valve(v):
    angles = sorted(set([*range(0, int(v.p.open_angle) + 1, 5), v.q.spring_dead_angle,
                         v.p.open_angle / 2, v.p.open_angle]))
    count = 0
    for angle in angles:
        ps = local_parts(v, angle)
        for item in ps.values():
            baseline.ok(item.shape)
        baseline.overlaps(ps)
        count += hardware_checks(ps)
    for angle in (0, v.p.open_angle):
        for delta in (-v.engagement_angle, -3, 0, 3, v.engagement_angle):
            ps = local_parts(v, angle, angle + delta)
            baseline.overlaps(ps)
            count += hardware_checks(ps)
        # Both stops really contact the output lug, rather than relying on servo position.
        label = 'closed' if angle == 0 else 'open'
        ps = local_parts(v, angle)
        assert ps['latch_rotor'].shape.distance(ps[f'{label}_stop_sleeve'].shape) < 1e-6
        assert ps['drive_pin'].shape.distance(ps['slotted_driver'].shape) > .1
    if v.kind == 'spring':
        t0, l0, _ = v.spring_torque(v.q.spring_dead_angle)
        assert abs(t0) < 1e-9
        assert l0 > v.spring_torque(0)[1] and l0 > v.spring_torque(v.p.open_angle)[1]
    return {'angles_deg': angles, 'print_and_hardware_clearance': True,
            'hardware_pairs_checked': count, 'hard_stop_contacts': True,
            'parked_servo_unloaded_pin_clearance_gt_mm': .1,
            'lost_motion_extremes_tested_deg': [-v.engagement_angle, v.engagement_angle],
            'mechanics': mechanics(v)}


def integration_sweep(p, q, kind):
    # All five placements are checked against every non-valve component, including the reference bin.
    base = variant_assembly(p, q, kind, 'cooling')
    prefixes = ('box_valve_left_', 'box_valve_right_', 'exhaust_left_', 'exhaust_right_', 'heater_valve_')
    housing = {n: x for n, x in base.items() if not n.startswith(prefixes) and x.kind == 'print'}
    housing['reference_bin'] = Part('reference_bin', reference_bin(p), 'print', '', '', '')
    placements = [
        (120, lambda s: valve_to_leg(s, -p.leg_spacing / 2, p)),
        (120, lambda s: valve_to_leg(s, p.leg_spacing / 2, p)),
        (80, lambda s: valve_to_outlet(s, -p.leg_spacing / 2, p)),
        (80, lambda s: valve_to_outlet(s, p.leg_spacing / 2, p)),
        (80, lambda s: valve_to_heater(s, p)),
    ]
    for index, (n, place) in enumerate(placements):
        v = RetainedValve(n, p, kind, q)
        for angle in (0, 10, 25, 41, 60, p.open_angle):
            ps = local_parts(v, angle)
            for name, item in ps.items():
                if item.kind == 'seal' or name in ('frame', 'hinge_pin'):
                    continue
                s = place(item.shape)
                for other, stationary in housing.items():
                    try:
                        clearance(s, stationary.shape)
                    except AssertionError as e:
                        raise AssertionError((kind, index, angle, name, other, str(e)))
    return {'valve_placements': 5, 'angles_deg': [0, 10, 25, 41, 60, p.open_angle],
            'all_printed_housings_and_reference_bin_clear': True}


def canonical(p, q, kind, full):
    unique = baseline.canonical(p, full)
    unique = {n: s for n, s in unique.items() if not n.startswith('valve')}
    for n in (80, 120):
        v = RetainedValve(n, p, kind, q)
        for name, item in local_parts(v, 0).items():
            if item.kind != 'print':
                continue
            s = item.shape
            if 'magnet_holder' in name or 'magnet_cap' in name:
                phi = v.phi - (p.open_angle if name.startswith('open_') else 0)
                s = rotate_x(s, -phi, v.pivot)
                if name.startswith('open_'):
                    s = s.mirror('XY', (0, 0, v.hz))
            elif name not in ('frame', 'flap'):
                s = s.rotate((0, 0, 0), (0, 1, 0), -90)
            b = s.BoundingBox()
            unique[f'valve{n}_{name}'] = s.translate((-b.xmin, -b.ymin, -b.zmin))
    return unique


def boundary_tests(p, q, kind):
    cases = []
    for label, pp, qq in [
        ('small', replace(p, leg_spacing=260, wall=2.8, bridge_depth=148, leg_end_y=207,
                          cassette_height=35, open_angle=78), replace(q, lost_motion_deg=6, magnet_gap=1.2, spring_radius=9,
                          spring_anchor_radius=33, spring_dead_angle=20, spring_free_eye_length=28,
                          spring_outer_diameter=3)),
        ('large', replace(p, leg_spacing=300, wall=4, bridge_depth=170, leg_end_y=232,
                          open_angle=83), replace(q, lost_motion_deg=9, magnet_gap=3, spring_anchor_radius=36,
                                                          spring_dead_angle=30, spring_free_eye_length=33))]:
        pp.validate(); qq.validate(pp)
        for n in (80, 120):
            v = RetainedValve(n, pp, kind, qq)
            for a in (0, pp.open_angle / 2, pp.open_angle):
                ps = local_parts(v, a)
                for item in ps.values():
                    baseline.ok(item.shape)
                baseline.overlaps(ps)
                hardware_checks(ps)
        full = variant_assembly(pp, qq, kind)
        baseline.overlaps(full)
        cases.append({'case': label, 'brep_valid': True, 'no_printed_collisions': True})
    for bad in (replace(q, lost_motion_deg=0), replace(q, magnet_gap=.5),
                replace(q, spring_dead_angle=90), replace(q, drive_pin_diameter=2)):
        try:
            bad.validate(p)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid mechanism parameters accepted')
    return {'valid': cases, 'invalid_cases_rejected': 4}


def package(kind):
    root = ROOT / kind
    report = json.loads((root / 'verification.json').read_text())
    assert report['source_sha256'] == fingerprints(), 'Sources changed; rebuild variants'
    assert report['status'] in ('geometry_and_export_checks_passed', 'passed_geometry_exports_and_visual_review')
    for entry in report['renders']:
        assert hashlib.sha256((root / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    files = [f for folder in ('cad', 'docs', 'electronics', 'firmware', 'scripts')
             for f in (REPO_ROOT / folder).rglob('*') if f.is_file()
             and '__pycache__' not in f.parts and f.suffix in ('.py', '.md', '.json', '.txt', '.png')]
    files += [REPO_ROOT / n for n in ('README.md', 'Makefile', '.gitignore', '.gitattributes')]
    files += [p for p in root.rglob('*') if p.is_file() and p.suffix in ('.step', '.stl', '.svg', '.dxf', '.json')
              and p.name != 'artifact_manifest.json']
    files += [root / r['path'] for r in report['renders']]
    manifest = {str(f.relative_to(REPO_ROOT)): {'bytes': f.stat().st_size,
                'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(set(files))}
    mp = root / 'artifact_manifest.json'
    mp.write_text(json.dumps(manifest, indent=2))
    path = REPO_ROOT / 'dist' / f'filament-dry-box-{kind}-prototype.zip'
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', compression=ZIP_DEFLATED) as z:
        for f in [*sorted(set(files)), mp]:
            z.write(f, str(f.relative_to(REPO_ROOT)))
    with ZipFile(path) as z:
        assert z.testzip() is None
        for name, record in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == record['sha256']
    print('PACKAGED', path, flush=True)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('spring', 'magnetic', 'both'), default='both')
    parser.add_argument('--no-render', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    parser.add_argument('--package-only', action='store_true')
    args = parser.parse_args()
    kinds = ('spring', 'magnetic') if args.kind == 'both' else (args.kind,)
    p = Parameters(**json.loads(PARAMETERS_FILE.read_text()))
    p.validate()
    for kind in kinds:
        q = load(kind); q.validate(p)
        root = ROOT / kind
        if args.package_only:
            package(kind); continue
        if args.render_only:
            report = json.loads((root / 'verification.json').read_text())
            assert report['source_sha256'] == fingerprints(), 'Sources changed; rebuild variants'
        else:
            print('BUILD', kind, flush=True)
            for folder in ('exports/parts', 'exports/assemblies', 'exports/templates', 'renders'):
                (root / folder).mkdir(parents=True, exist_ok=True)
            baseline.ROOT = root
            report = {'status': 'building', 'variant': kind, 'units': 'mm', 'platform': platform.platform(),
                      'versions': {k: importlib.metadata.version(k) for k in ('cadquery', 'pyvista', 'numpy')},
                      'source_sha256': fingerprints(), 'baseline_parameters': asdict(p), 'retention_parameters': asdict(q),
                      'physical_validation': 'not performed; spring law and magnetic force are design assumptions', 'valves': {}}
            (root / 'verification.json').write_text(json.dumps(report, indent=2))
            for n in (80, 120):
                print('MOTION', kind, n, flush=True)
                v = RetainedValve(n, p, kind, q)
                report['valves'][str(n)] = check_valve(v)
                for label, angle in (('closed', 0), ('open', p.open_angle)):
                    baseline.export_assembly(local_parts(v, angle), f'valve{n}_{label}')
            print('INTEGRATION', kind, flush=True)
            report['integration_sweep'] = integration_sweep(p, q, kind)
            report['states'] = {}
            for state in ('dry', 'regenerate', 'cooling'):
                ps = variant_assembly(p, q, kind, state)
                result = baseline.overlaps(ps)
                result['bounds_mm'] = baseline.bounds(cq.Compound.makeCompound([x.shape for x in ps.values()]))
                result['assembly'] = baseline.export_assembly(ps, state)
                report['states'][state] = result
            print('BOUNDARIES', kind, flush=True)
            report['parameter_tests'] = boundary_tests(p, q, kind)
            ps = variant_assembly(p, q, kind)
            report['part_instances'] = len(ps)
            report['print_instances'] = sum(x.kind == 'print' for x in ps.values())
            report['parts'] = []
            for name, s in canonical(p, q, kind, ps).items():
                print('EXPORT', kind, name, flush=True)
                report['parts'].append(baseline.export_part(name, s, p))
            report['unique_print_designs'] = len(report['parts'])
            report['templates'] = [str(Path(f).relative_to(root)) for f in baseline.generate(p, root / 'exports/templates')]
            counts = Counter(x.design for x in ps.values() if x.kind == 'print')
            (root / 'print_manifest.json').write_text(json.dumps(dict(counts, fit_coupon=1, test_journal=1), indent=2))
            (root / 'parameters_resolved.json').write_text(json.dumps({'baseline': asdict(p), 'retention': asdict(q)}, indent=2))
            report['renders'] = []
            report['status'] = 'geometry_and_export_checks_passed'
            (root / 'verification.json').write_text(json.dumps(report, indent=2))
        if not args.no_render:
            from drybox_cad.render_variants import render_variant
            print('RENDER', kind, flush=True)
            report['renders'] = []
            report['status'] = 'geometry_and_export_checks_passed'
            (root / 'verification.json').write_text(json.dumps(report, indent=2))
            names = render_variant(p, q, kind, root / 'renders')
            report['renders'] = [{'path': f'renders/{name}', 'sha256': hashlib.sha256((root / 'renders' / name).read_bytes()).hexdigest(),
                                  'native_view_image_inspected': False} for name in names]
            report['status'] = 'geometry_and_export_checks_passed'
            (root / 'verification.json').write_text(json.dumps(report, indent=2))
        print('PASS', kind, flush=True)


if __name__ == '__main__':
    run()
