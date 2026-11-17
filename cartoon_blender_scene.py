"""Headless Blender scene builder for Heart and Mind."""
import json
import math
import os
from pathlib import Path
from random import Random

import bpy
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rng = Random(18)
shot = json.loads(os.environ['HEART_STORYBOOK_SHOT'])
FPS = 12.5
scene.frame_end = shot['frames']
place = shot['place']
outside = place == 'outdoors'
prop = shot['prop']


def color(name, rgb, rough=.48):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    node = mat.node_tree.nodes['Principled BSDF']
    node.inputs['Base Color'].default_value = (*rgb, 1)
    node.inputs['Roughness'].default_value = rough
    mat.diffuse_color = (*rgb, 1)
    return mat


def mesh(name, mat, loc, size, *, roundness=0):
    if roundness:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        obj = bpy.context.object
        obj.dimensions = size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        bevel = obj.modifiers.new('Rounded edges','BEVEL')
        bevel.width = roundness
        bevel.segments = 4
        obj.modifiers.new('Soft normals','WEIGHTED_NORMAL')
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc)
        obj = bpy.context.object
        obj.scale = size
        for face in obj.data.polygons:
            face.use_smooth = True
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def key(obj, field, frame, value):
    setattr(obj,field,value)
    obj.keyframe_insert(data_path=field,frame=frame)


def empty(name, loc):
    obj = bpy.data.objects.new(name,None)
    scene.collection.objects.link(obj)
    obj.location = loc
    return obj


def local(obj, parent):
    obj.parent = parent
    return obj


def rectangle(name, mat, xyz, xyz_size, bevel=.03):
    return mesh(name,mat,xyz,xyz_size,roundness=bevel)


skin_a = color('Mira charcoal face',(.017,.014,.031),.42)
skin_b = color('Theo charcoal face',(.023,.014,.025),.44)
black = color('Soft dark ink',(.033,.018,.033))
hair_a = color('Mira dark bob',(.10,.035,.083))
hair_b = color('Theo brown curls',(.22,.079,.024))
cream = color('Cream canvas',(.92,.82,.65))
white = color('Luminous ivory expressions',(.98,.94,.82))
face_light=white.node_tree.nodes.get('Principled BSDF')
face_light.inputs['Emission Color'].default_value=(1,.94,.80,1)
face_light.inputs['Emission Strength'].default_value=.85
teal = color('Mira teal jacket',(.006,.37,.54))
amber = color('Theo amber vest',(.95,.44,.012))
navy = color('Theo navy trousers',(.038,.084,.16))
brown = color('Mira brown trousers',(.20,.096,.048))
coral = color('Coral sock',(.88,.096,.14))
cyan = color('Blue sock',(.016,.49,.72))
pale_pink = color('Coral stripe',(1,.52,.45))
pale_blue = color('Blue stripe',(.44,.82,.88))
wood = color('Honey oak',(.40,.19,.062))
darkwood = color('Walnut',(.13,.069,.031))
wall = color('Periwinkle wall',(.065,.035,.12))
panel = color('Deep blue wall panel',(.023,.013,.055))
rug = color('Peach rug',(.38,.10,.18))
leaf = color('Plant',(.07,.37,.15))
soil = color('Plant pot',(.72,.23,.12))
glass = color('Evening window',(.065,.18,.36))
# Saturated purple-to-ember dusk beyond the window.
tree = glass.node_tree
glass_shader = tree.nodes.get('Principled BSDF')
coordinates = tree.nodes.new('ShaderNodeTexCoord')
axis = tree.nodes.new('ShaderNodeSeparateXYZ')
gradient = tree.nodes.new('ShaderNodeValToRGB')
gradient.color_ramp.elements[0].position = .06
gradient.color_ramp.elements[0].color = (.91,.17,.032,1)
gradient.color_ramp.elements[1].position = .92
gradient.color_ramp.elements[1].color = (.075,.023,.22,1)
gradient.color_ramp.elements.new(.46).color = (.40,.057,.22,1)
tree.links.new(coordinates.outputs['Generated'],axis.inputs[0])
tree.links.new(axis.outputs['Z'],gradient.inputs[0])
tree.links.new(gradient.outputs['Color'],glass_shader.inputs['Base Color'])
tree.links.new(gradient.outputs['Color'],glass_shader.inputs['Emission Color'])
glass_shader.inputs['Emission Strength'].default_value = .80
light_panel = color('Lamp shade',(1,.63,.23))
lamp_bsdf = light_panel.node_tree.nodes['Principled BSDF']
lamp_bsdf.inputs['Emission Color'].default_value = (1,.47,.13,1)
lamp_bsdf.inputs['Emission Strength'].default_value = .5

