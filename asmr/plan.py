"""Bounded local-AI ideas mapped to executable geometry, not arbitrary generated code."""
import copy
import hashlib
import json
import re
from pathlib import Path
from jsonschema import validate,ValidationError
from . import VERSION

PALETTES = {
 'candy':['ff8cac','ffb270','ffe27a','80dea2','7abeff','b898f2'],
 'ocean':['164b70','2588b5','54c8d3','a1e7dc','d6f2ef','618acb'],
 'sunset':['642967','b44679','f57678','ffa36c','ffd28a','e6a0b9'],
 'forest':['244f44','448b64','82b979','bdcf87','dbc791','769b8d'],
 'jewel':['5d317f','a04b9b','d864af','309caa','5372ba','b999db'],
 'citrus':['f08b36','ffbb48','ffe873','c3dd61','8bbb60','ffc27b'],
 'lavender':['57416f','8062a1','ad8ac6','ceb3df','e6d2ec','9ca7cf'],
 'rose':['78394e','ad5c78','d88aa4','f2b3c4','f9d7df','cda6be'],
}
MATERIALS=('soap','sand','clay','slime')
SHAPES=('bar','tapered','stepped')
PATTERNS=('rainbow','solid','layered','striped')

def atomic(path, value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2,ensure_ascii=False));temp.replace(path)

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def scene_identity(scene):
 return {k:scene[k] for k in ('material','palette','shape','pattern','cuts')}

def fingerprint(plan):
 return digest([scene_identity(s) for s in plan['scenes']])

def obj(properties):
 return dict(type='object',additionalProperties=False,properties=properties,required=list(properties))

def text(minimum,maximum):
 return dict(type='string',minLength=minimum,maxLength=maximum)

def metadata_schema():
 return obj(dict(title=text(20,90),description=text(80,1000),tags=dict(type='array',minItems=5,maxItems=12,uniqueItems=True,items=text(3,40))))

def schema():
 scene=obj(dict(label=text(8,65),material=dict(type='string',enum=list(MATERIALS)),
  palette=dict(type='string',enum=list(PALETTES)),shape=dict(type='string',enum=list(SHAPES)),
  pattern=dict(type='string',enum=list(PATTERNS)),cuts=dict(type='integer',minimum=8,maximum=10)))
 return obj(dict(idea=text(40,350),video=metadata_schema(),shorts=metadata_schema(),
  scenes=dict(type='array',minItems=12,maxItems=12,items=scene),
  short_scenes=dict(type='array',minItems=3,maxItems=3,uniqueItems=True,items=dict(type='integer',minimum=0,maximum=11))))

def validate_plan(plan):
 payload={k:plan[k] for k in ('idea','video','shorts','scenes','short_scenes')}
 scenes=copy.deepcopy(payload['scenes'])
 for scene in scenes:
  for k in ('index','seconds','start','seed'):scene.pop(k,None)
 payload['scenes']=scenes
 validate(payload,schema())
 if plan.get('version')!=VERSION or plan.get('seconds') not in (240,270,300):raise ValueError('Invalid ASMR version or duration')
 if not re.fullmatch(r'asmr-[A-Za-z0-9_-]{1,70}',plan.get('run_id','')):raise ValueError('Invalid ASMR identity')
 if len({digest(scene_identity(s)) for s in plan['scenes']})!=12:raise ValueError('Every scene must have a distinct rendered configuration')
 for i,scene in enumerate(plan['scenes']):
  expected=plan['seconds']/12
  if scene['index']!=i or scene['seconds']!=expected or abs(scene['start']-i*expected)>1e-5:raise ValueError('ASMR scene timeline changed')
  if type(scene['seed']) is not int or not 0<=scene['seed']<2**31:raise ValueError('Invalid scene seed')
 if plan['video']['title'].casefold()==plan['shorts']['title'].casefold():raise ValueError('Full episode and Short need distinct titles')
 for kind,indices in [('video',range(12)),('shorts',plan['short_scenes'])]:
  meta=plan[kind];words=set(re.findall(r'[a-z]+',meta['title'].lower()))
  available={plan['scenes'][i]['material'] for i in indices}
  if 'asmr' not in words:raise ValueError('Title must identify the ASMR video')
  for material in MATERIALS:
   if material in words and material not in available:raise ValueError('Title promises a material absent from the rendered video')
  if re.search(r'\b[0-9]+\s+(cuts|slices|colors|layers|materials)\b',meta['title']+' '+meta['description'],re.I):raise ValueError('Metadata must not invent numeric event counts')
  if re.search(r'\b(cure|cures|heal|heals|guaranteed|real footage|recorded live)\b',meta['title']+' '+meta['description'],re.I):raise ValueError('Unverifiable metadata claim')
  if len({x.casefold().strip() for x in meta['tags']})!=len(meta['tags']) or sum(len(x)+2 for x in meta['tags'])>450:raise ValueError('Invalid ASMR tags')
 if plan.get('fingerprint')!=fingerprint(plan):raise ValueError('ASMR plan fingerprint mismatch')
 return plan

