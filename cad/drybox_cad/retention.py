"""Two independent bistable valve prototypes, with a common coaxial lost-motion drive.

Valve datums match model.Valve. Positive flap angles rotate clockwise about local X.
All dimensions in mm; spring/magnetic force inputs are assumptions, not vendor data.
"""
from dataclasses import dataclass, asdict
from functools import lru_cache
import math

import cadquery as cq
import numpy as np

from .model import (Valve, Part, box, cyl, cut, fuse, hexprism, rotate_x,
                    make_parts, valve_to_leg, valve_to_outlet, valve_to_heater)


@dataclass(frozen=True)
class RetentionParameters:
    drive_radius: float = 8.5
    lost_motion_deg: float = 7.0
    drive_pin_diameter: float = 3.0
    slot_clearance: float = 0.4
    stop_radius: float = 16.0
    spring_radius: float = 10.0
    spring_anchor_radius: float = 35.0
    spring_dead_angle: float = 25.0
    spring_free_eye_length: float = 32.0
    spring_initial_force_n: float = 1.5
    spring_rate_n_per_mm: float = 1.1
    spring_outer_diameter: float = 4.0
    magnet_radius: float = 24.0
    magnet_diameter: float = 6.0
    magnet_thickness: float = 3.0
    magnet_gap: float = 1.5
    assumed_force_per_magnet_n: float = 1.8
    polymer_density_g_cm3: float = 1.4

    def validate(self, p):
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name}: finite positive value required')
        if not 6 <= self.lost_motion_deg <= 9:
            raise ValueError('lost_motion_deg supported range 6..9')
        if not 8 <= self.drive_radius <= 9:
            raise ValueError('drive_radius supported range 8..9')
        if self.drive_pin_diameter != 3 or not .3 <= self.slot_clearance <= .6:
            raise ValueError('M3 smooth drive pin required; clearance .3..0.6 mm')
        if self.stop_radius != 16 or self.magnet_radius != 24:
            raise ValueError('stop and magnetic carrier interfaces fixed at R16/R24')
        if not 9 <= self.spring_radius <= 10:
            raise ValueError('spring_radius supported range 9..10')
        if not 33 <= self.spring_anchor_radius <= 36:
            raise ValueError('spring_anchor_radius supported range 33..36')
        if not 20 <= self.spring_dead_angle <= 30 < p.open_angle:
            raise ValueError('spring dead angle supported range 20..30')
        if not 28 <= self.spring_free_eye_length <= 33:
            raise ValueError('spring free eye-to-eye length supported range 28..33')
        if not 3 <= self.spring_outer_diameter <= 4:
            raise ValueError('spring envelope OD supported range 3..4')
        if self.magnet_diameter != 6 or self.magnet_thickness != 3:
            raise ValueError('magnet cartridges use 6x3 mm discs')
        if not 1.2 <= self.magnet_gap <= 3:
            raise ValueError('magnet_gap supported range 1.2..3 mm')


def radial_point(radius, phi):
    a = math.radians(phi)
    return np.array([radius * math.cos(a), radius * math.sin(a)])


def segment(radius, length, a, b):
    """Exact cylinder from a to b. Purchased spring clearance envelope uses this."""
    a, b = np.array(a), np.array(b)
    direction = b - a
    return cyl(radius, length if length is not None else np.linalg.norm(direction),
               tuple(a), tuple(direction / np.linalg.norm(direction)))


