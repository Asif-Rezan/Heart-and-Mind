import json
import os
from pathlib import Path
import re
import subprocess
from PIL import Image,ImageOps,ImageEnhance
from asmr.plan import atomic,digest
from asmr.render import file_hash
from .writer import validate_song
from . import VERSION

def identity(song):
 return digest(dict(song=song,version=VERSION,renderer=file_hash(__file__),packaging=file_hash(Path(__file__).with_name('packaging.py'))))

def probe(path):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))

def duration(path):return float(probe(path)['format']['duration'])

def verify_audio(path):
 seconds=duration(path)
 if not 178<=seconds<=302:raise ValueError('English song audio must remain about 3-5 minutes')
 result=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(path),'-af','silencedetect=noise=-55dB:d=8,volumedetect','-f','null','-'],check=True,capture_output=True,text=True)
 mean=re.search(r'mean_volume: ([\d.-]+) dB',result.stderr)
 if not mean or float(mean.group(1))< -42:raise ValueError('Silent or extremely quiet music rejected')
 if 'silence_start:' in result.stderr:raise ValueError('Eight-second audio dropout rejected; keep candidate for review')
 return seconds

def music(root,song):
 validate_song(song);root=Path(root);receipt=root/'music.json';target=root/'song.wav'
 from music_cpu import SOURCE_REVISION,MODEL_REVISION,MODEL,inference_steps
 if os.getenv('REFERENCE_AUDIO_PATH'):raise ValueError('English original-song generation must not inherit a legacy style-reference recording')
 key=digest(dict(lyrics=song['lyrics_sha256'],prompt=song['prompt'],language='en',duration=song['duration'],voice=song['vocal_gender'],source=SOURCE_REVISION,model=MODEL,model_revision=MODEL_REVISION,steps=inference_steps()))
 if receipt.exists() and target.exists():
  previous=json.loads(receipt.read_text())
  if previous['identity']==key and previous['sha256']==file_hash(target):verify_audio(target);return previous
  raise ValueError('Saved singing differs from accepted lyrics; use a new song identity')
 from music_cpu import generate_segment
 for attempt in range(2):
  raw=root/'raw-song.wav';state_path=root/'music-state.json'
  state=json.loads(state_path.read_text()) if state_path.exists() else {}
  request=dict(song,_segment=True)
  generate_segment(request,raw,state,lambda:atomic(state_path,state))
  try:verify_audio(raw);break
  except ValueError:
   raw.replace(root/f'rejected-song-{attempt}.wav')
   if attempt==1:raise
 temp=root/'song.partial.wav'
 subprocess.run(['ffmpeg','-y','-v','error','-i',str(raw),'-af','loudnorm=I=-14:TP=-1.5:LRA=9','-ar','44100','-ac','2','-c:a','pcm_s16le',str(temp)],check=True)
 seconds=verify_audio(temp);temp.replace(target)
 report=dict(identity=key,sha256=file_hash(target),seconds=seconds,language='en',lyrics_sha256=song['lyrics_sha256'])
 atomic(receipt,report);return report

def image_plan(song,index):
 import image_cpu
 from image_cpu import MODEL,REVISION
 return dict(prompt=song['visuals'][index]['prompt'],seed=int(digest(dict(song=song['lyrics_sha256'],index=index))[:7],16),
  width=1024,height=576,steps=24,style='cinematic',model=MODEL,revision=REVISION,implementation=file_hash(image_cpu.__file__))

def image(root,song,index):
 validate_song(song)
 if index not in range(6):raise ValueError('Image index must be 0-5')
 root=Path(root);folder=root/'images';folder.mkdir(parents=True,exist_ok=True)
 path=folder/f'background-{index}.png';receipt=folder/f'background-{index}.json';plan=image_plan(song,index)
 if path.exists() and receipt.exists():
  previous=json.loads(receipt.read_text())
  if previous.get('plan')==plan and previous.get('sha256')==file_hash(path):
   with Image.open(path) as im:im.verify()
   return
 from image_cpu import generate
 temp=folder/f'background-{index}.partial.png'
 generate(plan['prompt'],temp,seed=plan['seed'],width=plan['width'],height=plan['height'],steps=plan['steps'],style='cinematic')
 with Image.open(temp) as im:
  if im.size!=(1024,576):raise ValueError('English image dimensions mismatch')
  im.verify()
 temp.replace(path);atomic(receipt,dict(plan=plan,sha256=file_hash(path)))

