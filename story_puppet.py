"""Deterministic layered 2D cut-out puppets; Pillow drawing and streaming FFmpeg.

No model weights or image service. Plans are inspectable and travel with shards.
Coordinates use a 960x540 stage; character rigs stay identical across scenes.
"""
import hashlib
import math
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

VERSION = 'heart-mind-puppet-v1'
COLORS = {'blue':'#467dbb','green':'#4a9c87','red':'#cc6669','yellow':'#e6b75d',
          'pink':'#d88ea8','white':'#eee9dd','purple':'#9477b9','orange':'#da925c'}


def contains(text, words):
    return any(re.search(r'\b'+re.escape(word)+r'\b',text) for word in words.split('|'))


def cast_plan(story):
    descriptions=re.split(r'\.\s*|;\s*',story.get('characters',''))
    result=[]
    for description in descriptions:
        if not description.strip():
            continue
        lower=description.lower()
        seed=int(hashlib.sha256(description.encode()).hexdigest()[:8],16)
        name=re.split(r'[,:(]',description)[0].strip()
        color=next((value for word,value in COLORS.items() if contains(lower,word)),list(COLORS.values())[seed%len(COLORS)])
        result.append(dict(name=name,description=description,shirt=color,
            skin=['#bf8868','#d49a74','#e3b28d'][seed%3],hair='#30283a',
            long_hair=contains(lower,'woman|female|wife|mother|daughter|sari|saree|girl'),
            gray=contains(lower,'elderly|grey|gray'),glasses=contains(lower,'glasses|spectacles')))
    return result[:4] or [dict(name='Lead',description='Story protagonist',shirt='#467dbb',skin='#d49a74',hair='#30283a',long_hair=False,gray=False,glasses=False)]


def scene_plan(story, slot):
    from story_format import is_short
    index=slot.get('story_scene',slot['index'])
    scene=story['scenes'][index]
    visual=story.get('visuals',{}).get(str(index),scene.get('visual',''))
    text=(visual+' '+scene.get('text','')).lower()
    world=story.get('world','').lower()
    setting='home'
    for kind,words in [('street','street|road|village|walk|bus|सड़क'),('garden','garden|park|tree|field|खेत'),
                       ('school','school|classroom|study|exam|schoolroom|स्कूल'),('shop','shop|market|store|दुकान'),
                       ('office','office|workshop|factory|काम'),('home','home|kitchen|bedroom|house|घर')]:
        if contains(text,words): setting=kind; break
    else:
        if contains(world,'village|garden|field'): setting='garden'
    action='talk'
    for kind,words in [('walk','walk|walks|walking|runs|running|arrives|leaves|सड़क'),
                       ('write','write|writes|writing|study|studies|exam'),('offer','give|gives|hands|offers|helps|help'),
                       ('reach','opens|reaches|works|repair|build|lifts')]:
        if contains(text,words): action=kind; break
    emotion='hopeful'
    if contains(text,'sad|cry|cries|tears|lonely|loss|दुख'): emotion='sad'
    elif contains(text,'worried|worry|anxious|struggle|afraid|setback'): emotion='worried'
    elif contains(text,'happy|smile|smiles|joy|celebrate|success|हँस'): emotion='happy'
    prop=None
    for kind,words in [('letter','letter|envelope|चिट्ठी'),('book','book|study|exam|किताब'),
                       ('parcel','parcel|package|box'),('plant','plant|seed|flower'),('tool','repair|tool|hammer')]:
        if contains(text,words): prop=kind;break
    cast=cast_plan(story)
    visible=[i for i,c in enumerate(cast) if c['name'].split()[0].lower() in text]
    if not visible: visible=[0]
    if contains(text,'together|family|helps|offers|hands') and len(cast)>1: visible=list(range(min(2,len(cast))))
    return dict(version=VERSION,index=slot['index'],story_scene=index,visual=visual,setting=setting,
        action=action,emotion=emotion,prop=prop,cast=cast,visible=visible[:3],
        night=contains(text,'night|evening|moon'),start=slot.get('start') if is_short(story) else None,end=slot.get('end') if is_short(story) else None)


