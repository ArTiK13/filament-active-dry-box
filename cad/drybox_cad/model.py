"""Pure exact BRep builders. Printed parts, seals and purchased envelopes stay separate."""
from dataclasses import dataclass
from functools import lru_cache
import math
import cadquery as cq
from .parameters import Parameters


def box(x,y,z,at=(0,0,0)):
    return cq.Solid.makeBox(x,y,z,cq.Vector(*at))


def cyl(r,length,at=(0,0,0),axis=(0,0,1)):
    return cq.Solid.makeCylinder(r,length,cq.Vector(*at),cq.Vector(*axis))


def cut(s,tools):
    return s.cut(*tools) if tools else s


def fuse(s,items):
    return s.fuse(*items) if items else s


def ring(w,h,t,iw,ih=None):
    ih=iw if ih is None else ih
    return box(w,h,t,(-w/2,-h/2,0)).cut(box(iw,ih,t+2,(-iw/2,-ih/2,-1)))


def hexprism(af,length,at,axis='X'):
    # regular hex with across-flats dimension af, initially normal Z
    s=cq.Workplane('XY').polygon(6,af/math.cos(math.pi/6)).extrude(length).val()
    if axis=='X': s=s.rotate((0,0,0),(0,1,0),90)
    if axis=='Y': s=s.rotate((0,0,0),(1,0,0),-90)
    return s.translate(at)


def bolt_pattern(n):
    a=(n+36)/2-8
    b=(n-8)/2-8
    return [(x,y) for x in (-a,a) for y in (-b,b)]


def points_holes(s,points,d,length=40,z=-10):
    return cut(s,[cyl(d/2,length,(x,y,z)) for x,y in points])


def rotate_x(s,theta,pivot):
    return s.rotate(pivot,(pivot[0]+1,pivot[1],pivot[2]),theta)


@dataclass
class Part:
    name: str
    shape: cq.Shape
    kind: str  # print / seal / purchased_reference
    material: str
    color: str
    design: str
    orientation: str='as_modelled'


