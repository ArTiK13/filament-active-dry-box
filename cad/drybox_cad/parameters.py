"""All dimensions in mm; Z up; bin wall Y=0, module Y>0."""
from dataclasses import dataclass, asdict
import math

@dataclass(frozen=True)
class Parameters:
    bin_width: float = 600
    bin_depth: float = 400
    bin_height: float = 350
    fan120: float = 120
    fan80: float = 80
    fan_thickness: float = 25
    heater_y: float = 110
    leg_spacing: float = 280
    duct_size: float = 156
    wall: float = 3.2
    bottom_z: float = 50
    leg_start_y: float = 12
    leg_end_y: float = 222
    joint_gap: float = 1
    bridge_depth: float = 156
    lid_thickness: float = 4
    flange_thickness: float = 6
    cassette_height: float = 45
    cassette_wall: float = 2.4
    cassette_floor_z: float = 60
    open_angle: float = 82
    gasket_free: float = 2
    gasket_compressed: float = 1.7
    journal_clearance: float = .45
    hex_clearance: float = .25
    m3_clearance: float = 3.4
    m4_clearance: float = 4.5
    rod_centres: float = 42
    crank_radius: float = 18
    print_limit: float = 240
    mesh_linear: float = .12
    mesh_angular: float = .12

    @property
    def width(self): return self.leg_spacing + self.duct_size
    @property
    def bridge_y(self): return self.leg_end_y + self.joint_gap
    @property
    def bridge_cy(self): return self.bridge_y + self.bridge_depth/2
    @property
    def back_y(self): return self.bridge_y + self.bridge_depth
    @property
    def centre_z(self): return self.bottom_z + self.duct_size/2
    @property
    def top_z(self): return self.bottom_z + self.duct_size
    @property
    def lid_z(self): return self.top_z - self.lid_thickness
    @property
    def half(self): return self.duct_size/2

    def validate(self):
        for k,v in asdict(self).items():
            if not isinstance(v,(int,float)) or not math.isfinite(v) or v <= 0:
                raise ValueError(f'{k}: finite positive dimension required')
        if self.duct_size != self.fan120+36:
            raise ValueError('duct_size must equal fan120 + 36 for the valve interface')
        if not 2.8 <= self.wall <= 4:
            raise ValueError('wall supported range 2.8..4')
        if not 260 <= self.leg_spacing <= 300:
            raise ValueError('leg_spacing supported range 260..300')
        if not 195 <= self.leg_end_y-self.leg_start_y <= 220:
            raise ValueError('leg length supported range 195..220')
        if not 148 <= self.bridge_depth <= 170:
            raise ValueError('bridge_depth supported range 148..170')
        if not 35 <= self.cassette_height <= 45:
            raise ValueError('cassette_height supported range 35..45; inlet flap must clear it')
        if not 78 <= self.open_angle <= 83:
            raise ValueError('open_angle supported range 78..83; avoids linkage toggle')
        if not self.bottom_z+self.wall+5 <= self.cassette_floor_z <= self.lid_z-self.cassette_height-30:
            raise ValueError('cassette must clear floor screw heads and leave >=30 mm air channel')
        if self.leg_spacing <= self.duct_size+80:
            raise ValueError('insufficient central service space')
        if self.gasket_compressed >= self.gasket_free:
            raise ValueError('gasket_compressed must be less than free thickness')
        if self.width/2 > self.print_limit:
            raise ValueError('bridge half exceeds provisional print envelope')
