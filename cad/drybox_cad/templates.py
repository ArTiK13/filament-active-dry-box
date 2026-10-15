from pathlib import Path
from html import escape
import ezdxf
from .model import bolt_pattern


def write_template(folder,name,w,h,inner=None,holes=(),note='',circles=()):
    # Both formats in physical millimetres. SVG includes a 100 mm calibration bar.
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w+30}mm" height="{h+56}mm" viewBox="{-w/2-15} {-h/2-28} {w+30} {h+56}">',
         '<style>text{font-family:Arial,sans-serif;font-size:3px} .cut{fill:none;stroke:#ad2727;stroke-width:.2}</style>',
         f'<text x="{-w/2}" y="{-h/2-16}">{escape(name)}</text>',
         f'<text x="{-w/2}" y="{-h/2-10}">mm / print 100% / check the 100 mm bar</text>',
         f'<text x="{-w/2}" y="{-h/2-5}">{escape(note)}</text>']
    doc=ezdxf.new('R2010');doc.units=4;m=doc.modelspace()
    def rect(a,b):
        svg.append(f'<rect class="cut" x="{-a/2}" y="{-b/2}" width="{a}" height="{b}"/>')
        m.add_lwpolyline([(-a/2,-b/2),(a/2,-b/2),(a/2,b/2),(-a/2,b/2)],close=True)
    rect(w,h)
    if inner: rect(*inner)
    for x,y,d in holes:
        svg.append(f'<circle class="cut" cx="{x}" cy="{-y}" r="{d/2}"/>')
        m.add_circle((x,y),d/2)
    for d in circles:
        svg.append(f'<circle class="cut" cx="0" cy="0" r="{d/2}"/>');m.add_circle((0,0),d/2)
    y=h/2+12
    svg += [f'<path d="M -50 {y} h 100 m -100 -2 v 4 m 100 -4 v 4" stroke="black" stroke-width=".3"/>',
            f'<text x="-12" y="{y+7}">100 mm</text>','</svg>']
    (folder/f'{name}.svg').write_text('\n'.join(svg))
    doc.saveas(folder/f'{name}.dxf')


def generate(p,folder):
    folder.mkdir(parents=True,exist_ok=True)
    def holes(n): return [(x,y,4.5) for x,y in bolt_pattern(n)]
    for n in (120,80):
        ap=n-8
        write_template(folder,f'flap_seal_{n}',ap+14,ap+14,(ap+1,ap+1),note='silicone 2 mm; assembled compression 0.3 mm')
    write_template(folder,'wall_outer_seal',156,156,(122,122),holes(120),'silicone 3 mm; adjust to measured wall')
    write_template(folder,'wall_inner_seal',156,156,(122,122),holes(120),'silicone 1 mm')
    write_template(folder,'valve_leg_seal',156,156,(156-2*p.wall,156-2*p.wall),note='silicone 1 mm; narrow perimeter, RTV is an alternative')
    write_template(folder,'leg_bridge_seal',156,156,(128,128),[(x,z,4.5) for x in (-70,70) for z in (-62,62)],'silicone 1 mm; two copies')
    write_template(folder,'bridge_centre_seal',p.bridge_depth,156,(p.bridge_depth-28,128),
                   [(y,z,4.5) for y in (-p.bridge_depth/2+8,p.bridge_depth/2-8) for z in (-64,65)],'silicone 1 mm')
    write_template(folder,'exhaust_mount_seal',116,116,(72,72),holes(80),'silicone 1 mm; two copies')
    write_template(folder,'heater_mount_seal',116,116,(72,72),holes(80),'silicone 1 mm; to main leg')
    write_template(folder,'heater_hood_seal',116,116,(116-2*p.wall,116-2*p.wall),note='silicone 1 mm; front perimeter')
    write_template(folder,'journal_seal',16,16,None,note='cut the two circles only; silicone 1 mm',circles=(12,8.1))
    write_template(folder,'bin_cut_and_drill',156,156,(120,120),holes(120),
                   f'inner square: CUT; circles: drill; centres X +/-{p.leg_spacing/2}, Z {p.centre_z}')
    return sorted(str(f) for f in folder.glob('*'))