class RetainedValve(Valve):
    def __init__(self, n, p, kind, q=None):
        super().__init__(n, p)
        self.q = q or RetentionParameters()
        self.q.validate(p)
        if kind not in ('spring', 'magnetic'):
            raise ValueError('kind must be spring or magnetic')
        self.kind = kind
        self.phi = 90 + p.open_angle / 2
        self.x0 = self.d + 20
        self.input_x = self.d + 44

    def polar(self, s, phi=None):
        return rotate_x(s, self.phi if phi is None else phi, (0, 0, 0)).translate((0, self.hy, self.hz))

    @lru_cache(None)
    def mount(self):
        """Frame-edge attachment, bearing support plate and coaxial SG90 cradle."""
        o = self.outer / 2
        x = o + .6
        s = box(5, self.outer - 28, 7, (x, -o + 14, .5))
        s = fuse(s, [box(4, 72, self.hz + 55, (x, self.hy - 36, 0))])
        # Outrigger rails avoid the rotating disc and keep the SG90 case in its window.
        for yy in (self.hy - 29, self.hy + 22):
            s = fuse(s, [box(self.d + 63 - x, 7, 4, (x, yy, .5))])
        plate = box(4, 58, 20, (self.d + 54.5, self.hy - 29, self.hz - 10))
        plate = plate.cut(box(6, 25, 13, (self.d + 53.5, self.hy - 18, self.hz - 6.5)))
        s = fuse(s, [plate])
        for yy in (-o + 20, o - 20):
            s = fuse(s, [box(6, 10, 8, (o, yy - 5, 0))])
        holes = [cyl(1.7, 14, (o - 3, yy, 4), (1, 0, 0)) for yy in (-o + 20, o - 20)]
        holes.append(cyl(5.5, 8, (x - 1, self.hy, self.hz), (1, 0, 0)))
        for yy in (self.hy - 19.25, self.hy + 8.25):
            holes.append(cyl(1.3, 8, (self.d + 53.5, yy, self.hz), (1, 0, 0)))
        for angle in (0, self.p.open_angle):
            yy, zz = self.stop_centre(angle)
            holes.append(cyl(1.25, 8, (x - 1, yy, zz), (1, 0, 0)))
        if self.kind == 'spring':
            holes.append(cyl(1.25, 8, (x - 1, self.hy, self.hz + self.q.spring_anchor_radius), (1, 0, 0)))
        else:
            for angle in (0, self.p.open_angle):
                for t in (6, 12):
                    sign = 1 if angle == 0 else -1
                    hole = self.polar(cyl(1.7, 8, (x - 1, 35, sign * t), (1, 0, 0)), self.phi - angle)
                    holes.append(hole)
        return cut(s, holes)

    def stop_centre(self, angle):
        phi = self.phi - angle
        p = radial_point(self.q.stop_radius, phi)
        a = math.radians(phi)
        tangent = np.array([math.sin(a), -math.cos(a)])
        p += (-1 if angle == 0 else 1) * 5.5 * tangent
        return tuple(p + [self.hy, self.hz])

    @lru_cache(None)
    def stop_sleeve(self):
        return cyl(3, 4, (self.x0, 0, 0), (1, 0, 0)).cut(cyl(1.7, 6, (self.x0 - 1, 0, 0), (1, 0, 0)))

    @lru_cache(None)
    def rotor(self):
        s = cyl(7, 4, (self.x0, self.hy, self.hz), (1, 0, 0))
        # Top arm operates replaceable closed/open stop sleeves.
        arm = box(4, 17, 4, (self.x0, 0, -2))
        arm = fuse(arm, [cyl(2.5, 4, (self.x0, 16, 0), (1, 0, 0))])
        s = fuse(s, [self.polar(arm)])
        if self.kind == 'spring':
            phi = -90 + self.q.spring_dead_angle
            arm = box(4, self.q.spring_radius, 4, (self.x0, 0, -2))
            arm = fuse(arm, [cyl(2.2, 4, (self.x0, self.q.spring_radius, 0), (1, 0, 0))])
            arm = arm.cut(cyl(1.1, 6, (self.x0 - 1, self.q.spring_radius, 0), (1, 0, 0)))
            s = fuse(s, [self.polar(arm, phi)])
        else:
            # A mild-steel 14x8x2 mm keeper slides in axially and exposes both magnetic faces.
            carrier = box(4, 25, 2.8, (self.x0, 0, -1.4))
            carrier = fuse(carrier, [box(4, 16, 3, (self.x0, 16, -1.5)),
                                     box(20, 4.5, 3, (self.x0, 16, -1.5)),
                                     box(20, 4.5, 3, (self.x0, 27.5, -1.5))])
            carrier = carrier.cut(box(17, 8.4, 2.2, (self.d + 24.2, 19.8, -1.1)))
            carrier = cut(carrier, [cyl(.85, 7, (self.d + 34, rr, 0), (1, 0, 0)) for rr in (18, 30)])
            s = fuse(s, [self.polar(carrier)])
        # Drive pin starts toward +Y, clear of the spring and stock-horn screws.
        s = fuse(s, [cyl(2.5, 4, (self.x0, self.hy + self.q.drive_radius, self.hz), (1, 0, 0))])
        return cut(s, [hexprism(6 + self.p.hex_clearance, 6, (self.x0 - 1, self.hy, self.hz), 'X'),
                       cyl(1.25, 6, (self.x0 - 1, self.hy + self.q.drive_radius, self.hz), (1, 0, 0))])

    @lru_cache(None)
    def driver(self):
        s = cyl(12, 4, (self.input_x, self.hy, self.hz), (1, 0, 0))
        s = s.cut(cyl(1.6, 6, (self.input_x - 1, self.hy, self.hz), (1, 0, 0)))
        s = s.cut(cyl(4.25, 3, (self.input_x + 2, self.hy, self.hz), (1, 0, 0)))
        tools = []
        for sign in (-1, 1):
            zc = self.hz + sign * 6
            tools.append(box(6, 2.3, 2, (self.input_x - 1, self.hy - 1.15, zc - 1)))
            for offset in (-1, 1):
                tools.append(cyl(1.15, 6, (self.input_x - 1, self.hy, zc + offset), (1, 0, 0)))
        # Analytic annular-sector slot with round caps, rather than a polygon approximation.
        r = self.q.drive_radius
        w = (self.q.drive_pin_diameter + self.q.slot_clearance) / 2
        a = math.radians(self.q.lost_motion_deg)
        def yz(rad, theta):
            return (rad * math.cos(theta), -rad * math.sin(theta))
        wire = (cq.Workplane('YZ', origin=(self.input_x - 1, self.hy, self.hz))
                .moveTo(*yz(r + w, -a)).threePointArc(yz(r + w, 0), yz(r + w, a))
                .lineTo(*yz(r - w, a)).threePointArc(yz(r - w, 0), yz(r - w, -a)).close())
        tools.append(wire.extrude(6).val())
        for t in (-a, a):
            yy, zz = yz(r, t)
            tools.append(cyl(w, 6, (self.input_x - 1, self.hy + yy, self.hz + zz), (1, 0, 0)))
        return cut(s, tools)

    @lru_cache(None)
    def magnetic_holder(self, opened=False, cap=False):
        sign = -1 if opened else 1
        phi = self.phi - (self.p.open_angle if opened else 0)
        front = 1 + self.q.magnet_gap - .4
        end = 1 + self.q.magnet_gap + self.q.magnet_thickness
        if cap:
            s = box(21.4, 10, .8, (self.d + 18.6, 20, end))
        else:
            s = box(21.4, 10, end - front, (self.d + 18.6, 20, front))
            s = fuse(s, [box(21.4, 9, 16 - front, (self.d + 18.6, 30, front))])
            holes = []
            for xx in (self.d + 27.5, self.d + 34.5):
                holes += [cyl(3.15, 5, (xx, 24, front + .4)),
                          cyl(2.6, 1, (xx, 24, front - .1))]
            # Clamp slots tangent to the arc: 2 mm travel for force tuning.
            for tt in (6, 12):
                holes.append(box(25, 3.4, 2, (self.d + 17.6, 35 - 1.7, tt - 1)))
                for off in (-1, 1):
                    holes.append(cyl(1.7, 25, (self.d + 17.6, 35, tt + off), (1, 0, 0)))
            s = cut(s, holes)
        screws = [cyl(.85 if not cap else 1.1, 8, (xx, rr, front - 1))
                  for xx, rr in ((self.d + 22, 22), (self.d + 37, 28))]
        s = cut(s, screws)
        if sign < 0:
            s = s.mirror('XY')
        return self.polar(s, phi)

    def spring_points(self, angle):
        move = radial_point(self.q.spring_radius, -90 + self.q.spring_dead_angle - angle)
        return np.array([self.d + 29, self.hy + move[0], self.hz + move[1]]), np.array([
            self.d + 29, self.hy, self.hz + self.q.spring_anchor_radius])

    def spring_torque(self, angle):
        a, b = self.spring_points(angle)
        length = np.linalg.norm(b - a)
        force = self.q.spring_initial_force_n + self.q.spring_rate_n_per_mm * (length - self.q.spring_free_eye_length)
        direction = (b - a) / length
        # Positive means opening, opposite local-X torque.
        torque = -np.cross(a - [a[0], self.hy, self.hz], force * direction)[0]
        return float(torque), float(length), float(force)

    @property
    def engagement_angle(self):
        return self.q.lost_motion_deg + math.degrees(2 * math.asin(self.q.slot_clearance / (4 * self.q.drive_radius)))

    def components(self, angle, input_angle=None):
        if not 0 <= angle <= self.p.open_angle:
            raise ValueError('flap outside hard stops')
        input_angle = angle if input_angle is None else input_angle
        if abs(input_angle - angle) > self.engagement_angle + 1e-8:
            raise ValueError('drive pin outside angular lost-motion domain')
        base = super().components(angle)
        for key in ('crank', 'horn_adapter', 'link', 'servo_cradle', 'servo_envelope', 'stock_horn_envelope'):
            base.pop(key)
        def add(name, s, kind='print', mat='hot polymer', color='#35576A'):
            base[name] = (s, kind, mat, color)
        add('coaxial_mount', self.mount())
        add('latch_rotor', rotate_x(self.rotor(), -angle, self.pivot), color='#D58638')
        add('slotted_driver', rotate_x(self.driver(), -input_angle, self.pivot), color='#E9C777')
        for label, a in (('closed', 0), ('open', self.p.open_angle)):
            yy, zz = self.stop_centre(a)
            add(f'{label}_stop_sleeve', self.stop_sleeve().translate((0, yy, zz)), color='#6C8A9B')
            add(f'{label}_stop_screw', cyl(1.5, 11, (self.d + 15, yy, zz), (1, 0, 0)),
                'purchased_reference', 'M3 screw, smooth envelope', '#A6ADB2')
        pin = cyl(1.5, 28, (self.x0 + 1, self.hy + self.q.drive_radius, self.hz), (1, 0, 0))
        # Smooth M3 pin/shaft, locked to rotor; threaded metal must not rub the slot.
        add('drive_pin', rotate_x(pin, -angle, self.pivot), 'purchased_reference', 'smooth steel M3 pin', '#D2D8DB')
        add('rotor_retainer', cyl(2.5, 2, (self.x0 + 4, self.hy, self.hz), (1, 0, 0)),
            'purchased_reference', 'M3 low head and washer envelope', '#A6ADB2')
        servo = box(23, 23, 12, (self.d + 56, self.hy - 17, self.hz - 6))
        servo = fuse(servo, [box(2.5, 32.5, 12, (self.d + 58.5, self.hy - 22, self.hz - 6)),
                            cyl(2.5, 7, (self.d + 49, self.hy, self.hz), (1, 0, 0))])
        add('servo_envelope', servo, 'purchased_reference', 'SG90 provisional', '#3883B9')
        add('stock_horn_envelope', cyl(7, .9, (self.d + 48.2, self.hy, self.hz), (1, 0, 0)),
            'purchased_reference', 'stock SG90 horn', '#F0EADC')
        if self.kind == 'spring':
            a, b = self.spring_points(angle)
            direction = (b - a) / np.linalg.norm(b - a)
            # OD envelope ends 3 mm from eye centres; actual hook geometry is vendor dependent.
            add('extension_spring_envelope', segment(self.q.spring_outer_diameter / 2, None,
                a + direction * 3, b - direction * 3), 'purchased_reference',
                'extension spring OD envelope; see force assumptions', '#9EB4A2')
            for label, pt in (('moving', a), ('anchor', b)):
                add(f'spring_{label}_pin', cyl(1, 10 if label == 'moving' else 16, (self.x0 + 1 if label == 'moving' else self.d + 15, pt[1], pt[2]), (1, 0, 0)),
                    'purchased_reference', 'M2 eye pin with spacer', '#D2D8DB')
        else:
            steel = self.polar(box(14, 8, 2, (self.d + 24.5, 20, -1)))
            add('steel_keeper', rotate_x(steel, -angle, self.pivot), 'purchased_reference',
                'mild steel strip 14x8x2 mm', '#B4BDC5')
            cap = self.polar(fuse(box(2, 16, 3, (self.d + 40, 16, -1.5)),
                                  [box(1.5, 8, 2, (self.d + 38.5, 20, -1))]))
            cap = cut(cap, [self.polar(cyl(1.1, 4, (self.d + 39, rr, 0), (1, 0, 0))) for rr in (18, 30)])
            add('keeper_cap', rotate_x(cap, -angle, self.pivot), color='#D58638')
            for opened in (False, True):
                label = 'open' if opened else 'closed'
                add(f'{label}_magnet_holder', self.magnetic_holder(opened))
                add(f'{label}_magnet_cap', self.magnetic_holder(opened, True), color='#6C8A9B')
                phi = self.phi - (self.p.open_angle if opened else 0)
                sign = -1 if opened else 1
                for i, xx in enumerate((self.d + 27.5, self.d + 34.5)):
                    mag = cyl(3, 3, (xx, 24, 1 + self.q.magnet_gap))
                    if sign < 0:
                        mag = mag.mirror('XY')
                    add(f'{label}_magnet_{i}', self.polar(mag, phi), 'purchased_reference',
                        '6x3 mm magnet; force/temperature grade unselected', '#C5D2D6')
        return base


def variant_assembly(p, q, kind, mode='dry'):
    parts = make_parts(p, mode)
    placements = [
        ('box_valve_left_', 120, lambda s: valve_to_leg(s, -p.leg_spacing / 2, p)),
        ('box_valve_right_', 120, lambda s: valve_to_leg(s, p.leg_spacing / 2, p)),
        ('exhaust_left_', 80, lambda s: valve_to_outlet(s, -p.leg_spacing / 2, p)),
        ('exhaust_right_', 80, lambda s: valve_to_outlet(s, p.leg_spacing / 2, p)),
        ('heater_valve_', 80, lambda s: valve_to_heater(s, p)),
    ]
    for prefix, n, place in placements:
        for name in list(parts):
            if name.startswith(prefix):
                del parts[name]
        angle = p.open_angle if (mode == 'dry' and n == 120) or (mode == 'regenerate' and n == 80) else 0
        for key, (shape, part_kind, material, color) in RetainedValve(n, p, kind, q).components(angle).items():
            name = prefix + key
            parts[name] = Part(name, place(shape), part_kind, material, color, f'valve{n}_{key}')
    return parts