if outside:
    meadow=color('Twilight grass',(.075,.19,.085))
    rectangle('Ground',meadow,(0,4,-.13),(24,24,.26),.1)
    rectangle('Garden path',wood,(0,1,-.006),(4.5,19,.04),.018)
    for i in range(12):
        x = -8+i*1.4
        y = 4.5+rng.random()*6
        z = 1.8+rng.random()*1.1
        rectangle('Tree trunk',darkwood,(x,y,z/2),(.19,.2,z),.05)
        mesh('Rounded tree canopy',leaf,(x,y,z),(.83,.65,.93))
else:
    rectangle('Floor',wood,(0,2,-.13),(15,12,.26),.08)
    rectangle('Rug',rug,(0,-.12,.014),(6.6,3.2,.026),.012)
    rectangle('Back wall',wall,(0,3.8,2.4),(15,.24,5.1),.04)
    rectangle('Wood paneling',panel,(0,3.61,.62),(15,.12,1.20),.04)
    rectangle('Window recess',panel,(.1,3.56,2.7),(3.8,.12,2.7),.08)
    rectangle('Blue window',glass,(.1,3.47,2.69),(3.52,.08,2.42),.035)
    for x in (-1.68,.1,1.86):
        rectangle('Window frame',cream,(x,3.39,2.69),(.095,.12,2.49))
    rectangle('Window crossbar',cream,(.1,3.38,2.67),(3.61,.12,.086))
    for i in range(13):
        x = -1.6+i*.27
        height = rng.uniform(.28,.90)
        rectangle('City silhouette',panel,(x,3.37,1.51+height*.5),(.21,.035,height),.012)
    for x,z in ((-3.4,2.55),(3.3,2.8)):
        rectangle('Picture frame',darkwood,(x,3.46,z),(.78,.09,.86),.04)
        rectangle('Picture paper',pale_pink,(x,3.40,z),(.65,.045,.73),.015)
        mesh('Picture circle',amber,(x,3.373,z),(.22,.02,.22))
    
    rectangle('Side table',darkwood,(3.2,2.3,.59),(1.23,.93,.12),.06)
    rectangle('Lamp pole',darkwood,(3.2,2.3,.97),(.08,.08,.73))
    mesh('Lamp shade',light_panel,(3.2,2.3,1.43),(.37,.35,.31))
    mesh('Plant pot',soil,(-3.5,2.38,.25),(.37,.34,.27))
    for i in range(8):
        angle = i*math.tau/8
        frond = mesh('Plant leaf',leaf,(-3.5+.22*math.cos(angle),2.38+.20*math.sin(angle),.62+rng.random()*.3),
                     (.12,.09,.35))
        frond.rotation_euler.y = .65*math.cos(angle)
        frond.rotation_euler.x = .65*math.sin(angle)
    if place == 'kitchen':
        for i in range(5):
            rectangle('Kitchen cabinet',panel,(-2.6+i*1.25,2.67,.53),(1.12,.55,1.05),.06)
            rectangle('Copper handle',amber,(-2.6+i*1.25,2.345,.77),(.21,.04,.045),.015)
        rectangle('Countertop',cream,(0,2.65,1.10),(6.6,.69,.11),.035)
    elif place == 'bedroom':
        rectangle('Bed frame',darkwood,(2.7,2.05,.24),(1.8,2.35,.35),.09)
        rectangle('Quilt',coral,(2.7,2.05,.49),(1.8,2.35,.24),.09)
        rectangle('Pillow',cream,(2.7,2.81,.65),(1.48,.55,.20),.085)
    elif place == 'entry':
        rectangle('Front door',darkwood,(2.52,3.33,1.40),(1.54,.14,2.74),.065)
        mesh('Door knob',amber,(2.05,3.19,1.37),(.063,.059,.067))
show_table = bool(prop) and prop != 'ball'
if show_table:
    for x in (-.97,.97):
        for y in (-.49,.47):
            rectangle('Table leg',darkwood,(x,y,.47),(.14,.14,.94))
    rectangle('Table top',wood,(0,0,1.02),(2.40,1.43,.16),.085)
    if prop in ('sock','cup'):
        rectangle('Table runner',cream,(0,.03,1.125),(1.76,.92,.061),.028)