class Valve:
    """Local aperture XY, positive Z is flap-opening side; hinge axis X."""
    def __init__(self,n,p):
        self.n=n;self.p=p
        self.ap=n-8;self.outer=n+36;self.d=self.ap/2+8
        self.hy=self.ap/2+12
        self.hz=8+p.gasket_compressed+2
        self.sx=self.d+24
        self.crank_x=self.d+20
        self.servo_z=self.hz+p.rod_centres
        self.pivot=(0,self.hy,self.hz)

    @lru_cache(None)
    def frame(self):
        s=ring(self.outer,self.outer,8,self.ap)
        # bearing pedestals attach to the seat at Z=8; left steel pin, right printed journal
        adds=[]
        for sign in (-1,1):
            x=sign*(self.d+5.75)
            x0=x-3.75
            adds += [box(7.5,11,self.hz,(x0,self.hy-5.5,0)),
                     cyl(5.5,7.5,(x0,self.hy,self.hz),(1,0,0))]
        s=fuse(s,adds)
        holes=[cyl(self.p.m4_clearance/2,32,(x,y,-1)) for x,y in bolt_pattern(self.n)]
        holes += [cyl(1.7,12,(-self.d-11,self.hy,self.hz),(1,0,0)),
                  cyl((8+self.p.journal_clearance)/2,20,(self.d,self.hy,self.hz),(1,0,0)),
                  cyl(5.5,2*self.d+1,(-self.d-.5,self.hy,self.hz),(1,0,0))]
        # servo bracket bolts normal X into captive M3 nuts in the seat edge
        for y in (-self.outer/2+20,self.outer/2-20):
            holes += [box(3,6.7,5,(self.outer/2-11,y-3.35,4)),
                      cyl(1.7,16,(self.outer/2-14,y,4),(1,0,0)),
                      hexprism(5.8,3,(self.outer/2-11,y,4),'X')]
        return cut(s,holes)

    @lru_cache(None)
    def door(self):
        s=box(2*self.d,2*self.d,4,(-self.d,-self.d,8+self.p.gasket_compressed))
        # two hinge ears, one steel-pin bearing and one integral driven journal
        for x0 in (-self.d,self.d-8):
            s=fuse(s,[box(8,self.hy-self.d+1,4,(x0,self.d-1,8+self.p.gasket_compressed)),
                      cyl(5,8,(x0,self.hy,self.hz),(1,0,0))])
        s=fuse(s,[cyl(4,28,(self.d-8,self.hy,self.hz),(1,0,0)),
                  hexprism(6,3.8,(self.d+20,self.hy,self.hz),'X')])
        return cut(s,[cyl(1.65,12,(-self.d-1,self.hy,self.hz),(1,0,0)),
                      cyl(1.25,17,(self.d+10,self.hy,self.hz),(1,0,0))])

    def arm(self,horn=False):
        # normal X, hinge at (0,hy,hz); stock horn is retained, no copied spline
        x0=self.crank_x
        root=cyl(8,4,(x0,self.hy,self.hz),(1,0,0))
        adds=[box(4,self.p.crank_radius,8,(x0,self.hy-self.p.crank_radius,self.hz-4)),
              cyl(4,4,(x0,self.hy-self.p.crank_radius,self.hz),(1,0,0))]
        s=fuse(root,adds)
        holes=[cyl(1.2,8,(x0-1,self.hy-self.p.crank_radius,self.hz),(1,0,0))]
        if horn:
            holes += [cyl(1.2,8,(x0-1,self.hy,self.hz),(1,0,0)),
                      cyl(4.25,3,(x0+2,self.hy,self.hz),(1,0,0))]
            # two elongated holes, attached to a normal SG90 stock horn at 5..7 mm radius
            for sign in (-1,1):
                yc=self.hy+sign*6
                holes += [box(8,3,2.3,(x0-1,yc-1.5,self.hz-1.15)),
                          cyl(1.15,8,(x0-1,yc-1.5,self.hz),(1,0,0)),
                          cyl(1.15,8,(x0-1,yc+1.5,self.hz),(1,0,0))]
        else:
            holes += [hexprism(6+self.p.hex_clearance,8,(x0-1,self.hy,self.hz),'X')]
        return cut(s,holes)

    @lru_cache(None)
    def link(self):
        x0=self.crank_x+4.7
        y=self.hy-self.p.crank_radius
        s=box(3,8,self.p.rod_centres,(x0,y-4,self.hz))
        s=fuse(s,[cyl(4,3,(x0,y,self.hz),(1,0,0)),
                  cyl(4,3,(x0,y,self.servo_z),(1,0,0))])
        return cut(s,[cyl(1.2,5,(x0-1,y,z),(1,0,0)) for z in (self.hz,self.servo_z)])

    @lru_cache(None)
    def servo_bracket(self):
        # SG90 mounting ears lie in a YZ plane; slots accept approximate 27.5 mm pitch.
        o=self.outer/2; x=o+.6
        s=box(5,self.outer-28,7,(x,-self.outer/2+14,.5))
        s=fuse(s,[box(5,7,self.servo_z-16,(x,self.hy-29,6)),
                  box(self.d+33-x,7,4,(x,self.hy-29,self.servo_z-14)),
                  box(self.d+33-x,7,4,(x,self.hy+8,self.servo_z-14))])
        plate=box(4,44,20,(self.d+28.5,self.hy-29,self.servo_z-10))
        plate=plate.cut(box(6,25,13,(self.d+27.5,self.hy-18,self.servo_z-6.5)))
        s=fuse(s,[plate])
        for y in (-o+20,o-20):
            s=fuse(s,[box(6,10,8,(o,y-5,0))])
        tools=[cyl(1.7,14,(o-3,y,4),(1,0,0)) for y in (-o+20,o-20)]
        for y in (self.hy-19.25,self.hy+8.25):
            tools += [box(8,2,2.6,(self.d+27,y-1,self.servo_z-1.3)),
                      cyl(1.3,8,(self.d+27,y-1,self.servo_z),(1,0,0)),
                      cyl(1.3,8,(self.d+27,y+1,self.servo_z),(1,0,0))]
        return cut(s,tools)

    def gasket(self):
        return ring(self.ap+14,self.ap+14,self.p.gasket_compressed,self.ap+1).translate((0,0,8))

    def journal_washer(self):
        return cyl(6,1,(self.outer/2,self.hy,self.hz),(1,0,0)).cut(
            cyl(4.05,3,(self.outer/2-1,self.hy,self.hz),(1,0,0)))

    def components(self,angle):
        a=-angle
        door=rotate_x(self.door(),a,self.pivot)
        crank=rotate_x(self.arm(),a,self.pivot)
        horn=self.arm(True).translate((0,0,self.p.rod_centres))
        horn=rotate_x(horn,a,(0,self.hy,self.servo_z))
        rad=math.radians(a)
        dy=self.p.crank_radius*(1-math.cos(rad))
        dz=-self.p.crank_radius*math.sin(rad)
        link=self.link().translate((0,dy,dz))
        # vendor envelope, not a manufacturing drawing of any particular SG90
        servo=box(23,23,12,(self.d+30,self.hy-17,self.servo_z-6))
        servo=fuse(servo,[box(2.5,32.5,12,(self.d+32.5,self.hy-22,self.servo_z-6)),
                          cyl(2.5,7,(self.d+23,self.hy,self.servo_z),(1,0,0))])
        stock=cyl(7,.9,(self.crank_x+4.2,self.hy,self.servo_z),(1,0,0))
        pin=cyl(1.5,20,(-self.d-12,self.hy,self.hz),(1,0,0))
        return {'frame':(self.frame(),'print','hot polymer','#35576A'),
                'flap':(door,'print','hot polymer','#DBA34A'),
                'crank':(crank,'print','polymer','#D58638'),
                'horn_adapter':(horn,'print','polymer','#D58638'),
                'link':(link,'print','polymer','#EBCB82'),
                'servo_cradle':(self.servo_bracket(),'print','polymer','#35576A'),
                'flap_seal':(self.gasket(),'seal','silicone sheet 2 mm','#5C666B'),
                'journal_seal':(self.journal_washer(),'seal','silicone washer','#5C666B'),
                'hinge_pin':(pin,'purchased_reference','steel 3 mm','#A6ADB2'),
                'servo_envelope':(servo,'purchased_reference','SG90 provisional','#3883B9'),
                'stock_horn_envelope':(stock,'purchased_reference','stock SG90 horn','#F0EADC')}


