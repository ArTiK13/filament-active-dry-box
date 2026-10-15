"""Fixed-camera views of the exact retention prototypes and installed assemblies."""
from pathlib import Path

from .model import Part, box
from .retention import RetainedValve, variant_assembly
from .render import setup, draw, finish


def render_variant(p, q, kind, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    names = []
    v = setup(f'{kind.upper()} | installed storage mode | prototypes, mm')
    for item in variant_assembly(p, q, kind, 'dry').values():
        draw(v, item)
    v.add_floor('-z', color='#DCE3E8', lighting=False, pad=.18)
    name = 'assembly_dry.png'
    finish(v, out / name, (790, -850, 700), (0, 180, 120), 370)
    names.append(name)

    v = setup(f'{kind.upper()} | 120 mm valves: CLOSED and OPEN | mm')
    for index, angle in enumerate((0, p.open_angle)):
        valve = RetainedValve(120, p, kind, q)
        for key, (s, t, m, c) in valve.components(angle).items():
            draw(v, Part(key, s.translate((index * 290, 0, 0)), t, m, c, key))
    name = 'valve_states.png'
    finish(v, out / name, (780, -550, 410), (170, 25, 55), 240)
    names.append(name)

    title = ('SPRING | end stops and over-centre action | green = spring OD envelope'
             if kind == 'spring' else 'MAGNETIC | two end catches, one steel keeper | two 6x3 discs per catch')
    v = setup(title)
    valve = RetainedValve(120, p, kind, q)
    hidden = {'frame', 'flap', 'flap_seal', 'journal_seal', 'hinge_pin',
              'servo_envelope', 'stock_horn_envelope', 'slotted_driver', 'drive_pin'}
    for index, angle in enumerate((0, p.open_angle)):
        for key, (s, t, m, c) in valve.components(angle).items():
            if key in hidden:
                continue
            # Side view deliberately removes servo/input disc to expose the retainer.
            if key == 'coaxial_mount':
                s = s.intersect(box(120, 80, 100, (valve.d + 10, valve.hy - 40, -5)))
            opacity = .22 if key == 'coaxial_mount' else 1
            draw(v, Part(key, s.translate((0, index * 125, 0)), t, m, c, key), opacity=opacity)
    name = 'latch_detail.png'
    finish(v, out / name, (620, valve.hy + 65, valve.hz + 38),
           (valve.d + 29, valve.hy + 62, valve.hz + 15), None)
    names.append(name)

    v = setup(f'{kind.upper()} | lost-motion coupling | input disc + stock horn exploded 32 mm')
    for key, (s, t, m, c) in valve.components(0).items():
        if key in ('flap', 'frame', 'flap_seal', 'journal_seal', 'hinge_pin', 'servo_envelope'):
            continue
        if key == 'coaxial_mount':
            s = s.intersect(box(120, 80, 100, (valve.d + 10, valve.hy - 40, -5)))
        if key in ('slotted_driver', 'stock_horn_envelope'):
            s = s.translate((32, 0, 0))
        draw(v, Part(key, s, t, m, c, key), opacity=.16 if key == 'coaxial_mount' else 1)
    name = 'drive_exploded.png'
    finish(v, out / name, (valve.d + 240, valve.hy - 150, valve.hz + 100),
           (valve.d + 45, valve.hy, valve.hz + 16), None)
    names.append(name)
    return names
