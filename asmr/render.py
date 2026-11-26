"""Measured, resumable geometry renders and a separate exact thirty-second edit."""
import hashlib
import json
from pathlib import Path
import subprocess
from . import VERSION
from .plan import atomic,digest,validate_plan

FPS=30

def file_hash(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def command(*args):
 subprocess.run(list(args),check=True)

def probe(path,seconds,decode=False,orientation='landscape'):
 from .activities import FORMATS
 data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))
 video=next(s for s in data['streams'] if s['codec_type']=='video')
 width,height=FORMATS[orientation]
 if (video['width'],video['height'],video['r_frame_rate'])!=(width,height,'30/1'):raise ValueError('ASMR video format mismatch')
 if abs(float(data['format']['duration'])-seconds)>.08:raise ValueError('ASMR duration mismatch')
 if not any(s['codec_type']=='audio' and s['channels']==2 for s in data['streams']):raise ValueError('ASMR stereo audio missing')
 if decode:command('ffmpeg','-v','error','-i',str(path),'-f','null','-')
 return dict(seconds=float(data['format']['duration']),width=width,height=height,fps=30,stereo=True,sha256=file_hash(path))

def renderer_id():
 return digest(dict(version=VERSION,activities=file_hash(Path(__file__).with_name('activities.py')),render=file_hash(__file__)))

def scene_key(scene):
 return digest(dict(scene=scene,renderer=renderer_id()))

def scene_current(root,scene):
 root=Path(root);base=root/'scenes'/f"scene-{scene['index']:02}"
 try:
  receipt=json.loads(base.with_suffix('.json').read_text())
  return receipt['identity']==scene_key(scene) and receipt['sha256']==file_hash(base.with_suffix('.mp4'))
 except (OSError,ValueError,KeyError):return False

def encode_scene(base,scene,orientation='landscape',seconds=None):
 from .activities import Scene,FORMATS
 g=Scene(scene,orientation);seconds=scene['seconds'] if seconds is None else seconds
 audio=base.with_suffix('.wav');g.build_audio(audio)
 temp=base.with_suffix('.partial.mp4')
 width,height=FORMATS[orientation]
 args=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','30','-i','pipe:0','-i',str(audio),
  '-t',str(seconds),'-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p',
  '-af',f'loudnorm=I=-19:TP=-2:LRA=6,afade=t=in:d=0.03,afade=t=out:st={seconds-.03}:d=0.03',
  '-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(temp)]
 proc=subprocess.Popen(args,stdin=subprocess.PIPE)
 try:
  for frame in range(round(seconds*FPS)):
   proc.stdin.write(g.render(frame/FPS).tobytes())
   if frame%(FPS*5)==0:print(json.dumps(dict(scene=scene['index'],rendered_seconds=frame/FPS)),flush=True)
 except BaseException:
  proc.stdin.close();proc.kill();proc.wait();raise
 else:proc.stdin.close()
 if proc.wait()!=0:raise RuntimeError('ASMR FFmpeg scene encode failed')
 report=probe(temp,seconds,decode=True,orientation=orientation)
 temp.replace(base.with_suffix('.mp4'))
 audio.unlink(missing_ok=True)
 return report,g

def render_scene(root,scene):
 root=Path(root);parts=root/'scenes';parts.mkdir(parents=True,exist_ok=True)
 base=parts/f"scene-{scene['index']:02}"
 if scene_current(root,scene):return base.with_suffix('.mp4')
 report,g=encode_scene(base,scene)
 g.render(.5+g.cycle*.5).save(base.with_suffix('.jpg'),quality=92)
 atomic(base.with_suffix('.json'),dict(identity=scene_key(scene),**report))
 return base.with_suffix('.mp4')

def product_identity(plan):return digest(dict(plan=plan,renderer=renderer_id()))

def validate_products(root,plan):
 root=Path(root);validate_plan(plan)
 report=json.loads((root/'media.json').read_text())
 if report['identity']!=product_identity(plan):raise ValueError('Finished ASMR source identity changed')
 for kind,path,seconds in [('video',root/'video.mp4',plan['seconds']),('shorts',root/'short'/'video.mp4',30)]:
  if report[kind]['sha256']!=file_hash(path):raise ValueError('Finished ASMR checksum changed')
  probe(path,seconds,orientation='landscape' if kind=='video' else 'portrait')
 return report

def assemble(root,plan):
 root=Path(root);validate_plan(plan)
 if (root/'media.json').exists():
  try:return validate_products(root,plan)
  except (ValueError,OSError,KeyError):pass
 paths=[]
 for scene in plan['scenes']:
  if not scene_current(root,scene):raise ValueError('Missing or stale ASMR scene; render the affected shard')
  paths.append(root/'scenes'/f"scene-{scene['index']:02}.mp4")
 listing=root/'concat.txt'
 listing.write_text(''.join(f"file 'scenes/{p.name}'\n" for p in paths))
 long_temp=root/'video.partial.mp4'
 command('ffmpeg','-y','-loglevel','error','-f','concat','-safe','1','-i',str(listing),'-t',str(plan['seconds']),'-c','copy','-movflags','+faststart',str(long_temp))
 long_report=probe(long_temp,plan['seconds'],decode=True);long_temp.replace(root/'video.mp4')
 short=root/'short';short.mkdir(exist_ok=True)
 pieces=[]
 for i,index in enumerate(plan['short_scenes']):
  target=short/f'part-{i}.mp4'
  # Recompose the original scene for portrait, preserving the entire action.
  encode_scene(target.with_suffix(''),plan['scenes'][index],orientation='portrait',seconds=10)
  pieces.append(target)
 (short/'concat.txt').write_text(''.join(f"file '{p.name}'\n" for p in pieces))
 short_temp=short/'video.partial.mp4'
 command('ffmpeg','-y','-loglevel','error','-f','concat','-safe','1','-i',str(short/'concat.txt'),'-t','30','-c','copy','-movflags','+faststart',str(short_temp))
 short_report=probe(short_temp,30,decode=True,orientation='portrait');short_temp.replace(short/'video.mp4')
 from PIL import Image,ImageOps
 for dest,index in [(root,0),(short,plan['short_scenes'][0])]:
  with Image.open(root/'scenes'/f'scene-{index:02}.jpg') as image:
   # Separate landscape YouTube thumbnail, taken from the actual rendered subject.
   ImageOps.fit(image.convert('RGB'),(1280,720),method=Image.Resampling.LANCZOS,centering=(.5,.62)).save(dest/'thumbnail.jpg',quality=92)
 atomic(root/'media.json',dict(identity=product_identity(plan),video=long_report,shorts=short_report))
 for p in pieces:p.unlink(missing_ok=True)
 return validate_products(root,plan)