def valve_to_leg(s,x,p):
    return s.rotate((0,0,0),(1,0,0),90).rotate((0,0,0),(0,0,1),180).translate((x,3,p.centre_z))


def valve_to_outlet(s,x,p):
    return s.translate((x,p.bridge_cy,p.top_z+1))


def valve_to_heater(s,p):
    # local X -> +Z, Y -> -Y, Z -> +X; flap opens outward inside the sealed hood
    return s.rotate((0,0,0),(0,1,0),90).rotate((0,0,0),(1,0,0),180).translate((p.width/2+1,p.heater_y,p.centre_z+20))


def lid_points_leg(p,heater=False):
    pts=[]
    for x in (-p.half+8,p.half-8):
        mid=p.leg_end_y-44 if heater and x>0 else (p.leg_start_y+p.leg_end_y)/2
        pts.extend((x,y) for y in (p.leg_start_y+35,mid,p.leg_end_y-20))
    return pts


def lid_points_bridge(p,side):
    xmin,xmax=(-p.width/2,-.5) if side<0 else (.5,p.width/2)
    return [(x,y) for x in (xmin+12,(xmin+xmax)/2,xmax-12)
            for y in (p.bridge_y+10,p.back_y-10)]


def add_posts(s,points,p):
    height=p.lid_z-p.bottom_z
    s=fuse(s,[cyl(5,height,(x,y,p.bottom_z)) for x,y in points])
    return cut(s,[cyl(1.25,12,(x,y,p.lid_z-10)) for x,y in points])