def finish(payload,run_id,seconds,seed):
 validate(payload,schema())
 plan=copy.deepcopy(payload)
 for i,s in enumerate(plan['scenes']):s.update(index=i,seconds=seconds/12,start=i*seconds/12,seed=(seed+i*7919)%(2**31))
 plan.update(version=VERSION,run_id=run_id,seconds=seconds)
 plan['fingerprint']=fingerprint(plan)
 return validate_plan(plan)

def metadata(plan,kind):
 validate_plan(plan)
 result=copy.deepcopy(plan[kind])
 result['description']+='\n\nDigitally animated ASMR with synthesized cutting, crunching and squishing sounds. No talking or music.'
 indices=range(12) if kind=='video' else plan['short_scenes']
 lines=[]
 for position,i in enumerate(indices):
  seconds=int(plan['scenes'][i]['start'] if kind=='video' else position*10)
  lines.append(f"{seconds//60:02}:{seconds%60:02} {plan['scenes'][i]['label']}")
 result['description']+='\n\nChapters\n'+'\n'.join(lines)
 return result

def generate(root,run_id,seconds,history,ask=None):
 root=Path(root);path=root/'plan.json'
 if path.exists():
  plan=validate_plan(json.loads(path.read_text()))
  if plan['run_id']!=run_id or plan['seconds']!=seconds:raise ValueError('Saved ASMR request differs; choose a new run ID')
  return plan
 seed=int(hashlib.sha256(run_id.encode()).hexdigest()[:8],16)%(2**31-3)
 recent=[dict(title=h.get('title','')[:90],idea=h.get('idea','')[:220],recipes=h.get('recipes',[])[:3]) for h in history[-8:]]
 prompt=f'''Design an original satisfying low-poly cutting ASMR episode of {seconds} seconds.
The renderer makes actual animated cutting geometry, not photographs. Invent one coherent fresh idea,
then exactly 12 DISTINCT scene configurations that realize it. Supported materials: soap (crisp flakes),
sand (fine grains), clay (soft chunks), slime (elastic slices). All are sliced by a moving blade.
Shapes: bar, tapered, stepped. Patterns: rainbow (different colored slices), solid, layered,
striped. Palettes: {json.dumps(PALETTES)}. Each scene has 8-10 cuts and lasts {seconds/12} seconds.
Vary at least two of material, shape, pattern and palette across the episode. The idea should be
visually coherent, not an unrelated random list. Never promise a shape or action outside these options.
Write English YouTube video and Short title, unique description and 5-12 relevant tags each.
Every title contains ASMR, a concrete rendered subject and a specific satisfying benefit/contrast.
Do not invent scientific/health benefits, real footage, talking, music, famous brands or impossible visuals.
Do not state numeric counts of cuts/slices/colors/layers/materials in titles or descriptions.
Choose exactly three distinct zero-based short_scenes; the Short will contain the first 10 seconds
of those three scenes, for exactly 30 seconds. Short metadata describes ONLY those selected scenes.
Labels are short, readable chapter names. No timestamps in descriptions; real ones are added later.
Avoid the recent ideas/titles/render configurations: {json.dumps(recent)}.
Return only the requested JSON; labels and colors must match the selected renderer controls.'''
 if ask is None:
  def ask(prompt,spec,seed):
   from lyrics_cpu import request_story,MODEL_ID
   response=request_story('chat/completions',dict(model=MODEL_ID,seed=seed,max_completion_tokens=4800,
    messages=[dict(role='system',content='You design original procedural ASMR episodes. Respect the renderer controls and return valid JSON only.'),dict(role='user',content=prompt)],
    response_format=dict(type='json_schema',json_schema=dict(name='asmr_episode',schema=spec))))
   return json.loads(response['choices'][0]['message']['content'])
 for attempt in range(3):
  payload=ask(prompt,schema(),seed+attempt)
  atomic(root/'draft.json',payload)
  try:
   plan=finish(payload,run_id,seconds,seed)
   if any(h.get('fingerprint')==plan['fingerprint'] or h.get('title','').casefold()==plan['video']['title'].casefold() for h in history if h.get('run_id')!=run_id):raise ValueError('Duplicate ASMR title or render plan')
   diversity=[len({s[k] for s in plan['scenes']}) for k in ('material','shape','pattern','palette')]
   if sum(n>1 for n in diversity)<2:raise ValueError('Episode needs variation in two visual controls')
   atomic(path,plan);return plan
  except (ValueError,ValidationError) as e:
   if attempt==2:raise
   reason=e.message if isinstance(e,ValidationError) else str(e)
   prompt+='\nCorrect the previous candidate: '+reason[:400]+'. Return a complete new candidate.'
 raise RuntimeError('ASMR idea generation exhausted')
