"""Integral glue-in free-edge catches shared by spring and magnetic variants.

Local XY is the seat, +Z the opening side. Frame pockets load from the back;
flap pockets load from +Z. Open catch supports fuse into removable housings.
"""
from functools import lru_cache

from .model import box, cyl, cut, fuse, rotate_x
from .retention import RetainedValve


class EdgeMagneticValve(RetainedValve):
    def __init__(self, n, p, kind, q, role=None):
        super().__init__(n, p, kind, q)
        self.role = role or ('bin' if n == 120 else 'heater')
        if self.role not in ('bin', 'heater', 'exhaust') or (n == 120) != (self.role == 'bin'):
            raise ValueError('120 mm bin, or 80 mm heater/exhaust required')
        self.edge_y = -self.d - 3
        self.tab_bottom = 8 + p.gasket_compressed
        self.edge_z = self.tab_bottom + q.edge_membrane
        self.closed_top = 8 - q.edge_membrane
        self.tab_top = self.edge_z + q.edge_stack_capacity
        self.open_face = self.tab_top + q.edge_open_clearance + q.edge_membrane

    @property
    def edge_xs(self):
        return (-self.d + 18, self.d - 18)

    @property
    def edge_lever(self):
        return self.hy - self.edge_y

    @property
    def body_y(self):
        return self.p.half - self.p.lid_thickness if self.role == 'bin' else 58 - self.p.wall

    def opened(self, s):
        return rotate_x(s, -self.p.open_angle, self.pivot)

    def face_gap(self, opened=False):
        return (self.open_face - self.edge_z - self.q.edge_stack_height if opened
                else self.edge_z - self.closed_top)

    @lru_cache(None)
    def door(self):
        # A broad root carries the load; the thin membrane only closes the pocket.
        adds = [box(10, 10, self.tab_top - self.tab_bottom,
                    (x - 5, self.edge_y - 5, self.tab_bottom)) for x in self.edge_xs]
        s = fuse(super().door(), adds)
        return cut(s, [cyl(self.q.edge_pocket_diameter / 2, self.q.edge_stack_capacity + 1,
                           (x, self.edge_y, self.edge_z)) for x in self.edge_xs])

    @lru_cache(None)
    def frame(self):
        # Loading from the underside leaves an integral 0.4 mm contact membrane.
        return cut(super().frame(), [cyl(self.q.edge_pocket_diameter / 2, self.closed_top + 1,
                                        (x, self.edge_y, -1)) for x in self.edge_xs])

    def open_pad(self, x):
        bottom = self.open_face - self.q.edge_membrane
        top = self.open_face + self.q.edge_stack_capacity
        s = box(14, 10, top - bottom, (x - 7, self.edge_y - 5, bottom))
        s = s.cut(cyl(self.q.edge_pocket_diameter / 2, self.q.edge_stack_capacity + 1,
                      (x, self.edge_y, self.open_face)))
        return self.opened(s)

    @lru_cache(None)
    def open_support(self, x):
        """One solid designed to overlap its host wall by 0.5 mm for fusion."""
        s = self.open_pad(x)
        bb = s.BoundingBox()
        zc = bb.center.z
        start_y = bb.ymax - 1
        if self.body_y - 4 <= start_y:
            raise ValueError('integral open catch has no space before channel wall')
        rail_top = min(zc + 5, 112.5) if self.role == 'heater' else zc + 5
        rails = [box(2.4, self.body_y - start_y + .5, rail_top - zc + 5,
                     (x + dx, start_y, zc - 5)) for dx in (-7, 4.6)]
        lo, hi = (zc - 12, 112.5) if self.role == 'heater' else (zc - 8, zc + 8)
        foot = box(14, 4.5, hi - lo, (x - 7, self.body_y - 4, lo))
        return fuse(s, [*rails, foot])

    def components(self, angle, input_angle=None):
        parts = super().components(angle, input_angle)
        def add(name, s, kind='print', mat='hot polymer', color='#538D88'):
            parts[name] = (s, kind, mat, color)
        for label, x in zip(('left', 'right'), self.edge_xs):
            add(f'edge_flap_magnet_{label}', rotate_x(cyl(self.q.edge_magnet_diameter / 2,
                self.q.edge_stack_height, (x, self.edge_y, self.edge_z)), -angle, self.pivot),
                'purchased_reference', '5 mm glued magnet stack; attracts both endpoint mates', '#D4E0E2')
            add(f'edge_closed_magnet_{label}', cyl(self.q.edge_magnet_diameter / 2,
                self.q.edge_stack_height, (x, self.edge_y, self.closed_top - self.q.edge_stack_height)),
                'purchased_reference', '5 mm glued stack seated against frame membrane', '#D4E0E2')
            if self.role != 'exhaust':
                # Present locally for motion checks; fused into the host in full assemblies.
                add(f'edge_open_{self.role}_integral_{label}', self.open_support(x))
                add(f'edge_open_magnet_{label}', self.opened(cyl(self.q.edge_magnet_diameter / 2,
                    self.q.edge_stack_height, (x, self.edge_y, self.open_face))),
                    'purchased_reference', '5 mm glued stack seated against open-catch membrane', '#D4E0E2')
        return parts


def magnet_coupon(q):
    """Three real pocket diameters with the specified membrane, print open side up."""
    s = box(36, 12, q.edge_membrane + q.edge_stack_capacity)
    return cut(s, [cyl(d / 2, q.edge_stack_capacity + 1, (x, 6, q.edge_membrane))
                   for x, d in zip((6, 18, 30), (5.2, 5.3, 5.4))])