def leg_body(p,heater=False):
    h=p.lid_z-p.bottom_z; length=p.leg_end_y-p.leg_start_y
    s=box(p.duct_size,length,h,(-p.half,p.leg_start_y,p.bottom_z))
    s=s.cut(box(p.duct_size-2*p.wall,length+2,h+2,(-p.half+p.wall,p.leg_start_y-1,p.bottom_z+p.wall)))
    # rear flange, open top is closed by removable lid
    f=box(p.duct_size,6,h,(-p.half,p.leg_end_y-6,p.bottom_z))
    f=f.cut(box(128,8,128,(-64,p.leg_end_y-7,p.centre_z-64)))
    s=fuse(s,[f])
    # four front nut bosses connect through the bin clamp and the valve frame
    for x,z in bolt_pattern(120):
        s=fuse(s,[cyl(6,12,(x,p.leg_start_y,p.centre_z+z),(0,1,0))])
    tools=[]
    for x,z in bolt_pattern(120):
        tools += [cyl(2.25,15,(x,p.leg_start_y-1,p.centre_z+z),(0,1,0)),
                  hexprism(7.4,4,(x,p.leg_start_y+8,p.centre_z+z),'Y')]
    for x in (-70,70):
        for z in (-62,62): tools.append(cyl(2.25,10,(x,p.leg_end_y-7,p.centre_z+z),(0,1,0)))
    v=Valve(120,p)
    # through-wall journal and left steel pin. Holes need silicone journal washers externally.
    for xx,r in ((-p.half-1,4.3),(p.half-5,1.8)):
        tools.append(cyl(r,7,(xx,3+v.hz,p.centre_z+v.hy),(1,0,0)))
    tools.append(cyl(2.25,10,(0,65,p.bottom_z-1)))
    if heater:
        tools.append(box(12,72,72,(p.half-8,p.heater_y-36,p.centre_z+20-36)))
        for lx,ly in bolt_pattern(80):
            tools.append(cyl(2.25,12,(p.half-8,p.heater_y+ly,p.centre_z+20+lx),(1,0,0)))
    s=cut(s,tools)
    return add_posts(s,lid_points_leg(p,heater),p)


def lid_groove(s,xmin,xmax,ymin,ymax,p):
    # 0.8 mm recess for cured RTV or compressed 1 mm silicone perimeter strip.
    outer=box(xmax-xmin-.8,ymax-ymin-.8,.8,(xmin+.4,ymin+.4,p.lid_z))
    inner=box(xmax-xmin-5.6,ymax-ymin-5.6,2,(xmin+2.8,ymin+2.8,p.lid_z-.5))
    return s.cut(outer.cut(inner))


def leg_lid(p,heater=False):
    s=box(p.duct_size,p.leg_end_y-p.leg_start_y,p.lid_thickness,
          (-p.half,p.leg_start_y,p.lid_z))
    s=lid_groove(s,-p.half,p.half,p.leg_start_y,p.leg_end_y,p)
    return cut(s,[cyl(1.7,8,(x,y,p.lid_z-1)) for x,y in lid_points_leg(p,heater)])


def bridge_body(p,side):
    xmin,xmax=(-p.width/2,-.5) if side<0 else (.5,p.width/2)
    h=p.lid_z-p.bottom_z
    s=box(xmax-xmin,p.bridge_depth,h,(xmin,p.bridge_y,p.bottom_z))
    innerx=xmin+p.wall if side<0 else xmin-1
    innerw=xmax-xmin-p.wall+1
    s=s.cut(box(innerw,p.bridge_depth-2*p.wall,h+1,(innerx,p.bridge_y+p.wall,p.bottom_z+p.wall)))
    # thicker front port flange, full height below lid
    cx=side*p.leg_spacing/2
    front=box(p.duct_size,6,h,(cx-p.half,p.bridge_y,p.bottom_z))
    front=front.cut(box(128,8,128,(cx-64,p.bridge_y-1,p.centre_z-64)))
    s=fuse(s,[front])
    # central split flange normal X
    fx=xmax-6 if side<0 else xmin
    f=box(6,p.bridge_depth,h,(fx,p.bridge_y,p.bottom_z))
    f=f.cut(box(8,p.bridge_depth-28,128,(fx-1,p.bridge_y+14,p.centre_z-64)))
    s=fuse(s,[f])
    tools=[box(128,9,128,(cx-64,p.bridge_y-1,p.centre_z-64))]
    for x in (-70,70):
        for z in (-62,62): tools.append(cyl(2.25,12,(cx+x,p.bridge_y-1,p.centre_z+z),(0,1,0)))
    for y in (p.bridge_y+8,p.back_y-8):
        for z in (p.bottom_z+14,p.lid_z-9):
            tools.append(cyl(2.25,12,(fx-1,y,z),(1,0,0)))
    tools += [cyl(2.25,10,(cx,330,p.bottom_z-1))]
    if side>0:
        # sensor cable exit on back wall; plugged gland model added separately
        tools.append(cyl(3,10,(p.width/2-35,p.back_y-7,p.bottom_z+30),(0,1,0)))
    s=cut(s,tools)
    return add_posts(s,lid_points_bridge(p,side),p)