def verify_products(root,song):
 validate_song(song);root=Path(root);report=json.loads((root/'media.json').read_text())
 if report.get('identity')!=identity(song):raise ValueError('English song source changed')
 for name in ('song.wav','video.mp4','thumbnail.jpg','metadata.json'):
  if file_hash(root/name)!=report['files'][name]:raise ValueError('English media checksum changed')
 d=probe(root/'video.mp4');v=next(s for s in d['streams'] if s['codec_type']=='video')
 if (v['width'],v['height'],v['r_frame_rate'])!=(1920,1080,'25/1'):raise ValueError('English full video must be 1920x1080 landscape / 25 FPS')
 if abs(float(d['format']['duration'])-report['seconds'])>.15:raise ValueError('Full song video duration mismatch')
 if not any(s['codec_type']=='audio' and s['channels']==2 for s in d['streams']):raise ValueError('English stereo singing missing')
 return report

def cinematic_timeline(paths,seconds,size=(1920,1080)):
 """MoviePy native 16:9 composition, bounded Ken Burns movement and real dissolves."""
 import numpy as np
 from moviepy import ImageClip,CompositeVideoClip,vfx
 width,height=size;crossfade=min(.8,seconds/len(paths)/4)
 span=(seconds+crossfade*(len(paths)-1))/len(paths)
 clips=[];starts=[]
 for i,path in enumerate(paths):
  with Image.open(path) as source:
   graded=ImageEnhance.Contrast(source.convert('RGB')).enhance(1.045)
   graded=ImageEnhance.Color(graded).enhance(.95)
   data=np.asarray(graded).astype('float32')
  h,w=data.shape[:2];yy,xx=np.mgrid[-1:1:complex(h),-1:1:complex(w)]
  vignette=1-.10*np.clip((xx*xx+yy*yy)/2,0,1)
  data=np.clip(data*np.array([1.015,1,.99])*vignette[:,:,None],0,255).astype('uint8')
  base=max(width/w,height/h)
  def zoom(t,index=i,scale=base,length=span):
   u=max(0,min(1,t/length));return scale*(1.035+.045*(u if index%2==0 else 1-u))
  def position(t,z=zoom,index=i,source_w=w,source_h=h,length=span):
   sx=source_w*z(t);sy=source_h*z(t);u=max(0,min(1,t/length))
   pan=.25+.5*(u if index%2==0 else 1-u)
   return ((width-sx)*pan,(height-sy)*.5)
  start=i*(span-crossfade);starts.append(start)
  clip=ImageClip(data).with_duration(span).resized(zoom).with_position(position).with_start(start)
  if i:clip=clip.with_effects([vfx.CrossFadeIn(crossfade)])
  clips.append(clip)
 final=CompositeVideoClip(clips,size=size).with_duration(seconds)
 return final,starts,clips

def assemble(root,song):
 root=Path(root);validate_song(song)
 if (root/'media.json').exists():return verify_products(root,song)
 seconds=verify_audio(root/'song.wav');music=json.loads((root/'music.json').read_text())
 if music['sha256']!=file_hash(root/'song.wav') or music['lyrics_sha256']!=song['lyrics_sha256']:raise ValueError('Audio was generated from different lyrics')
 paths=[]
 for i in range(6):
  path=root/'images'/f'background-{i}.png';receipt=json.loads(path.with_suffix('.json').read_text())
  if receipt['plan']!=image_plan(song,i) or receipt['sha256']!=file_hash(path):raise ValueError('Background image does not match this English song')
  paths.append(path)
 if len({file_hash(p) for p in paths})!=6:raise ValueError('Six distinct English song backgrounds required')
 # MoviePy retains the whole measured performance, including its natural intro/outro.
 from moviepy import AudioFileClip
 final,scene_starts,clips=cinematic_timeline(paths,seconds)
 temp=root/'video.partial.mp4'
 audio=AudioFileClip(str(root/'song.wav'))
 try:
  final=final.with_audio(audio)
  final.write_videofile(str(temp),fps=25,codec='libx264',audio_codec='aac',audio_bitrate='320k',audio_fps=44100,
   preset='fast',threads=2,ffmpeg_params=['-crf','18','-pix_fmt','yuv420p','-movflags','+faststart'],logger=None)
 finally:
  final.close();audio.close()
  for clip in clips:clip.close()
 subprocess.run(['ffmpeg','-v','error','-i',str(temp),'-f','null','-'],check=True);temp.replace(root/'video.mp4')
 from .packaging import thumbnail,metadata
 thumbnail(paths[0],root/'thumbnail.jpg',song['title'])
 starts=[]
 for i,start in enumerate(scene_starts):
  t=int(start);starts.append(f'{t//60:02}:{t%60:02} '+song['visuals'][i]['label'])
 atomic(root/'metadata.json',metadata(song,starts))
 atomic(root/'media.json',dict(identity=identity(song),seconds=seconds,language='en',lyrics_sha256=song['lyrics_sha256'],renderer='MoviePy 2.2.1',scene_starts=scene_starts,files={name:file_hash(root/name) for name in ('song.wav','video.mp4','thumbnail.jpg','metadata.json')}))
 return verify_products(root,song)
