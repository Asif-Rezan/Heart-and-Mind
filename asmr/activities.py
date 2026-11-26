"""Eight distinct ASMR actions, each with its own geometry and contact-sound clock.

The scene is laid out natively in either aspect ratio. Portrait is never stretched
or blindly cropped from landscape. All coordinates below are stage-relative.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal
from scipy.io import wavfile
from .plan import PALETTES, ACTIVITIES

FORMATS={'landscape':(1280,720),'portrait':(720,1280)}
SR=48000

def ease(x):
 x=max(0,min(1,x));return x*x*(3-2*x)

class Scene:
 def __init__(self,recipe,orientation='landscape'):
  self.recipe=recipe;self.activity=recipe['activity'];self.material=recipe['material']
  if self.material not in ACTIVITIES[self.activity]:raise ValueError('Unsupported activity/material')
  self.size=FORMATS[orientation];self.cx=self.size[0]/2;self.cy=self.size[1]*.56
  self.scale=1.16 if orientation=='landscape' else 1.0
  self.colors=[tuple(bytes.fromhex(c)) for c in PALETTES[recipe['palette']]]
  self.duration=recipe['seconds'];self.count=recipe['cycles'];self.cycle=(self.duration-1)/self.count
  self.rng=np.random.default_rng(recipe['seed'])
  self.particles=self.rng.uniform(0,1,(180,4))
  w,h=self.size;y=np.linspace(0,1,h)[:,None,None]
  top=np.array([244,231,228]);bottom=np.array([222,212,234])
  bg=np.broadcast_to(top*(1-y)+bottom*y,(h,w,3)).astype('uint8').copy()
  self.bg=Image.fromarray(bg)
  d=ImageDraw.Draw(self.bg)
  for i in range(13):
   yy=int(h*.30+i*h*.065);d.line((0,yy,w,yy+20),fill=(214,199,211),width=1)
  try:self.font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',23)
  except OSError:
   try:self.font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',23)
   except OSError:self.font=ImageFont.load_default(size=23)
  title=recipe['label'];box=d.textbbox((0,0),title,font=self.font)
  d.text(((w-(box[2]-box[0]))/2,24),title,font=self.font,fill=(95,76,106))

 def point(self,x,y):return (self.cx+x*self.scale,self.cy+y*self.scale)
 def box(self,coords):
  x0,y0,x1,y1=coords;return (*self.point(x0,y0),*self.point(x1,y1))
 def ellipse(self,d,box,fill,outline=None,width=1):d.ellipse(self.box(box),fill=fill,outline=outline,width=width)
 def rect(self,d,box,fill,radius=12,outline=None,width=1):d.rounded_rectangle(self.box(box),radius=radius,fill=fill,outline=outline,width=width)
 def line(self,d,points,fill,width=2):d.line([self.point(*p) for p in points],fill=fill,width=width,joint='curve')
 def poly(self,d,points,fill):d.polygon([self.point(*p) for p in points],fill=fill)
 def color(self,i):
  pattern=self.recipe['pattern']
  if pattern=='solid':return self.colors[0]
  return self.colors[(i//2 if pattern=='layered' else i)%len(self.colors)]
 def clock(self,t):
  progress=max(0,min(self.count-1e-8,(t-.5)/self.cycle))
  return int(progress),progress%1
 def event_times(self):
  phase={'cutting':.30,'pressing':.5,'pouring':.2,'tapping':.5,'brushing':.15,'crinkling':.5,'raking':.15,'ripples':.35}[self.activity]
  return [.5+(i+phase)*self.cycle for i in range(self.count)]

 def render(self,t):
  image=self.bg.copy();d=ImageDraw.Draw(image);k,u=self.clock(t)
  self.ellipse(d,(-325,125,325,200),(194,179,198))
  getattr(self,'draw_'+self.activity)(d,k,u,t)
  fade=min(ease(t/.15),ease((self.duration-t)/.15))
  return image if fade>=1 else Image.fromarray((np.asarray(image)*fade).astype('uint8'))

 def draw_cutting(self,d,k,u,t):
  # Separate slab and detached slices, with a descending blade and contact seam.
  width=400/self.count;edge=200-k*width
  self.rect(d,(-280,30,edge,165),self.color(k),radius=6)
  # Stable faceted surfaces reveal actual colored sections as they are cut away.
  for row in range(4):
   for col in range(12):
    x=-280+col*40;right=min(edge,x+40)
    if x>=edge:continue
    yy=30+row*33.75
    index=row if self.recipe['pattern']=='layered' else col
    base=self.color(index)
    for points,factor in [([(x,yy),(right,yy),(right,yy+33.75)],.94), ([(x,yy),(right,yy+33.75),(x,yy+33.75)],1.04)]:
     self.poly(d,points,tuple(min(255,int(v*factor)) for v in base))
  self.poly(d,[(-280,30),(-260,11),(edge+20,11),(edge,30)],tuple(min(255,int(v*1.1)) for v in self.color(k)))
  for i in range(k):
   x=235+(i%3)*24;y=45+(i//3)*32
   self.rect(d,(x,y,x+width*.7,y+76),self.color(i),radius=4)
  for i in range(12):
   x=-275+i*38
   if x<edge:self.line(d,[(x,35),(min(edge,x+28),160)],tuple(int(v*.83) for v in self.color(k)),2)
  drop=ease(u/.46) if u<.46 else 1-ease((u-.57)/.38)
  blade_y=-220+drop*365
  self.poly(d,[(edge-width,-220+drop*365),(edge-width+19,blade_y-190),(edge-width+45,blade_y-190),(edge-width+26,blade_y)],(209,222,233))
  self.rect(d,(edge-width+17,blade_y-238,edge-width+48,blade_y-185),(138,93,66),radius=4)
  if u>.46:
   shift=ease((u-.46)/.35)
   x=edge-width+shift*(245-(edge-width));y=30+math.sin(shift*math.pi)*-38
   self.rect(d,(x,y,x+width*.8,y+125),self.color(k),radius=4)
  if .43<u<.68:
   age=(u-.43)/.25
   for j,(a,b,c,_) in enumerate(self.particles[:22]):
    x=edge-width+(a-.5)*160*age;y=40-b*130*age+140*age*age
    self.ellipse(d,(x,y,x+3+c*4,y+3+c*4),self.color(j))

 def draw_pressing(self,d,k,u,t):
  compression=math.sin(math.pi*u)**8
  wide=175+compression*85;high=95-compression*55
  if self.recipe['shape']=='bar':self.rect(d,(-wide,95-high,wide,95+high),self.color(k),radius=45,outline=(235,216,231),width=3)
  else:self.ellipse(d,(-wide,95-high,wide,95+high),self.color(k),outline=(235,216,231),width=3)
  for i in range(10):
   a=i*.63;self.ellipse(d,(math.cos(a)*wide*.65-9,95+math.sin(a)*high*.65-5,math.cos(a)*wide*.65+9,95+math.sin(a)*high*.65+5),self.color(k+i))
  bottom=-100+compression*153
  self.rect(d,(-25,-250,25,bottom-25),(126,141,160),radius=5)
  self.rect(d,(-190,bottom-38,190,bottom),(207,217,229),radius=15,outline=(242,247,250),width=2)
  if compression>.7:
   for a,b,c,_ in self.particles[:15]:
    x=(a-.5)*wide*2;y=95+(b-.5)*high
    self.ellipse(d,(x,y,x+4+c*5,y+4+c*5),(237,228,244))

 def draw_pouring(self,d,k,u,t):
  self.rect(d,(-105,35,205,205),(72,88,112),radius=25,outline=(205,219,230),width=4)
  amount=(k+min(1,u/.8))/self.count
  self.rect(d,(-96,190-amount*120,196,195),self.color(k),radius=12)
  tilt=math.sin(math.pi*min(1,u/.82))
  self.poly(d,[(-250,-215),(-85,-245),(-55-tilt*35,-145),(-220,-110)],(178,190,207))
  self.poly(d,[(-238,-205),(-95,-230),(-79-tilt*35,-155),(-218,-125)],self.color(k))
  if .16<u<.8:
   for j,(a,b,c,_) in enumerate(self.particles[:95]):
    v=(b+t*1.8)%1;x=-90+v*100+(a-.5)*24;y=-155+v*330
    radius=2+c*4 if self.material=='beads' else 2+c*2
    self.ellipse(d,(x-radius,y-radius,x+radius,y+radius),self.color(j) if self.material=='beads' else (137,211,240))
   if self.material=='water':self.line(d,[(-92,-150),(-46,-30),(0,180-amount*100)],(128,214,244),9)

 def draw_tapping(self,d,k,u,t):
  glass=self.material=='glass'
  for i in range(5):
   x=-250+i*105
   height=(100+i%3*28) if self.recipe['shape']=='stepped' else 125
   color=self.color(i) if glass else tuple(int(a*.45+b*.55) for a,b in zip(self.color(i),(170,123,80)))
   self.rect(d,(x,25-height,x+80,160),color,radius=15,outline=(217,216,226),width=2)
   if glass:self.line(d,[(x+13,45-height),(x+13,135)],(229,241,246),4)
   else:
    for j in range(4):self.line(d,[(x+8,50+j*26),(x+72,43+j*26)],(110,76,49),2)
  x=-210+(k%5)*105;hit=math.sin(math.pi*u)**12
  height=(100+(k%5)%3*28) if self.recipe['shape']=='stepped' else 125
  target=25-height-24;y=-245+hit*(target+245)
  self.line(d,[(x-60,y-80),(x,y)],(199,159,111),17)
  self.ellipse(d,(x-33,y-24,x+33,y+24),(229,207,165))
  if abs(u-.5)<.11:
   r=30+abs(u-.5)*220;self.ellipse(d,(x-r,target+24-r,x+r,target+24+r),None,outline=self.color(k),width=2)

 def draw_brushing(self,d,k,u,t):
  self.rect(d,(-290,-155,290,185),(123,96,72),radius=24)
  progress=ease(u)
  x=-230+460*(progress if k%2==0 else 1-progress)
  for a,b,c,_ in self.particles:
   px=(a-.5)*540;py=-130+b*280
   if abs(px-x)>50:self.ellipse(d,(px,py,px+3+c*4,py+3+c*4),self.color(int(c*6)))
  self.rect(d,(x-50,-180,x+50,80),(174,130,83),radius=12)
  for j in range(24):self.line(d,[(x-45+j*4,50),(x-48+j*4+math.sin(u*6)*9,115)],(230,203,163),3)
  self.rect(d,(x-15,-280,x+15,-170),(210,174,123),radius=10)

 def draw_crinkling(self,d,k,u,t):
  fold=math.sin(math.pi*u)**2;rx=270-fold*130;ry=170-fold*75
  center=(0,25)
  for j in range(12):
   a=j*math.pi/6;b=(j+1)*math.pi/6
   radial=1-((.30 if self.recipe['shape']=='stepped' else .18)*fold if j%2 else 0)
   v1=(math.cos(a)*rx*radial,25+math.sin(a)*ry)
   v2=(math.cos(b)*rx*(1-.18*fold if (j+1)%2 else 1),25+math.sin(b)*ry)
   self.poly(d,[center,v1,v2],tuple(int(v*(.75+.25*(j%3)/2)) for v in self.color(j)))
   self.line(d,[center,v1],(224,217,229),2)
  for side in (-1,1):
   x=side*(rx+35)
   self.rect(d,(x-40,-45,x+40,95),(214,165,139),radius=30)

 def draw_raking(self,d,k,u,t):
  self.rect(d,(-300,-175,300,200),(133,100,75),radius=24,outline=(202,170,122),width=8)
  self.rect(d,(-285,-160,285,185),self.colors[1],radius=20)
  x=-245+490*ease(u);direction=1 if k%2==0 else -1;x*=direction
  for j in range(7):
   y=-110+j*40
   end=x if direction==1 else 250
   start=-250 if direction==1 else x
   points=[(p,y+(10*math.sin(p/75+k*.7) if self.recipe['shape']!='stepped' else 8*(1 if int((p+300)/45)%2 else -1))) for p in np.linspace(start,end,50)]
   self.line(d,points,tuple(int(v*.64) for v in self.colors[1]),5)
   self.line(d,[(px,py-3) for px,py in points],self.colors[2],2)
  self.rect(d,(x-20,-170,x+20,175),(183,157,120),radius=8)
  for j in range(7):self.line(d,[(x,-110+j*40),(x+direction*40,-110+j*40)],(224,207,174),7)
  self.line(d,[(x,-170),(x-50,-270)],(185,145,95),17)

 def draw_ripples(self,d,k,u,t):
  self.ellipse(d,(-310,-165,310,205),(87,112,133),outline=(200,220,233),width=5)
  self.ellipse(d,(-290,-150,290,180),self.colors[0],outline=(139,200,223),width=3)
  x=math.sin(k*2.4)*120;y=25+math.cos(k*1.7)*25
  if u<.35:
   yy=-250+ease(u/.35)*(y+250)
   self.ellipse(d,(x-8,yy-17,x+8,yy+10),(171,223,246))
  for offset in (0,.12,.24):
   age=u-.35-offset
   if 0<age<.65:
    r=age*310;col=tuple(int(v*(1-age*.45)) for v in (172,221,238))
    self.ellipse(d,(x-r,y-r*.42,x+r,y+r*.42),None,outline=col,width=3)
  self.line(d,[(-180,110),(-85,125),(35,119)],(116,180,210),3)

 def build_audio(self,path):
  rng=np.random.default_rng(self.recipe['seed']);audio=np.zeros((round(self.duration*SR),2),dtype=np.float32)
  def add(wave,start,pan):
   i=round(start*SR);n=min(len(wave),len(audio)-i)
   if n<=0:return
   audio[i:i+n,0]+=wave[:n]*math.cos(pan*math.pi/2)
   audio[i:i+n,1]+=wave[:n]*math.sin(pan*math.pi/2)
  def noise(duration,low,high):
   return signal.sosfilt(signal.butter(2,[low,high],fs=SR,btype='bandpass',output='sos'),rng.standard_normal(round(duration*SR))).astype('float32')
  for i,start in enumerate(self.event_times()):
   pan=.25+.5*(.5+.5*math.sin(i*1.7))
   if self.activity in ('tapping','ripples'):
    duration=.45;t=np.arange(round(duration*SR))/SR
    freq=(1100 if self.material=='glass' else 220) if self.activity=='tapping' else 710
    wave=sum(np.sin(2*np.pi*freq*ratio*t)*np.exp(-t/decay)*amp for ratio,decay,amp in ((1,.12,.45),(1.71,.08,.18),(2.8,.04,.08)))
    wave+=noise(duration,1800,9000)*np.exp(-t/.008)*.6
   elif self.activity in ('pressing','crinkling','cutting'):
    duration=.35 if self.activity=='cutting' else self.cycle*.45
    t=np.arange(round(duration*SR))/SR
    wave=noise(duration,120 if self.activity=='pressing' else 900,2400 if self.activity=='pressing' else 11000)
    envelope=np.sin(np.pi*np.minimum(1,t/duration))**.5
    if self.activity=='crinkling':envelope*=.2+.8*np.maximum(0,np.sin(t*90+i))**8
    if self.activity=='cutting':envelope*=np.exp(-t*8)
    wave*=envelope*.65
    if self.activity=='pressing':wave+=np.sin(2*np.pi*(90*t+25*t*t))*envelope*.07
    # Center slow compression/crinkle sound at maximum visible deformation.
    if self.activity!='cutting':start-=duration/2
   else:
    duration=self.cycle*(.6 if self.activity=='pouring' else .7)
    t=np.arange(round(duration*SR))/SR
    high=8500 if self.activity in ('raking','pouring') else 4500
    wave=noise(duration,400,high)*np.sin(np.pi*t/duration)**.6*.42
    if self.activity=='pouring' and self.material=='beads':
     for impact in rng.uniform(0,duration,55):
      at=int(impact*SR);n=min(900,len(wave)-at);tt=np.arange(n)/SR
      wave[at:at+n]+=np.sin(2*np.pi*rng.uniform(900,2300)*tt)*np.exp(-tt*400)*.22
   add(wave,max(0,start),pan)
  peak=np.max(np.abs(audio));audio*=.82/max(peak,1e-6)
  n=min(960,len(audio)//2);fade=np.linspace(0,1,n)
  audio[:n]*=fade[:,None];audio[-n:]*=fade[::-1,None]
  wavfile.write(str(path),SR,(audio*32767).astype('int16'))
