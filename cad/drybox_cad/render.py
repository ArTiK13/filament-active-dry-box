"""Render ONLY meshes tessellated from delivered exact geometry."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/filament-mpl')
import numpy as np
import pyvista as pv
from .model import make_parts, Valve, reference_bin


def mesh(s):
    v,f=s.tessellate(.18,.15)
    return pv.PolyData(np.array([a.toTuple() for a in v]),np.array([[3,*t] for t in f],dtype=np.int64).ravel()).clean()


def setup(title):
    v=pv.Plotter(off_screen=True,window_size=(1800,1250))
    v.set_background('#F0F3F5')
    v.enable_anti_aliasing('ssaa')
    v.add_text(title,font_size=17,color='#233849',position='upper_left')
    v.add_text('PARAMETRIC PROTOTYPE v1  |  mm  |  component sizes provisional',font_size=10,color='#536673',position='lower_left')
    return v


def draw(v,part,shape=None,opacity=1):
    if part.kind=='seal': opacity*=.8
    v.add_mesh(mesh(shape or part.shape),color=part.color,opacity=opacity,
               smooth_shading=False,specular=.15,ambient=.28,diffuse=.72)


def finish(v,path,camera,focus,scale=None):
    v.camera_position=[camera,focus,(0,0,1)]
    v.camera.parallel_projection=True
    if scale: v.camera.parallel_scale=scale
    else: v.reset_camera()
    v.show(screenshot=str(path),auto_close=True)


def render_all(p,out):
    out.mkdir(parents=True,exist_ok=True)
    parts=make_parts(p,'dry')
    v=setup('01  Closed-loop drying / storage')
    for item in parts.values(): draw(v,item)
    v.add_floor('-z',color='#DCE3E8',lighting=False,pad=.18)
    finish(v,out/'assembly_dry.png',(750,-820,690),(0,180,110),350)

    v=setup('02  Service cutaway: two removable silica bags + open air channel')
    for name,item in parts.items():
        if name.startswith('leg_lid') or name.startswith('bridge_lid') or name.startswith('exhaust_') or name=='heater_hood_lid': continue
        draw(v,item,opacity=.85 if 'bag_' in name else 1)
    path=[(-p.leg_spacing/2,-15,135),(-p.leg_spacing/2,205,145),
          (-p.leg_spacing/2,p.bridge_cy,150),(p.leg_spacing/2,p.bridge_cy,150),
          (p.leg_spacing/2,185,145),(p.leg_spacing/2,0,135)]
    for a,b in zip(path[:-1],path[1:]):
        a=np.array(a);b=np.array(b)
        v.add_mesh(pv.Arrow(start=a,direction=b-a,scale=np.linalg.norm(b-a)*.74,shaft_radius=.009,tip_radius=.035),color='#37A7B0')
    finish(v,out/'cutaway.png',(690,-720,850),(0,185,105),355)

    v=setup('03  Regeneration: bin valves shut, heater inlet + both exhausts open')
    regen=make_parts(p,'regenerate')
    for item in regen.values(): draw(v,item)
    for x in (-p.leg_spacing/2,p.leg_spacing/2):
        v.add_mesh(pv.Arrow(start=(x,p.bridge_cy,258),direction=(0,0,1),scale=70,shaft_radius=.025,tip_radius=.08),color='#D46A44')
    finish(v,out/'assembly_regeneration.png',(800,760,710),(0,200,120),355)

    v=setup('04  Valve detail: CLOSED (left), OPEN 82 deg (right)')
    from .model import Part
    valve=Valve(120,p)
    for i,angle in enumerate((0,p.open_angle)):
        for name,(s,kind,material,color) in valve.components(angle).items():
            draw(v,Part(name,s.translate((i*280,0,0)),kind,material,color,name))
    finish(v,out/'valve_detail.png',(650,-550,430),(155,15,60),275)

    v=setup('05  Estimated bin reference 600 x 400 x 350 / confirm before cutting')
    for item in parts.values(): draw(v,item)
    v.add_mesh(mesh(reference_bin(p)),color='#A5B6C0',opacity=.14)
    # Three 200 mm spool envelopes provide scale only, no claimed bin measurement.
    from .model import cyl
    for x in (-165,0,165):
        spool=cyl(100,62,(x,-255,130),(1,0,0)).cut(cyl(26,64,(x-1,-255,130),(1,0,0)))
        v.add_mesh(mesh(spool),color='#C6AC82',opacity=.45)
    finish(v,out/'bin_layout.png',(1000,1000,800),(0,-20,155),520)

    v=setup('06  Access: remove bridge lids, then lift out the two baskets')
    for name,item in parts.items():
        shape=item.shape
        if name.startswith('bridge_lid') or name.startswith('exhaust_'): shape=shape.translate((0,0,160))
        elif name=='heater_hood_lid': shape=shape.translate((0,0,90))
        elif name.startswith('cassette_') or name.startswith('bag_'): shape=shape.translate((0,0,80))
        draw(v,item,shape)
    finish(v,out/'service_exploded.png',(820,-720,830),(0,190,205),400)
