"""Fixed-camera views of the exact retention prototypes and installed assemblies."""
from pathlib import Path

from .model import Part, box
from .retention import retention_valve, variant_assembly
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
        valve = retention_valve(120, p, kind, q)
        for key, (s, t, m, c) in valve.components(angle).items():
            draw(v, Part(key, s.translate((index * 290, 0, 0)), t, m, c, key))
    name = 'valve_states.png'
    finish(v, out / name, (780, -550, 410), (170, 25, 55), 240)
    names.append(name)

    title = ('SPRING | end stops and over-centre action | green = spring OD envelope'
             if kind == 'spring' else 'MAGNETIC | two end catches, one steel keeper | two 6x3 discs per catch')
    v = setup(title)
    valve = retention_valve(120, p, kind, q)
    hidden = {'frame', 'flap', 'flap_seal', 'journal_seal', 'hinge_pin',
              'servo_envelope', 'stock_horn_envelope', 'slotted_driver', 'drive_pin'}
    for index, angle in enumerate((0, p.open_angle)):
        for key, (s, t, m, c) in valve.components(angle).items():
            if key in hidden or key.startswith('edge_'):
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
        if key in ('flap', 'frame', 'flap_seal', 'journal_seal', 'hinge_pin', 'servo_envelope') or key.startswith('edge_'):
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
    if kind == 'magnetic':
        v = setup('MAGNETIC | storage mode: all five free-edge catches engaged | housings translucent')
        for key, item in variant_assembly(p, q, kind, 'dry').items():
            translucent = key.startswith(('leg_', 'bridge_')) or key in ('heater_hood', 'heater_hood_lid')
            draw(v, item, opacity=.12 if translucent else 1)
        name = 'edge_installed.png'
        finish(v, out / name, (740, -700, 770), (0, 180, 125), None)
        names.append(name)

        v = setup('MAGNETIC | direct free-edge catches | 120 mm closed / open; seat translucent')
        for index, angle in enumerate((0, p.open_angle)):
            for key, (s, t, m, c) in valve.components(angle).items():
                if key not in ('frame', 'flap', 'flap_seal') and not key.startswith('edge_'):
                    continue
                draw(v, Part(key, s.translate((index * 230, 0, 0)), t, m, c, key),
                     opacity=.22 if key in ('frame', 'flap') else 1)
        name = 'edge_catches.png'
        finish(v, out / name, (520, -600, 440), (115, 0, 65), None)
        names.append(name)

        v = setup('MAGNETIC | closed free-edge pair | geometry cutaway; polymer translucent')
        x = valve.edge_xs[1]
        window = box(24, 23, 22, (x - 12, valve.edge_y - 10, -1))
        for key, (s, t, m, c) in valve.components(0).items():
            if key not in ('frame', 'flap', 'flap_seal') and not key.startswith('edge_'):
                continue
            detail = s.intersect(window)
            if not detail.Solids():
                continue
            draw(v, Part(key, detail, t, m, c, key), opacity=.2 if t == 'print' else 1)
        name = 'edge_closed_detail.png'
        finish(v, out / name, (x + 45, valve.edge_y - 65, 42), (x, valve.edge_y, 9), None)
        names.append(name)

        v = setup('MAGNETIC | 80 mm exhaust: CLOSED / OPEN | direct catch only when closed')
        for index, angle in enumerate((0, p.open_angle)):
            exhaust = retention_valve(80, p, kind, q, 'exhaust')
            for key, (s, t, m, c) in exhaust.components(angle).items():
                draw(v, Part(key, s.translate((index * 240, 0, 0)), t, m, c, key))
        name = 'exhaust_states.png'
        finish(v, out / name, (660, -500, 380), (145, 15, 45), None)
        names.append(name)
    return names