def person(name, x, jacket, trousers, skin, hair, bob):
    y = .18
    mesh(name+' torso',jacket,(x,y,1.49),(.36,.24,.42))
    rectangle(name+' jacket seam',cream,(x,y-.229,1.47),(.024,.021,.43),.008)
    mesh(name+' neck',skin,(x,y,1.91),(.12,.11,.14))
    for side in (-1,1):
        mesh(name+(' leg left' if side<0 else ' leg right'),trousers,(x+side*.145,y,.68),(.126,.141,.56))
        mesh(name+(' shoe left' if side<0 else ' shoe right'),black,(x+side*.15,y-.10,.155),(.154,.213,.109))
    head = empty(name+' head rig',(x,y-.02,2.19))
    local(mesh(name+' face',skin,(0,-.055,0),(.347,.269,.38)),head)
    local(mesh(name+' hair crown',hair,(0,.047,.15),(.37,.286,.32)),head)
    if bob:
        local(mesh('Mira raised hood',jacket,(0,.092,.024),(.415,.316,.429)),head)
        for side in (-1,1):
            local(mesh('Mira bob',hair,(side*.30,.006,-.085),(.084,.215,.25)),head)
        fringe = local(mesh('Mira fringe',hair,(-.09,-.171,.224),(.255,.15,.123)),head)
        fringe.rotation_euler.y = -.35
    else:
        for i in range(11):
            angle = i*math.tau/11
            local(mesh('Theo curl',hair,(.25*math.sin(angle),-.06+.15*math.cos(angle),.23+.065*math.cos(angle)),
                       (.125,.134,.136)),head)
    eyebrows=[]
    for side in (-1,1):
        local(mesh(name+' eye',white,(side*.111,-.286,.034),(.061,.027,.084)),head)
        eyebrows.append(local(mesh(name+' brow',white,(side*.111,-.291,.142),(.079,.023,.026)),head))
    mouth = local(mesh(name+' mouth',white,(0,-.283,-.134),(.083,.023,.022)),head)
    arms=[]
    for i in range(2):
        upper=mesh(name+' upper sleeve',jacket,(0,0,0),(.09,.09,.1))
        lower=mesh(name+' forearm',jacket,(0,0,0),(.074,.074,.1))
        palm=mesh(name+' hand',skin,(0,0,0),(.082,.073,.079))
        arms.append((upper,lower,palm))
    return head, eyebrows, mouth, arms


mira = person('Mira',-1.48,teal,brown,skin_a,hair_a,True)
theo = person('Theo',1.48,amber,navy,skin_b,hair_b,False)


def sock(name, hue, stripe):
    root = empty(name,(0,0,0))
    local(rectangle(name+' ankle',hue,(0,0,-.14),(.21,.10,.29),.05),root)
    local(rectangle(name+' toe',hue,(.085,-.017,-.285),(.36,.13,.13),.06),root)
    for z in (-.045,-.085):
        local(rectangle(name+' cuff stripe',stripe,(0,-.009,z),(.214,.105,.023),.01),root)
    return root


def prop_model(kind):
    if kind == 'sock':
        return sock('Story sock',cyan,pale_blue)
    root = empty(kind,(0,0,0))
    if kind == 'ball':
        local(mesh('Ball',coral,(0,0,-.14),(.15,.15,.15)),root)
        local(mesh('Ball stripe',cream,(0,-.139,-.14),(.072,.013,.134)),root)
    elif kind == 'cup':
        local(rectangle('Mug',cyan,(0,0,-.115),(.22,.19,.23),.052),root)
        local(mesh('Mug handle',pale_blue,(.12,0,-.10),(.071,.045,.082)),root)
    elif kind in ('book','phone','key'):
        dimensions = {'book':(.34,.085,.23),'phone':(.18,.045,.30),'key':(.095,.037,.19)}[kind]
        local(rectangle(kind,amber if kind=='key' else navy,(0,0,-.13),dimensions,.023),root)
        local(rectangle('Inset',cream if kind=='book' else cyan,(0,-dimensions[1]*.55,-.13),
                        (dimensions[0]*.74,.014,dimensions[2]*.72),.006),root)
    elif kind == 'bag':
        local(rectangle('Bag',coral,(0,0,-.15),(.34,.19,.31),.067),root)
        local(rectangle('Bag clasp',amber,(0,-.105,-.14),(.084,.02,.067),.012),root)
    else:
        local(rectangle('Box',amber,(0,0,-.14),(.32,.24,.25),.034),root)
    return root


