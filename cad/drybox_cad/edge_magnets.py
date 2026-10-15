"""Direct free-edge magnetic catches, in addition to the original hinge catches.

Local XY is the seat, +Z is the opening side. The same moving magnets use
opposite pole faces for closed/open catches. Exhaust valves have no open bracket.
"""
from functools import lru_cache

import cadquery as cq

from .model import box, cyl, cut, fuse, rotate_x, hexprism
from .retention import RetainedValve


class EdgeMagneticValve(RetainedValve):
    def __init__(self, n, p, kind, q, role=None):
        super().__init__(n, p, kind, q)
        self.role = role or ('bin' if n == 120 else 'heater')
        if self.role not in ('bin', 'heater', 'exhaust') or (n == 120) != (self.role == 'bin'):
            raise ValueError('120 mm bin, or 80 mm heater/exhaust required')
        self.edge_y = -self.d - 3
        self.edge_z = 8 + p.gasket_compressed + .5  # bottom face of moving magnet
        self.closed_top = self.edge_z - q.edge_magnet_gap
        self.tab_top = 12 + p.gasket_compressed
        if not 6.3 <= self.closed_top <= 7.6:
            raise ValueError('edge catch requires a 0.4..1.7 mm flush seat cap')

    @property
    def edge_xs(self):
        return (-self.d + 18, self.d - 18)

    @property
    def edge_lever(self):
        return self.hy - self.edge_y

    @property
    def body_y(self):
        return self.p.half - self.p.lid_thickness if self.role == 'bin' else 58 - self.p.wall

    @property
    def body_thickness(self):
        return self.p.lid_thickness if self.role == 'bin' else self.p.wall

    def opened(self, s):
        return rotate_x(s, -self.p.open_angle, self.pivot)

    def cap(self, x, z, thickness, width=16):
        s = box(width, 12, thickness, (x - width / 2, self.edge_y - 6, z))
        holes = [cyl(1.1, thickness + 2, (x + dx, self.edge_y, z - 1)) for dx in (-5.5, 5.5)]
        holes += self.head_seats(x, z + thickness)
        return cut(s, holes)

    def head_seats(self, x, top):
        return [cq.Solid.makeCone(1.1, 2.1, 1, cq.Vector(x + dx, self.edge_y, top - 1))
                for dx in (-5.5, 5.5)]

    def screw_heads(self, x, top):
        # Threaded shanks intentionally omitted; head envelopes verify the real swept clearance.
        return [cq.Solid.makeCone(1, 2, 1, cq.Vector(x + dx, self.edge_y, top - 1))
                for dx in (-5.5, 5.5)]

    @lru_cache(None)
    def door(self):
        s = super().door()
        s = fuse(s, [box(16, 14, 4, (x - 8, self.edge_y - 6, self.tab_top - 4)) for x in self.edge_xs])
        holes = []
        for x in self.edge_xs:
            holes.append(cyl(3.15, 5, (x, self.edge_y, self.edge_z)))
            holes += [cyl(.85, 4, (x + dx, self.edge_y, self.tab_top - 3.5)) for dx in (-5.5, 5.5)]
            holes += self.head_seats(x, self.tab_top + .8)
        return cut(s, holes)

    @lru_cache(None)
    def frame(self):
        s = super().frame()
        holes = []
        for x in self.edge_xs:
            holes += [box(16.4, 12.4, 3, (x - 8.2, self.edge_y - 6.2, self.closed_top)),
                      cyl(3.15, 3.1, (x, self.edge_y, self.closed_top - 3.1))]
            holes += [cyl(.85, 6, (x + dx, self.edge_y, 2.5)) for dx in (-5.5, 5.5)]
            holes += self.head_seats(x, 8)
        return cut(s, holes)

    def open_pad(self, x):
        # Magnet starts 3 mm (nominal) from the opposite face of the moving magnet.
        face = self.edge_z + 3 + self.q.edge_magnet_gap
        bottom = face - .8
        top = face + 3.2
        s = box(22, 14, top - bottom, (x - 11, self.edge_y - 7, bottom))
        holes = [cyl(3.15, 5, (x, self.edge_y, face))]
        holes += [cyl(.85, top - bottom + 1, (x + dx, self.edge_y, bottom - .1)) for dx in (-5.5, 5.5)]
        holes += self.head_seats(x, top + .8)
        return self.opened(cut(s, holes))

    def open_mount_z(self):
        return self.open_pad(self.edge_xs[0]).BoundingBox().center.z

    @property
    def bolt_zs(self):
        zc = self.open_mount_z()
        return (zc - 15, zc - 4) if self.role == 'heater' else (zc - 8, zc + 8)

    @lru_cache(None)
    def open_bracket(self, x):
        s = self.open_pad(x)
        bb = s.BoundingBox()
        zc = self.open_mount_z()
        start_y = bb.ymax - 1.0
        if self.body_y - 4 <= start_y:
            raise ValueError('open catch bracket has no space before channel wall')
        rail_top = min(zc + 7, 112.5) if self.role == 'heater' else zc + 7
        rails = [box(2.6, self.body_y - start_y, rail_top - zc + 7,
                     (x + dx, start_y, zc - 7)) for dx in (-11, 8.4)]
        lo, hi = (zc - 22, 112.5) if self.role == 'heater' else (zc - 12, zc + 12)
        foot = box(22, 4, hi - lo, (x - 11, self.body_y - 4, lo))
        s = fuse(s, [*rails, foot])
        return cut(s, [cyl(1.7, 6, (x, self.body_y - 5, zz), (0, 1, 0)) for zz in self.bolt_zs])

    def body_mount_holes(self):
        if self.role == 'exhaust':
            return []
        return [cyl(1.7, self.body_thickness + 2, (x, self.body_y - 1, zz), (0, 1, 0))
                for x in self.edge_xs for zz in self.bolt_zs]

    def components(self, angle, input_angle=None):
        parts = super().components(angle, input_angle)
        def add(name, s, kind='print', mat='hot polymer', color='#538D88'):
            parts[name] = (s, kind, mat, color)
        for label, x in zip(('left', 'right'), self.edge_xs):
            add(f'edge_flap_cap_{label}', rotate_x(self.cap(x, self.tab_top, .8), -angle, self.pivot),
                color='#DBA34A')
            add(f'edge_flap_magnet_{label}', rotate_x(cyl(3, 3, (x, self.edge_y, self.edge_z)), -angle, self.pivot),
                'purchased_reference', '6x3 disc, pole opposite closed mate', '#D4E0E2')
            add(f'edge_closed_cap_{label}', self.cap(x, self.closed_top, 8 - self.closed_top))
            add(f'edge_closed_magnet_{label}', cyl(3, 3, (x, self.edge_y, self.closed_top - 3)),
                'purchased_reference', '6x3 disc, attracts flap bottom face', '#D4E0E2')
            for i, (moving, fixed) in enumerate(zip(self.screw_heads(x, self.tab_top + .8), self.screw_heads(x, 8))):
                add(f'edge_flap_screw_head_{label}_{i}', rotate_x(moving, -angle, self.pivot),
                    'purchased_reference', 'M2x4 countersunk head envelope; threaded shank omitted', '#A6ADB2')
                add(f'edge_closed_screw_head_{label}_{i}', fixed, 'purchased_reference',
                    'M2x5 countersunk head envelope; threaded shank omitted', '#A6ADB2')
            if self.role != 'exhaust':
                face = self.edge_z + 3 + self.q.edge_magnet_gap
                add(f'edge_open_{self.role}_bracket_{label}', self.open_bracket(x))
                add(f'edge_open_cap_{label}', self.opened(self.cap(x, face + 3.2, .8)))
                add(f'edge_open_magnet_{label}', self.opened(cyl(3, 3, (x, self.edge_y, face))),
                    'purchased_reference', '6x3 disc, attracts flap top face', '#D4E0E2')
                for i, head in enumerate(self.screw_heads(x, face + 4)):
                    add(f'edge_open_screw_head_{label}_{i}', self.opened(head), 'purchased_reference',
                        'M2x4 countersunk head envelope; threaded shank omitted', '#A6ADB2')
                for i, zz in enumerate(self.bolt_zs):
                    shaft = cyl(1.5, 16, (x, self.body_y - 4, zz), (0, 1, 0))
                    head = cyl(2.8, 2, (x, self.body_y - 6, zz), (0, 1, 0))
                    add(f'edge_mount_screw_{label}_{i}', fuse(shaft, [head]),
                        'purchased_reference', 'M3x16 body catch mounting', '#A6ADB2')
                    seal = cyl(3.5, 1, (x, self.body_y + self.body_thickness, zz), (0, 1, 0)).cut(
                        cyl(1.55, 3, (x, self.body_y + self.body_thickness - 1, zz), (0, 1, 0)))
                    add(f'edge_mount_seal_{label}_{i}', seal, 'seal', 'silicone sealing washer', '#5C666B')
                    washer = cyl(3.5, .5, (x, self.body_y + self.body_thickness + 1, zz), (0, 1, 0)).cut(
                        cyl(1.7, 2, (x, self.body_y + self.body_thickness + .5, zz), (0, 1, 0)))
                    add(f'edge_mount_washer_{label}_{i}', washer, 'purchased_reference', 'M3 washer', '#A6ADB2')
                    nut = hexprism(5.5, 2.4, (x, self.body_y + self.body_thickness + 1.5, zz), 'Y')
                    nut = nut.cut(cyl(1.5, 5, (x, self.body_y + self.body_thickness, zz), (0, 1, 0)))
                    add(f'edge_mount_nut_{label}_{i}', nut, 'purchased_reference', 'M3 nut envelope', '#A6ADB2')
        return parts
