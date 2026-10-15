#!/usr/bin/env python3
"""Single rebuild command: geometry, collision/travel, exports, templates, renders and report."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/filament-mpl')
from pathlib import Path
from dataclasses import asdict,replace
from collections import Counter
import argparse,json,sys,math,time,hashlib,platform,importlib.metadata
import cadquery as cq
import numpy as np
import pyvista as pv
from drybox_cad.parameters import Parameters
from drybox_cad.model import *
from drybox_cad.templates import generate

from drybox_cad.project import OUTPUT_ROOT, PARAMETERS_FILE, source_hashes

ROOT=OUTPUT_ROOT


def bounds(s):
    b=s.BoundingBox()
    return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]


def dims(s):
    b=s.BoundingBox();return [b.xlen,b.ylen,b.zlen]


def ok(s):
    assert s.isValid(),'invalid BRep'
    assert len(s.Solids())==1,f'expected one solid, got {len(s.Solids())}'
    assert s.Volume()>0


def overlaps(parts):
    vals=[v for v in parts.values() if v.kind=='print'];issues=[];candidates=0
    for i,a in enumerate(vals):
        ba=bounds(a.shape)
        for b in vals[i+1:]:
            bb=bounds(b.shape)
            if any(min(ba[k+3],bb[k+3])-max(ba[k],bb[k])<1e-6 for k in range(3)): continue
            candidates+=1;vol=a.shape.intersect(b.shape).Volume()
            if vol>1e-3: issues.append([a.name,b.name,vol])
    assert not issues,issues
    return {'printed_pairs_tested':len(vals)*(len(vals)-1)//2,'exact_intersections_after_bounds_filter':candidates,'unintended_overlaps':0}


def canonical(p,parts):
    unique={}
    for a in parts.values():
        if a.kind=='print' and a.design not in unique: unique[a.design]=a.shape
    for n in (80,120):
        for key,(s,kind,*_) in Valve(n,p).components(0).items():
            if kind=='print':
                # Make plate-like lever/link broad faces horizontal for printing.
                if key in ('crank','horn_adapter','link'): s=s.rotate((0,0,0),(0,1,0),90)
                unique[f'valve{n}_{key}']=s
    for name in list(unique):
        if name.startswith('leg_lid') or name.startswith('bridge_lid'):
            unique[name]=unique[name].rotate((0,0,0),(1,0,0),180)
        if name=='bin_backing':
            unique[name]=bin_backing(p)
        if name=='heater_fan_adapter': unique[name]=fan_adapter80(p)
        if name=='heater_hood_lid': unique[name]=heater_hood_lid(p).rotate((0,0,0),(0,1,0),90)
    # Tolerance coupon with three journal fits, pin fits and hex fits.
    c=box(100,55,8)
    tools=[]
    for x,d in zip((18,50,82),(8.3,8.45,8.6)): tools.append(cyl(d/2,10,(x,15,-1)))
    for x,d in zip((18,50,82),(3.1,3.3,3.5)): tools.append(cyl(d/2,10,(x,30,-1)))
    for x,af in zip((18,50,82),(6.15,6.25,6.4)): tools.append(hexprism(af,10,(x,44,-1),'Z'))
    unique['fit_coupon']=cut(c,tools)
    journal=fuse(cyl(7,3),[cyl(4,20,(0,0,3)),hexprism(6,6,(0,0,23),'Z')])
    unique['test_journal']=journal.cut(cyl(1.25,14,(0,0,16)))
    for name,s in unique.items():
        b=s.BoundingBox();unique[name]=s.translate((-b.xmin,-b.ymin,-b.zmin))
    return unique


def export_part(name,s,p):
    ok(s);base=ROOT/'exports'/'parts'/name
    assert max(dims(s))<=p.print_limit+1e-6,(name,dims(s))
    cq.exporters.export(s,str(base)+'.step')
    back=cq.importers.importStep(str(base)+'.step').val();ok(back)
    assert np.allclose(bounds(s),bounds(back),atol=1e-5)
    assert abs(back.Volume()/s.Volume()-1)<1e-7
    cq.exporters.export(s,str(base)+'.stl',tolerance=p.mesh_linear,angularTolerance=p.mesh_angular)
    mesh=pv.read(str(base)+'.stl').clean()
    assert mesh.n_points and mesh.n_cells
    assert mesh.n_open_edges==0,(name,mesh.n_open_edges)
    assert np.allclose(np.array(mesh.bounds)[[0,2,4,1,3,5]],bounds(s),atol=p.mesh_linear*2)
    error=abs(abs(mesh.volume)/s.Volume()-1)
    assert error<.015,(name,'mesh volume discrepancy',error)
    return {'name':name,'dimensions_mm':dims(s),'volume_mm3':s.Volume(),'brep_valid':True,
            'step_roundtrip':True,'stl_watertight':True,'stl_volume_error_relative':error,
            'step':str(base.relative_to(ROOT))+'.step','stl':str(base.relative_to(ROOT))+'.stl'}


def export_assembly(parts,name):
    a=cq.Assembly(name=name)
    for item in parts.values(): a.add(item.shape,name=item.name,color=cq.Color(item.color))
    path=ROOT/'exports'/'assemblies'/f'{name}.step'
    a.export(str(path),unit="MM")
    back=cq.importers.importStep(str(path)).val()
    assert back.isValid()
    expected=sum(len(v.shape.Solids()) for v in parts.values())
    assert len(back.Solids())==expected,(name,len(back.Solids()),expected)
    assert np.allclose(bounds(back),bounds(a.toCompound()),atol=1e-5)
    # STEP text preserves product names in assembly, independently of flat reimport.
    raw=path.read_text(errors='replace')
    assert all(v.name in raw for v in parts.values())
    return {'path':str(path.relative_to(ROOT)),'body_count':expected,'roundtrip':True,'names_preserved':True}


def motion_tests(p):
    results=[]
    for n in (80,120):
        v=Valve(n,p)
        for angle in (0,20,40,60,p.open_angle):
            c=v.components(angle)
            items={k:Part(k,s,kind,mat,col,k) for k,(s,kind,mat,col) in c.items()}
            for a in items.values():ok(a.shape)
            overlaps(items)
            a=math.radians(angle)
            pins=[(v.hy-p.crank_radius*math.cos(a),v.hz+p.crank_radius*math.sin(a)),
                  (v.hy-p.crank_radius*math.cos(a),v.servo_z+p.crank_radius*math.sin(a))]
            assert abs(math.dist(*pins)-p.rod_centres)<1e-9
        results.append({'fan_class_mm':n,'angles_deg':[0,20,40,60,p.open_angle],
                        'no_printed_interference':True,'linkage_closure_error_mm':0,
                        'journal_diametral_clearance_mm':p.journal_clearance})
    # System motion against all printed housings, all modes; interpolate driven valves in each group.
    base=make_parts(p,'cooling')
    for prefix,n,place in [('box_valve_left_',120,lambda s:valve_to_leg(s,-p.leg_spacing/2,p)),
                           ('box_valve_right_',120,lambda s:valve_to_leg(s,p.leg_spacing/2,p)),
                           ('heater_valve_',80,lambda s:valve_to_heater(s,p))]:
        v=Valve(n,p)
        for angle in (0,20,40,60,p.open_angle):
            moving=place(v.components(angle)['flap'][0]);b=bounds(moving)
            for name in ('leg_left','leg_right','leg_lid_left','leg_lid_right','bridge_left','bridge_right',
                         'bridge_lid_left','bridge_lid_right','cassette_left','cassette_right','heater_hood','heater_hood_lid'):
                target=base[name].shape;t=bounds(target)
                if any(min(b[k+3],t[k+3])-max(b[k],t[k])<1e-6 for k in range(3)):continue
                assert moving.intersect(target).Volume()<1e-3,(prefix,angle,name)
    return results


def parameter_tests(p):
    results=[]
    variants=[('small',replace(p,leg_spacing=260,wall=2.8,bridge_depth=148,leg_end_y=207,cassette_height=35,open_angle=78)),
              ('large',replace(p,leg_spacing=300,wall=4,bridge_depth=170,leg_end_y=232,open_angle=83))]
    for label,q in variants:
        q.validate();parts=make_parts(q,'dry')
        for item in parts.values():ok(item.shape)
        overlaps(parts)
        for n,s in canonical(q,parts).items():
            assert max(dims(s))<=q.print_limit+1e-6,(label,n,dims(s))
        results.append({'case':label,'valid_brep':True,'collision_free':True,'print_envelope':True})
    invalid=[replace(p,wall=1),replace(p,leg_spacing=190),replace(p,cassette_height=80),
             replace(p,open_angle=90),replace(p,duct_size=150),replace(p,bridge_depth=300)]
    for q in invalid:
        try:q.validate()
        except ValueError:pass
        else:raise AssertionError('invalid parameter case accepted')
    return {'valid_cases':results,'invalid_cases_rejected':len(invalid)}


def run():
    ap=argparse.ArgumentParser();ap.add_argument('--no-render',action='store_true');args=ap.parse_args()
    p=Parameters(**json.loads(PARAMETERS_FILE.read_text()));p.validate()
    for folder in ('exports/parts','exports/assemblies','exports/templates','renders'): (ROOT/folder).mkdir(parents=True,exist_ok=True)
    report={'status':'building','units':'mm','python':sys.version,'platform':platform.platform(),
            'versions':{k:importlib.metadata.version(k) for k in ('cadquery','cadquery-ocp','pyvista','numpy','ezdxf')},
            'source_sha256':source_hashes(),'parameters':asdict(p),'manufacturing_print_limit_provisional_mm':p.print_limit,
            'physical_validation':'not performed; photo dimensions and component fit provisional'}
    print('Building cooling state',flush=True);parts=make_parts(p,'cooling')
    for a in parts.values():ok(a.shape)
    assert len(parts)==94,len(parts)
    report['part_instances']=len(parts);report['print_instances']=sum(a.kind=='print' for a in parts.values())
    report['states']={}
    for mode in ('dry','regenerate','cooling'):
        print('Checking state',mode,flush=True);ps=make_parts(p,mode)
        report['states'][mode]=overlaps(ps)
        report['states'][mode]['bounds_mm']=bounds(cq.Compound.makeCompound([a.shape for a in ps.values()]))
        report['states'][mode]['assembly']=export_assembly(ps,mode)
    print('Travel checks',flush=True);report['motion']=motion_tests(p)
    print('Boundary cases',flush=True);report['parameter_tests']=parameter_tests(p)
    report['parts']=[];unique=canonical(p,parts)
    for name,s in unique.items():
        print('Export',name,flush=True);report['parts'].append(export_part(name,s,p))
    report['unique_print_designs']=len(unique)
    report['templates']=[str(Path(f).relative_to(ROOT)) for f in generate(p,ROOT/'exports'/'templates')]
    counts=Counter(a.design for a in parts.values() if a.kind=='print')
    (ROOT/'print_manifest.json').write_text(json.dumps(dict(counts,fit_coupon=1,test_journal=1),indent=2))
    (ROOT/'parameters_resolved.json').write_text(json.dumps(asdict(p),indent=2))
    report['intent']={'main_duct_envelope_mm':[p.width,p.back_y-p.leg_start_y,p.duct_size],
                      'wall_port_centres_XZ_mm':[[-p.leg_spacing/2,p.centre_z],[p.leg_spacing/2,p.centre_z]],
                      'wall_square_cut_mm':120,'cassette_height_mm':p.cassette_height,
                      'air_gap_above_basket_mm':p.lid_z-p.cassette_floor_z-p.cassette_height,
                      'heater_flap_opens_into_external_hood':True,
                      'four_supports_rest_at_Z0':True,'closed_seal_squish_mm':p.gasket_free-p.gasket_compressed}
    if not args.no_render:
        print('Rendering',flush=True);from drybox_cad.render import render_all
        render_all(p,ROOT/'renders')
    report['renders']=[{'path':str(f.relative_to(ROOT)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
                       'native_view_image_inspected':False} for f in sorted((ROOT/'renders').glob('*.png')) if not args.no_render and f.name!='smoke.png']
    report['status']='geometry_and_export_checks_passed'
    (ROOT/'verification.json').write_text(json.dumps(report,indent=2))
    print('PASS: geometry, travel, boundary cases, STEP and watertight STL',flush=True)

if __name__=='__main__':run()
