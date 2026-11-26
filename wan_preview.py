"""Artifact-only Wan 2.1 T2V 1.3B Q4 Short: six real diffusion clips, no still fallback."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import zipfile

from asmr.plan import atomic,digest

ENGINE_REV='52491bd9f1fc15281791723bdff13baab7fd6819'
ENGINE_URL='https://github.com/leejet/stable-diffusion.cpp/releases/download/master-1133-52491bd/sd-master-52491bd-bin-Linux-Ubuntu-26.04-x86_64.zip'
ENGINE_SHA='49c9c949217ee18fc3f948773243978c4096b5b5cb60e58923dd9ddabf3fe21f'
FILES=[
 ('off-grid-ai/Wan2.1-T2V-1.3B-GGUF','1ba777b2426d5717dd0fddb1100078604a9d4667','Wan2.1-T2V-1.3B-calibrated-Q4_K_S.gguf','82788a4a3ce6e206edd3e8e5fe512b2a75344a3d272d80f07cd4e48b60b7aaf7'),
 ('off-grid-ai/Video-Companions-GGUF','18b5ae5e93799acd6cd20819f898ff60f4b822d1','umt5-xxl-encoder-Q4_K_M.gguf','17cf97a5bbbc60a646d6105b832b6f657ce904a8a1ad970e4b59df0c67584a40'),
 ('off-grid-ai/Video-Companions-GGUF','18b5ae5e93799acd6cd20819f898ff60f4b822d1','wan_2.1_vae.safetensors','2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b'),
]
PROFILE=dict(width=288,height=512,frames=41,native_fps=8,steps=20,cfg=6,flow_shift=3,seconds=5,output_fps=24)
SOUNDS=('water','granules','paper','brush','soft')
CACHE=Path('.wan-cache')
ROOT=Path('output/wan-short')

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def engine():
 matches=list((CACHE/'engine').rglob('sd-cli'))
 if len(matches)!=1:raise ValueError('Expected exactly one pinned sd-cli')
 return matches[0].resolve()

def engine_env():
 env=dict(os.environ)
 env['LD_LIBRARY_PATH']=str(engine().parent)+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
 return env

def assets():
 from huggingface_hub import hf_hub_download
 CACHE.mkdir(exist_ok=True)
 for repo,revision,name,expected in FILES:
  path=Path(hf_hub_download(repo,filename=name,revision=revision,local_dir=CACHE/'weights',token=False))
  if sha(path)!=expected:raise ValueError('Wan weight checksum mismatch: '+name)
  print(json.dumps(dict(verified=name)),flush=True)
 archive=CACHE/'engine.zip'
 if not archive.exists() or sha(archive)!=ENGINE_SHA:
  part=archive.with_suffix('.partial');urllib.request.urlretrieve(ENGINE_URL,part)
  if sha(part)!=ENGINE_SHA:raise ValueError('Wan engine checksum mismatch')
  part.replace(archive)
 with zipfile.ZipFile(archive) as z:
  target=(CACHE/'engine').resolve()
  for item in z.infolist():
   if not (target/item.filename).resolve().is_relative_to(target):raise ValueError('Unsafe engine archive')
  z.extractall(target)
 binary=engine();binary.chmod(0o755)
 subprocess.run([str(binary),'--help'],check=True,stdout=subprocess.DEVNULL,env=engine_env())
 atomic(CACHE/'manifest.json',dict(engine=ENGINE_REV,engine_zip_sha=ENGINE_SHA,weights=FILES))

def plan_schema():
 from asmr.plan import obj,text
 return obj(dict(idea=text(40,1000),title=text(20,90),description=text(80,1000),
  tags=dict(type='array',minItems=5,maxItems=8,items=text(3,40),uniqueItems=True),
  shots=dict(type='array',minItems=6,maxItems=6,items=obj(dict(label=text(8,60),prompt=text(100,650),sound=dict(type='string',enum=list(SOUNDS)))))))

def plan_grammar():
 def literal(s):return json.dumps(json.dumps(s))
 def obj(fields):return '"{" ws '+' ws "," ws '.join(literal(k)+' ws ":" ws '+v for k,v in fields)+' ws "}"'
 return '\n'.join([
  'root ::= '+obj([('idea','string'),('title','string'),('description','string'),('tags','"[" ws string (ws "," ws string){4,7} ws "]"'),('shots','"[" ws '+' ws "," ws '.join(['shot']*6)+' ws "]"')])+' ws',
  'shot ::= '+obj([('label','string'),('prompt','string'),('sound','sound')]),
  'sound ::= '+' | '.join(literal(s) for s in SOUNDS),
  r'string ::= "\"" char* "\""',
  r'char ::= [^"\\\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})',
  r'ws ::= [ \t\n\r]{0,4}',
 ])

def validate_plan(p):
 from jsonschema import validate
 validate(p,plan_schema())
 if len({s['prompt'].casefold() for s in p['shots']})!=6:raise ValueError('Six distinct Wan prompts required')
 if 'asmr' not in p['title'].lower():raise ValueError('ASMR title required')
 if re.search(r'\b(cure|guaranteed|real footage|recorded live)\b',p['description']+' '+p['title'],re.I):raise ValueError('Unsupported metadata claim')
 if sum(len(t)+2 for t in p['tags'])>450:raise ValueError('Tag budget exceeded')
 return p

def make_plan():
 from llama_cpp import LlamaGrammar
 from lyrics_cpu import load_model,inference_progress
 model=load_model();seed=int(hashlib.sha256(os.getenv('GITHUB_RUN_ID','wan-local').encode()).hexdigest()[:7],16)
 prompt=('Invent ONE fresh visually realistic satisfying ASMR idea, excluding soap cutting and cartoon animation. '
  'Use a simple physical subject with visible gradual motion: water ripples, flowing colored beads, paper textures, soft sand or similar. '
  'Write six coherent five-second macro camera shots of the SAME idea, each with a different composition/action variation. '
  'Wan 2.1 will generate actual video from each prompt independently; repeat the subject, colors, lighting and surface in EVERY prompt for consistency. '
  'Keep motion simple and slow. Prefer no people, hands, faces, words, logos, or impossible physical transformations. '
  'Specify photorealistic macro cinematography, realistic materials, shallow depth of field and calm soft lighting. '
  'Each English prompt is 150-450 characters; labels 10-45 characters. English title contains ASMR and is 35-75 characters. '
  'Description 150-500 characters, idea 100-500 characters. Include 5-8 relevant tags. '
  'Sound field selects a SYNTHETIC ambient sound-design bed: water, granules, paper, brush or soft. '
  'Do not claim recorded/native model audio or exact contact synchronization. Return JSON with idea,title,description,tags,shots. '
  'Each shot has label,prompt,sound. Exactly six shots, no timestamps; final Short lasts exactly 30 seconds.')
 for attempt in range(3):
  with inference_progress():
   response=model.create_chat_completion(messages=[dict(role='system',content='Design a realistic relaxing ASMR Short. Return complete JSON only.'),dict(role='user',content=prompt)],
    grammar=LlamaGrammar.from_string(plan_grammar(),verbose=False),max_tokens=3000,temperature=.65,seed=seed+attempt)
  choice=response['choices'][0]
  if choice.get('finish_reason')!='stop':raise ValueError('Wan plan output incomplete')
  p=json.loads(choice['message']['content']);atomic(ROOT/'draft.json',p)
  try:
   validate_plan(p);atomic(ROOT/'plan.json',p);atomic(ROOT/'profile.json',PROFILE);return p
  except ValueError as e:prompt+='\nCorrect: '+str(e)[:100]
  except Exception as e:
   from jsonschema import ValidationError
   if not isinstance(e,ValidationError):raise
   prompt+='\nCorrect field '+'.'.join(map(str,e.absolute_path))+'; '+e.validator+'='+str(e.validator_value)[:50]
 raise ValueError('Wan plan validation exhausted')

def command(plan,index):
 s=plan['shots'][index];weights=(CACHE/'weights').resolve()
 seed=int(digest(dict(prompt=s['prompt'],run=os.getenv('GITHUB_RUN_ID','local'),index=index))[:7],16)
 return [str(engine()),'-M','vid_gen','--diffusion-model',str(weights/FILES[0][2]),'--t5xxl',str(weights/FILES[1][2]),'--vae',str(weights/FILES[2][2]),
  '-p',s['prompt'],'-n','cartoon, illustration, text, logo, watermark, frozen frame, poor detail, flickering, deformed objects, extra hands, fast camera movement',
  '-W',str(PROFILE['width']),'-H',str(PROFILE['height']),'--video-frames',str(PROFILE['frames']),'--fps',str(PROFILE['native_fps']),
  '--steps',str(PROFILE['steps']),'--cfg-scale',str(PROFILE['cfg']),'--flow-shift',str(PROFILE['flow_shift']),
  '--sampling-method','euler','--seed',str(seed),'--rng','cpu','--backend','cpu','--flash-attn','on',
  '--vae-tiling','--vae-tile-size','256x256','--vae-tile-overlap','0.25','-t',str(min(4,os.cpu_count() or 2)),
  '-o',str((ROOT/f'shot-{index}'/'frames'/'frame_%03d.png').resolve())]

def probe(path,seconds,audio=False):
 d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))
 v=next(s for s in d['streams'] if s['codec_type']=='video')
 if (v['width'],v['height'],v['r_frame_rate'])!=(720,1280,'24/1') or abs(float(d['format']['duration'])-seconds)>.1:raise ValueError('Wan output format/duration mismatch')
 if audio and not any(s['codec_type']=='audio' and s['channels']==2 for s in d['streams']):raise ValueError('Stereo sound missing')
 subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True)
 return dict(seconds=float(d['format']['duration']),width=720,height=1280,fps=24,sha256=sha(path))

def render(index):
 from PIL import Image
 if index not in range(6):raise ValueError('Shot index must be 0-5')
 p=validate_plan(json.loads((ROOT/'plan.json').read_text()));folder=ROOT/f'shot-{index}';frames=folder/'frames';frames.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((CACHE/'manifest.json').read_text())
 if manifest!=dict(engine=ENGINE_REV,engine_zip_sha=ENGINE_SHA,weights=[list(f) for f in FILES]):raise ValueError('Wan runtime manifest changed')
 args=command(p,index);identity=digest(dict(shot=p['shots'][index],profile=PROFILE,engine=ENGINE_REV,weights=FILES))
 target=folder/'video.mp4';receipt=folder/'receipt.json'
 if receipt.exists() and target.exists():
  saved=json.loads(receipt.read_text())
  if saved['identity']==identity and saved['sha256']==sha(target):return
 if list(frames.glob('*.png')):raise ValueError('Partial frames exist; reconcile the interrupted shard instead of mixing generations')
 start=time.monotonic()
 # Prompt is an argv value, never shell code. Native progress is retained in the artifact.
 with (folder/'generation.log').open('w') as log:
  child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=engine_env())
  try:
   while child.poll() is None:
    try:child.wait(timeout=30)
    except subprocess.TimeoutExpired:
     print(json.dumps(dict(shot=index,elapsed_seconds=round(time.monotonic()-start),frames_saved=len(list(frames.glob('*.png'))))),flush=True)
   if child.returncode:raise RuntimeError('Wan native inference failed; inspect generation.log')
  except BaseException:child.kill();child.wait();raise
 images=sorted(frames.glob('*.png'))
 export_frames(folder)
 report=probe(folder/'video.mp4',5)
 atomic(receipt,dict(identity=identity,**report,inference_seconds=round(time.monotonic()-start),actual_generated_frames=len(images),native_profile=PROFILE))

def export_frames(folder):
 from PIL import Image
 frames=folder/'frames';target=folder/'video.mp4'
 images=sorted(frames.glob('*.png'))
 if len(images)!=PROFILE['frames']:raise ValueError('Wan did not generate all 41 actual frames; no still/loop fallback')
 if len({sha(p) for p in images})<6:raise ValueError('Wan output is nearly frozen; rejecting still-frame output')
 for path in images:
  with Image.open(path) as im:
   if im.size!=(288,512):raise ValueError('Wan native frame dimensions changed')
   im.verify()
 listing=folder/'frames.txt';listing.write_text(''.join(f"file 'frames/{f.name}'\nduration 0.125\n" for f in images))
 temp=folder/'video.partial.mp4'
 vf='tpad=start_mode=clone:start_duration=0.125:stop_mode=clone:stop_duration=0.25,minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,scale=720:1280:flags=lanczos'
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-vf',vf,'-t','5','-r','24','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)],check=True)
 probe(temp,5);temp.replace(target)

def assemble():
 import numpy as np
 from scipy import signal
 from scipy.io import wavfile
 p=validate_plan(json.loads((ROOT/'plan.json').read_text()));reports=[]
 for i in range(6):
  folder=ROOT/f'shot-{i}';receipt=json.loads((folder/'receipt.json').read_text())
  expected=digest(dict(shot=p['shots'][i],profile=PROFILE,engine=ENGINE_REV,weights=FILES))
  if receipt['identity']!=expected or receipt['sha256']!=sha(folder/'video.mp4') or receipt['actual_generated_frames']!=41:raise ValueError('Wan shot provenance mismatch')
  probe(folder/'video.mp4',5);reports.append(receipt)
 if len({r['sha256'] for r in reports})!=6:raise ValueError('Repeated Wan clips detected; refusing to loop one clip into thirty seconds')
 sr=48000;rng=np.random.default_rng(int(digest(p)[:7],16));audio=np.zeros((sr*30,2),dtype=np.float32)
 for i,s in enumerate(p['shots']):
  t=np.arange(sr*5)/sr;low,high={'water':(120,2400),'granules':(600,8000),'paper':(1400,11000),'brush':(250,4200),'soft':(90,1600)}[s['sound']]
  wave=signal.sosfilt(signal.butter(3,[low,high],fs=sr,btype='bandpass',output='sos'),rng.standard_normal(len(t)))
  wave*=.20+.15*np.sin(2*np.pi*.38*t+i)**2
  if s['sound']=='paper':wave*=.15+.85*np.maximum(0,np.sin(t*55+i))**8
  fade=np.minimum(1,np.minimum(t/.25,(5-t)/.25));wave*=fade
  pan=.5+.18*np.sin(t*.7+i)
  audio[i*sr*5:(i+1)*sr*5,0]=wave*np.cos(pan*math.pi/2)
  audio[i*sr*5:(i+1)*sr*5,1]=wave*np.sin(pan*math.pi/2)
 audio*=.8/max(np.max(np.abs(audio)),1e-6);wavfile.write(ROOT/'sound-design.wav',sr,(audio*32767).astype('int16'))
 (ROOT/'clips.txt').write_text(''.join(f"file 'shot-{i}/video.mp4'\n" for i in range(6)))
 temp=ROOT/'video.partial.mp4'
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','1','-i',str(ROOT/'clips.txt'),'-i',str(ROOT/'sound-design.wav'),'-t','30','-c:v','copy','-af','loudnorm=I=-19:TP=-2:LRA=6','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(temp)],check=True)
 report=probe(temp,30,audio=True);temp.replace(ROOT/'video.mp4')
 desc=p['description']+'\n\nAI-generated Wan 2.1 video with separate synthesized ASMR sound design. No talking or music.\n\nChapters\n'
 desc+='\n'.join(f"00:{i*5:02} {s['label']}" for i,s in enumerate(p['shots']))
 atomic(ROOT/'metadata.json',dict(title=p['title'],description=desc,tags=p['tags']))
 atomic(ROOT/'media.json',dict(**report,model='Wan2.1-T2V-1.3B calibrated Q4_K_S GGUF',engine=ENGINE_REV,profile=PROFILE,clips=reports,publish=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['assets','plan','render','assemble']);parser.add_argument('--index',type=int);args=parser.parse_args()
 ROOT.mkdir(parents=True,exist_ok=True)
 if args.stage=='render':render(args.index)
 else:globals()[dict(assets='assets',plan='make_plan',assemble='assemble')[args.stage]]()