class Stage:
    def __init__(self, plan, width=960, height=540):
        self.plan=plan
        self.size=(width,height)
        # Draw at a consistent logical resolution, then resize for the encoder.
        self.background=self.make_background()

    def make_background(self):
        p=self.plan
        image=Image.new('RGB',(960,540))
        d=ImageDraw.Draw(image)
        top,bottom=((44,53,91),(128,117,153)) if p['night'] else ((179,213,225),(251,232,202))
        for y in range(540):
            f=y/540
            d.line((0,y,960,y),fill=tuple(round(a+(b-a)*f) for a,b in zip(top,bottom)))
        setting=p['setting']
        if setting in ('garden','street'):
            d.ellipse((730,38,808,116),fill='#f8e4ad')
        if setting in ('garden','street'):
            d.polygon([(0,330),(220,215),(510,335),(710,245),(960,330),(960,540),(0,540)],fill='#92b9a6')
            d.rectangle((0,360,960,540),fill='#c1cda5')
            d.polygon([(310,540),(473,360),(560,360),(760,540)],fill='#e6c9a3')
            for x in (75,845):
                d.rounded_rectangle((x,176,x+24,395),12,fill='#98765c')
                for dx,dy,r in [(-25,0,66),(35,-25,75),(72,20,60)]:
                    d.ellipse((x+dx-r,170+dy-r,x+dx+r,170+dy+r),fill='#609b83')
            if setting=='street':
                for x in (170,650):
                    d.rounded_rectangle((x,235,x+140,375),8,fill='#e9b58e')
                    d.polygon([(x-12,240),(x+70,179),(x+152,240)],fill='#ad7180')
                    d.rectangle((x+45,288,x+85,375),fill='#69788a')
        else:
            d.rectangle((0,350,960,540),fill='#c5a58d')
            for y in range(380,540,45):d.line((0,y,960,y),fill='#b99982',width=2)
            d.rectangle((0,340,960,356),fill='#faf0dc')
            # Thick inset window, panes and quiet wall ornament.
            d.rounded_rectangle((72,70,307,294),18,fill='#f7edda')
            d.rectangle((86,84,293,280),fill='#7aafbd' if not p['night'] else '#444e79')
            d.ellipse((190,111,237,158),fill='#ffe7ad')
            d.line((190,84,190,280),fill='#f7edda',width=10)
            d.line((86,183,293,183),fill='#f7edda',width=10)
            d.rounded_rectangle((743,105,847,218),12,fill='#f6e6c9')
            d.ellipse((765,125,827,188),fill='#cb9e88')
            if setting in ('shop','office','school'):
                d.rounded_rectangle((615,235,899,357),8,fill='#9a786b')
                for x in range(637,880,46):
                    d.rounded_rectangle((x,256,x+26,337),3,fill=['#668eac','#d6ae6d','#ba7e88'][x%3])
            if setting=='school':
                d.rounded_rectangle((348,70,693,234),8,fill='#537e78',outline='#bc956e',width=9)
                for y in (110,143,176):d.line((380,y,610,y),fill='#c5dbbc',width=3)
            if setting=='home':
                d.rounded_rectangle((620,288,917,400),25,fill='#b98089')
                d.rounded_rectangle((645,273,752,355),18,fill='#cf9da2')
        # Decorative plant adds depth at the stage edge.
        d.polygon([(35,438),(103,438),(90,506),(49,506)],fill='#bd7f65')
        for x,y in [(47,386),(89,399),(63,363)]:
            d.line((69,451,x,y),fill='#4e8071',width=6)
            d.ellipse((x-18,y-12,x+18,y+12),fill='#6c9e82')
        return image

    def frame(self, t, speaking=True):
        p=self.plan
        image=self.background.copy()
        d=ImageDraw.Draw(image)
        n=len(p['visible'])
        for pos,index in enumerate(p['visible']):
            x=480 if n==1 else 370+pos*240 if n==2 else 270+pos*220
            if p['action']=='walk': x+=34*math.sin(t*.65)
            self.puppet(d,p['cast'][index],x,438,t+index*.7,speaking and pos==0, -1 if pos==n-1 and n>1 else 1, pos==0)
        if self.size!=(960,540): image=image.resize(self.size,Image.Resampling.LANCZOS)
        return image

    def puppet(self,d,c,x,y,t,speaking,facing,holds_prop):
        p=self.plan
        walk=p['action']=='walk'
        beat=math.sin(t*7) if walk else math.sin(t*2.2)
        bob=abs(beat)*4 if walk else beat*2
        y-=bob
        ink='#43394a'; skin=c['skin']; shirt=c['shirt']
        d.ellipse((x-64,443,x+64,461),fill='#a69183')
        # Separate articulated legs, knees and shoes.
        for side in (-1,1):
            hip=(x+side*19,y-66)
            knee=(x+side*22+(beat*13*side if walk else 0),y-31)
            foot=(x+side*25+(beat*23*side if walk else 0),y)
            d.line([hip,knee,foot],fill='#45485e',width=22)
            d.ellipse((foot[0]-12,foot[1]-8,foot[0]+24,foot[1]+10),fill=ink)
        if c['long_hair']:
            d.polygon([(x-34,y-170),(x+34,y-170),(x+56,y-30),(x-56,y-30)],fill=shirt,outline=ink,width=3)
        d.rounded_rectangle((x-44,y-178,x+44,y-62),22,fill=shirt,outline=ink,width=3)
        d.rounded_rectangle((x+25,y-157,x+38,y-75),6,fill=shirt)
        if c['long_hair']:
            d.polygon([(x+24,y-174),(x+43,y-159),(x-25,y-60),(x-42,y-72)],fill='#dfc58a')
            d.line((x+24,y-172,x-42,y-72),fill='#f6e1ac',width=3)
        d.polygon([(x-18,y-177),(x,y-148),(x+18,y-177)],fill='#f6e6ca')
        d.line((x,y-148,x,y-76),fill='#eee0ce',width=2)
        for yy in (y-131,y-111):d.ellipse((x-2,yy-2,x+2,yy+2),fill=ink)
        # Arms rotate about shoulder and elbow joints, independently of torso.
        for side in (-1,1):
            shoulder=(x+side*39,y-159)
            gesture=math.sin(t*3+side)*12
            if p['action'] in ('offer','reach','write') and side==facing:
                elbow=(x+side*65,y-121)
                hand=(x+side*(96+gesture*.4),y-145+gesture*.4)
            else:
                elbow=(x+side*(56+beat*3),y-116)
                hand=(x+side*(56+gesture*.5),y-78+(beat*13*side if walk else gesture*.3))
            d.line([shoulder,elbow],fill=ink,width=23)
            d.line([shoulder,elbow],fill=shirt,width=19)
            d.line([elbow,hand],fill=skin,width=15)
            d.ellipse((hand[0]-9,hand[1]-9,hand[0]+9,hand[1]+9),fill=skin,outline=ink,width=2)
            if side==facing and p['prop'] and holds_prop:self.prop(d,hand[0],hand[1],p['prop'])
        d.rectangle((x-12,y-196,x+12,y-167),fill=skin)
        hair='#b5b0b0' if c['gray'] else c['hair']
        if c['long_hair']: d.rounded_rectangle((x-53,y-291,x+53,y-172),32,fill=hair)
        for side in (-1,1):d.ellipse((x+side*47-10,y-245,x+side*47+10,y-216),fill=skin,outline=ink,width=2)
        d.rounded_rectangle((x-48,y-285,x+48,y-185),39,fill=skin,outline=ink,width=3)
        d.pieslice((x-51,y-300,x+51,y-211),180,360,fill=hair)
        d.ellipse((x-49,y-278,x-25,y-235),fill=hair)
        if c['long_hair']:
            d.ellipse((x+31,y-269,x+43,y-257),fill='#e7bd72')
            d.ellipse((x-3,y-261,x+3,y-255),fill='#b65561')
        # Brief, deterministic blinks; brows and mouth convey scene emotion.
        blink=(t%4.3)<.14
        for side in (-1,1):
            xx=x+side*20
            if blink:d.line((xx-7,y-241,xx+7,y-241),fill=ink,width=3)
            else:
                d.ellipse((xx-8,y-249,xx+8,y-232),fill='#fff8ed')
                d.ellipse((xx-3+facing*2,y-247,xx+3+facing*2,y-234),fill=ink)
            worried=p['emotion'] in ('worried','sad')
            d.line((xx-8,y-258+(side*3 if worried else 0),xx+8,y-258-(side*3 if worried else 0)),fill=hair,width=3)
            d.ellipse((xx-11,y-226,xx+5,y-219),fill='#d58e81')
            if c['glasses']:d.ellipse((xx-13,y-253,xx+13,y-228),outline=ink,width=2)
        if c['glasses']:d.line((x-7,y-243,x+7,y-243),fill=ink,width=2)
        d.line((x+2,y-238,x-2,y-223,x+5,y-222),fill='#aa725d',width=2)
        opening=(.5+.5*math.sin(t*19))*9 if speaking else 0
        if opening>3:d.ellipse((x-9,y-212,x+9,y-209+opening),fill='#6d3f4b')
        elif p['emotion'] in ('sad','worried'):d.arc((x-11,y-214,x+11,y-200),190,350,fill=ink,width=3)
        else:d.arc((x-13,y-219,x+13,y-201),5,175,fill=ink,width=3)

    @staticmethod
    def prop(d,x,y,kind):
        if kind=='letter':
            d.rectangle((x-23,y-18,x+23,y+12),fill='#fff0cf',outline='#997762',width=2)
            d.line((x-23,y-18,x,y,x+23,y-18),fill='#b8987a',width=2)
        elif kind=='book':
            d.rounded_rectangle((x-22,y-24,x+22,y+15),3,fill='#dfb56c',outline='#785c58',width=2)
            d.line((x,y-22,x,y+14),fill='#fff2da',width=3)
        elif kind=='parcel':
            d.rectangle((x-24,y-24,x+24,y+17),fill='#c99666',outline='#765b51',width=2)
            d.rectangle((x-4,y-24,x+4,y+17),fill='#edd7a7')
        elif kind=='plant':
            d.polygon([(x-15,y),(x+15,y),(x+10,y+23),(x-10,y+23)],fill='#b87661')
            d.line((x,y,x,y-35),fill='#4d806b',width=4)
            d.ellipse((x-21,y-35,x,y-20),fill='#679778')
            d.ellipse((x,y-43,x+22,y-27),fill='#679778')
        else:
            d.line((x,y+20,x,y-22),fill='#99745d',width=7)
            d.rounded_rectangle((x-18,y-28,x+18,y-15),3,fill='#73818c')


def encode(plan, target, frames, fps, width, height):
    """Stream frames, with bounded disk use and actionable encoder failures."""
    stage=Stage(plan,width,height)
    # Animate on twos: a common cut-out aesthetic, half the drawing cost at 25fps.
    with tempfile_log() as errors:
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
            '-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264',
            '-threads','4','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(target)]
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=errors)
        try:
            data=None
            for frame in range(frames):
                if frame%2==0:data=stage.frame(frame/fps).tobytes()
                process.stdin.write(data)
            process.stdin.close()
            if process.wait()!=0:raise RuntimeError('Puppet FFmpeg encoding failed')
        except BaseException as error:
            if process.stdin and not process.stdin.closed:process.stdin.close()
            process.kill();process.wait()
            errors.seek(0)
            detail=errors.read().decode(errors='replace')[-3000:]
            raise RuntimeError(f'Puppet render failed: {detail}') from error


def tempfile_log():
    import tempfile
    return tempfile.TemporaryFile()