item = prop_model(prop) if prop else None


def ease(a,b,t):
    v=max(0,min(1,(t-a)/(b-a)))
    return v*v*(3-2*v)


def linebetween(obj,a,b,frame,r):
    delta=b-a
    key(obj,'location',frame,(a+b)/2)
    key(obj,'rotation_euler',frame,delta.to_track_quat('Z','Y').to_euler())
    key(obj,'scale',frame,(r,r,delta.length/2+.04))


def move_arm(parts, shoulder, hand, frame):
    elbow=shoulder.lerp(hand,.49)+Vector((0,.055,-.22))
    upper,lower,palm=parts
    linebetween(upper,shoulder,elbow,frame,.094)
    linebetween(lower,elbow,hand,frame,.080)
    key(palm,'location',frame,hand)


for frame in range(1,scene.frame_end+1):
    t=(frame-1)/max(1,scene.frame_end-1)
    seconds=frame/FPS
    action=shot['action']
    handles_item = item is not None and action in ('handle','pass','approach_ball')
    rest = {'sock':.35,'ball':.29,'cup':.23,'bag':.31,'box':.265}.get(prop,.29)
    base = Vector((0,-.23,(1.10 if show_table else .02)+rest))
    hand_positions={}
    for name, actor, home, side in (('mira',mira,-1.48,1),('theo',theo,1.48,-1)):
        head,brows,mouth,arms=actor
        speaking=shot['speaker']==name
        emphasis=ease(.15,.34,t)*(1-ease(.72,.95,t))
        emotion={'surprised':1,'worried':.8,'amused':.68,'curious':.53,
                 'relieved':.4,'thoughtful':.35}.get(shot['emotion'],.4)
        mood=emphasis*emotion*(1 if speaking or shot['speaker']=='narrator' else .72)
        travel=0
        if action in ('approach_friend','follow_friend','approach_ball'):
            walk=ease(.07,.50,t)
            travel=(side*.65 if action!='follow_friend' else .60)*walk
            if action!='follow_friend' and name=='theo':
                travel=0
        stride=math.sin(seconds*9)*.14 if abs(travel)>.01 and .08<t<.50 else 0
        for leg in ('leg left','leg right','shoe left','shoe right'):
            actor_part=bpy.data.objects[name.title()+' '+leg]
            direction=-1 if leg.endswith('left') else 1
            is_shoe=leg.startswith('shoe')
            key(actor_part,'location',frame,(home+direction*.145+travel,
                (.08 if is_shoe else .18)+direction*stride,.155 if is_shoe else .68))
        key(bpy.data.objects[name.title()+' torso'],'location',frame,(home+travel,.18,1.49))
        key(bpy.data.objects[name.title()+' jacket seam'],'location',frame,(home+travel,-.049,1.47))
        key(bpy.data.objects[name.title()+' neck'],'location',frame,(home+travel,.18,1.91))
        key(head,'location',frame,(home+travel,.16,2.19+abs(stride)*.18))
        key(head,'rotation_euler',frame,(.12*mood,side*.09*mood,side*(.15+.17*mood)))
        jaw=.026*abs(math.sin(seconds*math.tau*4.6)) if speaking and .07<t<.93 else 0
        key(mouth,'scale',frame,(.087,.024,.020+.047*mood+jaw))
        for i,brow in enumerate(brows):
            direction=-1 if i==0 else 1
            key(brow,'location',frame,(direction*.111,-.291,.142+mood*(.039 if i==0 else .024)))
            key(brow,'rotation_euler',frame,(0,direction*.32*mood,0))
        near=Vector((home+travel+side*.37,-.14,1.30+(.24 if speaking else .09)*emphasis))
        far=Vector((home+travel-side*.28,.03,1.23))
        if handles_item and name==shot['holder']:
            grip=Vector((home+travel+side*.56,-.32,1.55))
            near=near.lerp(base,ease(.13,.37,t)).lerp(grip,ease(.40,.55,t))
        if handles_item and action=='pass':
            transfer=Vector((0,-.30,1.58))
            near=near.lerp(transfer,ease(.53,.68,t)*(1-ease(.72,.91,t)))
        hand_positions[name]=near
        move_arm(arms[0],Vector((home+travel+side*.26,.13,1.72)),near,frame)
        move_arm(arms[1],Vector((home+travel-side*.26,.15,1.72)),far,frame)
    if item:
        owner=shot['holder']
        if action=='pass' and t>=.70:
            owner='theo' if owner=='mira' else 'mira'
        position=hand_positions[owner] if handles_item and t>=.38 else base
        key(item,'location',frame,position)
        key(item,'rotation_euler',frame,(.26*(1-ease(.37,.53,t)),.14*math.sin(seconds*3)*ease(.37,.53,t),0))