def bridge_lid(p,side):
    xmin,xmax=(-p.width/2,-.5) if side<0 else (.5,p.width/2)
    s=box(xmax-xmin,p.bridge_depth,p.lid_thickness,(xmin,p.bridge_y,p.lid_z))
    cx=side*p.leg_spacing/2
    tools=[box(72,72,10,(cx-36,p.bridge_cy-36,p.lid_z-1))]
    tools += [cyl(1.7,10,(x,y,p.lid_z-1)) for x,y in lid_points_bridge(p,side)]
    tools += [cyl(2.25,10,(cx+x,p.bridge_cy+y,p.lid_z-1)) for x,y in bolt_pattern(80)]
    s=lid_groove(s,xmin,xmax,p.bridge_y,p.back_y,p)
    return cut(s,tools)


def cassette(p):
    # open perforated basket. Bag, not these slots, retains silica granules.
    w=p.width/2-25;d=p.bridge_depth-32;h=p.cassette_height;t=p.cassette_wall
    s=box(w,d,h)
    s=s.cut(box(w-2*t,d-2*t,h,(t,t,t)))
    holes=[]
    for x in range(10,int(w-8),14):
        holes.append(box(6,d-20,t+2,(x,10,-1)))
    for y in range(12,int(d-10),18):
        holes += [box(w+2,7,h-15,(-1,y,9))]
    # Keep solid corner strips and upper rim; across-wall side slots above are interrupted by rim.
    s=cut(s,holes)
    foot_h=p.cassette_floor_z-p.bottom_z-p.wall
    s=fuse(s,[box(8,8,foot_h,(x,y,-foot_h)) for x in (2,w-10) for y in (2,d-10)])
    return s


def support(p):
    s=box(48,40,6,(-24,-20,0))
    s=fuse(s,[box(28,28,p.bottom_z-6,(-14,-14,6))])
    return cut(s,[cyl(2.25,p.bottom_z+2,(0,0,-1)),hexprism(7.4,7,(0,0,0),'Z')])


def bin_backing(p):
    s=ring(156,156,4,116)  # replace square hole by circular aperture to retain fan corner mounts
    s=box(156,156,4,(-78,-78,0)).cut(cyl(58,6,(0,0,-1)))
    tools=[cyl(2.25,8,(x,y,-1)) for x,y in bolt_pattern(120)]
    tools += [cyl(2.25,8,(x,y,-1)) for x in (-52.5,52.5) for y in (-52.5,52.5)]
    return cut(s,tools)


def fan_adapter80(p):
    s=box(116,116,4,(-58,-58,0)).cut(cyl(39,6,(0,0,-1)))
    return cut(s,[cyl(2.25,8,(x,y,-1)) for x,y in bolt_pattern(80)]+[
        cyl(2.1,8,(x,y,-1)) for x in (-35.75,35.75) for y in (-35.75,35.75)])


def heater_hood(p):
    s=box(116,116,110,(-58,-58,9))
    s=s.cut(box(116-p.wall+1,116-2*p.wall,112,(-58+p.wall,-58+p.wall,8)))
    f=ring(116,116,6,90).translate((0,0,113))
    # roof of flange belongs to the removable lid
    f=f.cut(box(10,118,8,(58-p.wall,-59,112)))
    s=fuse(s,[f])
    for x,y in bolt_pattern(80):
        s=fuse(s,[cyl(4.5,12,(x,y,9)),
                  box(8,86 if y>0 else 30,12,(x-4,-58,9))])
    v=Valve(80,p)
    tools=[cyl(2.25,15,(x,y,8)) for x,y in bolt_pattern(80)]
    tools += [hexprism(7.4,4,(x,y,17),'Z') for x,y in bolt_pattern(80)]
    tools += [cyl(2.25,10,(x,y,112)) for x,y in bolt_pattern(80)]
    # fixed left hinge pin passes through bottom; driven journal through roof
    tools += [cyl(1.8,8,(-61,v.hy,v.hz),(1,0,0)),cyl(2.25,10,(-60,0,80),(1,0,0))]
    # screw posts for removable roof, outside swing envelope
    for y in (-50,50):
        for z in (42,100):
            s=fuse(s,[cyl(5.5,12-p.wall,(46,y,z),(1,0,0))])
            tools.append(cyl(1.25,14,(46,y,z),(1,0,0)))
    return cut(s,tools).cut(box(12,118,112,(58-p.wall,-59,8)))