def camera(name,frame,position,target,lens):
    bpy.ops.object.camera_add(location=position)
    camera=bpy.context.object
    camera.name=name
    camera.data.lens=lens
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    marker=scene.timeline_markers.new(name,frame=frame)
    marker.camera=camera
    return camera


wide = ((.18,-7.05,2.92),(0,.12,1.48),42)
mira_view = ((-2.30,-5.42,2.62),(-.38,.08,1.83),44)
theo_view = ((2.30,-5.42,2.62),(.38,.08,1.83),44)
focus = {'mira':mira_view,'theo':theo_view}.get(shot['speaker'],wide)
cover_view = ((-.48,-6.15,2.49),(-.07,.10,1.99),46)
opening = cover_view if shot['cover'] else wide if shot['action'] in (
    'approach_friend','follow_friend','approach_ball') else focus
scene.camera=camera('Establish action',1,*opening)
if not shot['cover'] and scene.frame_end >= 60:
    next_view = focus if opening==wide and focus!=wide else wide
    if opening==next_view:
        next_view = (mira_view,theo_view)[shot['index']%2]
    camera('Reaction or reveal',round(scene.frame_end*.58),*next_view)

scene.world=bpy.data.worlds.new('Storybook lighting world')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.14,.043,.24,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.18
lights = (
    ('Warm key',(-3,-4,5),575,4,(1,.61,.32)),
    ('Soft fill',(3,-3,3),135,4,(.42,.56,1)),
    ('Window rim',(.2,2.9,4),1120,2.4,(1,.32,.085)),
    ('Cyan edge',(-3.3,1.05,2.9),560,2.5,(.075,.52,1)),
    ('Purple bounce',(0,1,3.6),100,4,(.40,.14,1)),
    ('Amber practical',(3.2,1.8,2.25),168,1.2,(1,.43,.14)),
)
if shot['cover']:
    lights = (
        ('Warm key',(-2.5,-4.8,4.25),470,3.0,(1,.69,.40)),
        ('Violet fill',(3.4,-3,3.6),95,3.0,(.43,.35,1)),
        ('Golden rim',(1.25,1.50,3.4),1250,1.2,(1,.30,.055)),
        ('Edge cyan',(-3.3,.30,2.8),615,1.85,(.055,.53,1)),
        ('Purple backdrop',(2.5,1.35,3.20),236,2.5,(.44,.13,1)),
    )
    gradient.color_ramp.elements[0].color = (.98,.19,.024,1)
    gradient.color_ramp.elements[-1].color = (.043,.011,.115,1)
    glass_shader.inputs['Emission Strength'].default_value=.62
for name,pos,energy,size,hue in lights:
    bpy.ops.object.light_add(type='AREA',location=pos)
    obj=bpy.context.object
    obj.name=name
    obj.data.energy=energy
    obj.data.shape='DISK'
    obj.data.size=size
    obj.data.color=hue
    obj.rotation_euler=(Vector((0,0,1.2))-obj.location).to_track_quat('-Z','Y').to_euler()
scene.render.engine=os.environ.get('HEART_BLENDER_ENGINE','CYCLES')
if scene.render.engine=='CYCLES':
    scene.cycles.samples = 12 if shot['cover'] else 4
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=3
else:
    scene.eevee.taa_render_samples=24
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.render.resolution_x,scene.render.resolution_y=shot['resolution']
scene.render.fps=25
scene.render.fps_base=2
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.use_nodes=True
nodes=scene.node_tree.nodes
links=scene.node_tree.links
layers=nodes.get('Render Layers')
output=nodes.get('Composite')
glare=nodes.new('CompositorNodeGlare')
glare.glare_type='FOG_GLOW'
glare.inputs['Threshold'].default_value=1.35
links.new(layers.outputs['Image'],glare.inputs['Image'])
links.new(glare.outputs['Image'],output.inputs['Image'])
scene.render.filepath=shot['output']
scene.frame_set(max(1,round(scene.frame_end*.67)) if shot['cover'] else 1)
bpy.ops.render.render(write_still=True) if shot['cover'] else bpy.ops.render.render(animation=True)