def heater_hood_lid(p):
    s=box(p.wall,116-2*p.wall,110,(58-p.wall,-58+p.wall,9))
    v=Valve(80,p)
    tools=[cyl(4.3,10,(52,v.hy,v.hz),(1,0,0))]
    tools += [cyl(1.7,10,(52,y,z),(1,0,0)) for y in (-50,50) for z in (42,100)]
    return cut(s,tools)


def fan(n,thickness):
    s=box(n,n,thickness,(-n/2,-n/2,0)).cut(cyl(n*.46,thickness+2,(0,0,-1)))
    s=fuse(s,[cyl(n*.13,thickness,(0,0,0))])
    # static spider, no airflow/rotor simulation
    spokes=[]
    for a in (0,90,180,270):
        spokes.append(box(n*.40,n*.045,2,(n*.10,-n*.0225,thickness/2-1)).rotate((0,0,0),(0,0,1),a))
    return fuse(s,spokes)


def make_parts(p,mode='dry'):
    p.validate();parts={}
    def add(name,s,kind='print',material='polymer',color='#537789',design=None,orientation='as_modelled'):
        parts[name]=Part(name,s,kind,material,color,design or name,orientation)
    angle120=p.open_angle if mode=='dry' else 0
    angle80=p.open_angle if mode=='regenerate' else 0
    for side,label in ((-1,'left'),(1,'right')):
        cx=side*p.leg_spacing/2
        add(f'leg_{label}',leg_body(p,side>0).translate((cx,0,0)),design=f'leg_{label}',orientation='bottom_down')
        add(f'leg_lid_{label}',leg_lid(p,side>0).translate((cx,0,0)),design=f'leg_lid_{label}',orientation='flat')
        add(f'bridge_{label}',bridge_body(p,side),design=f'bridge_{label}',orientation='bottom_down')
        add(f'bridge_lid_{label}',bridge_lid(p,side),design=f'bridge_lid_{label}',orientation='flat')
        for y,where in ((65,'front'),(330,'rear')):
            add(f'foot_{label}_{where}',support(p).translate((cx,y,0)),design='foot',orientation='bottom_down')
        # baskets below flap sweep, removable upwards after removing bridge lids
        cw=p.width/2-25; cd=p.bridge_depth-32
        bx=-p.width/2+8 if side<0 else 17
        by=p.bridge_y+16
        add(f'cassette_{label}',cassette(p).translate((bx,by,p.cassette_floor_z)),color='#B77F42',design='cassette',orientation='bottom_down')
        add(f'bag_{label}_envelope',box(cw-9,cd-9,p.cassette_height-7,(bx+4.5,by+4.5,p.cassette_floor_z+3)),
            'purchased_reference','fabric bag + silica','#E3BF78')
        v=Valve(120,p)
        for key,(s,kind,mat,col) in v.components(angle120).items():
            add(f'box_valve_{label}_{key}',valve_to_leg(s,cx,p),kind,mat,col,f'valve120_{key}')
        backing=bin_backing(p)
        # local normal +Z -> +Y, backing at -7..-3 inside the bin
        add(f'bin_backing_{label}',valve_to_leg(backing,cx,p).translate((0,-10,0)),design='bin_backing',orientation='flat')
        add(f'fan120_{label}_envelope',valve_to_leg(fan(120,p.fan_thickness),cx,p).translate((0,-35,0)),
            'purchased_reference','120x120x25 provisional','#343F48')
        wallseal=ring(156,156,3,122)
        wallseal=points_holes(wallseal,bolt_pattern(120),4.5)
        add(f'wall_gasket_{label}',valve_to_leg(wallseal,cx,p).translate((0,-3,0)),
            'seal','silicone sheet','#5C666B','wall_gasket')
        innerseal=ring(156,156,1,122)
        innerseal=points_holes(innerseal,bolt_pattern(120),4.5)
        add(f'inner_wall_gasket_{label}',valve_to_leg(innerseal,cx,p).translate((0,-6,0)),
            'seal','silicone sheet','#5C666B','inner_wall_gasket')
        # seam gasket between valve frame and leg shell
        gs=ring(156,156,1,156-2*p.wall)
        add(f'valve_leg_gasket_{label}',valve_to_leg(gs,cx,p).translate((0,8,0)),
            'seal','silicone sheet','#5C666B','valve_leg_gasket')
        # rear leg to bridge gasket, same section as actual duct flange
        gs=ring(156,156,1,128)
        gs=points_holes(gs,[(x,z) for x in (-70,70) for z in (-62,62)],4.5)
        gs=gs.rotate((0,0,0),(1,0,0),90).rotate((0,0,0),(0,0,1),180).translate((cx,p.leg_end_y,p.centre_z))
        add(f'leg_bridge_gasket_{label}',gs,'seal','silicone sheet','#5C666B','leg_bridge_gasket')
        v=Valve(80,p)
        for key,(s,kind,mat,col) in v.components(angle80).items():
            add(f'exhaust_{label}_{key}',valve_to_outlet(s,cx,p),kind,mat,col,f'valve80_{key}')
        gs=ring(116,116,1,72)
        gs=points_holes(gs,bolt_pattern(80),4.5)
        add(f'exhaust_mount_gasket_{label}',valve_to_outlet(gs,cx,p).translate((0,0,-1)),
            'seal','silicone sheet','#5C666B','mount80_gasket')
        # lid seals: compressed thin silicone sheet, accounted by shallow gasket recess
        # These are cut templates only; lid is positioned at hard datum, sheet fits a recess added below.
    v=Valve(80,p)
    for key,(s,kind,mat,col) in v.components(angle80).items():
        add(f'heater_valve_{key}',valve_to_heater(s,p),kind,mat,col,f'valve80_{key}')
    # fan inlet adapter behind seat, circular aperture preserves standard fan mounting corners
    a=fan_adapter80(p).translate((0,0,119))
    add('heater_fan_adapter',valve_to_heater(a,p),design='heater_fan_adapter',orientation='flat')
    add('heater_fan80_envelope',valve_to_heater(fan(80,25).translate((0,0,123)),p),
        'purchased_reference','80x80x25 provisional','#343F48')
    gs=ring(116,116,1,72);gs=points_holes(gs,bolt_pattern(80),4.5)
    add('heater_mount_gasket',valve_to_heater(gs,p).translate((-1,0,0)),'seal','silicone sheet','#5C666B','heater_mount_gasket')
    add('heater_hood',valve_to_heater(heater_hood(p),p),design='heater_hood',orientation='bottom_down')
    add('heater_hood_lid',valve_to_heater(heater_hood_lid(p),p),design='heater_hood_lid',orientation='flat')
    hoodseal=ring(116,116,1,116-2*p.wall).translate((0,0,8))
    add('heater_hood_seal',valve_to_heater(hoodseal,p),'seal','silicone sheet','#5C666B','heater_hood_seal')
    h=p.centre_z+20-58
    foot=box(48,40,6,(-24,-20,0)).fuse(box(28,28,h-6,(-14,-14,6)))
    foot=cut(foot,[cyl(2.25,h+2,(0,0,-1)),hexprism(7.4,7,(0,0,0),'Z')])
    add('heater_hood_foot',foot.translate((p.width/2+1+80,p.heater_y,0)),design='heater_hood_foot',orientation='bottom_down')
    # centre split gasket: normal X
    g=ring(p.bridge_depth,156,1,p.bridge_depth-28,128)
    g=points_holes(g,[(y,z) for y in (-p.bridge_depth/2+8,p.bridge_depth/2-8) for z in (-64,65)],4.5)
    g=g.rotate((0,0,0),(1,0,0),90).rotate((0,0,0),(0,0,1),90).translate((-.5,p.bridge_cy,p.centre_z))
    add('bridge_centre_gasket',g,'seal','silicone sheet','#5C666B')
    # plugged silicone sensor gland, slit and seal around actual cables at assembly time
    gland=cyl(5,2,(p.width/2-35,p.back_y,p.bottom_z+30),(0,1,0))
    gland=fuse(gland,[cyl(3,3,(p.width/2-35,p.back_y-3,p.bottom_z+30),(0,1,0))])
    add('sensor_cable_gland',gland,'seal','silicone plug','#5C666B')
    return parts


def reference_bin(p):
    # Deliberately simple measurement reference, not a printable or dimensionally verified bin.
    s=box(p.bin_width,p.bin_depth,p.bin_height,(-p.bin_width/2,-p.bin_depth,0))
    s=s.cut(box(p.bin_width-4,p.bin_depth-4,p.bin_height,(-p.bin_width/2+2,-p.bin_depth+2,2)))
    tools=[box(120,8,120,(side*p.leg_spacing/2-60,-6,p.centre_z-60)) for side in (-1,1)]
    return cut(s,tools)
