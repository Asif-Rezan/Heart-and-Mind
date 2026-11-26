"""Bounded local-AI ideas mapped to executable geometry, not arbitrary generated code."""
import copy
import hashlib
import json
import re
import random
from collections import Counter
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
ACTIVITIES={
 'cutting':('soap','sand','clay','slime'),
 'pressing':('slime','clay'),
 'pouring':('beads','water'),
 'tapping':('wood','glass'),
 'brushing':('sand',),
 'crinkling':('paper',),
 'raking':('sand',),
 'ripples':('water',),
}
MATERIALS=tuple(dict.fromkeys(m for materials in ACTIVITIES.values() for m in materials))
SHAPES=('bar','tapered','stepped')
PATTERNS=('rainbow','solid','layered','striped')

def atomic(path, value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2,ensure_ascii=False));temp.replace(path)

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def scene_identity(scene):
 return {k:scene[k] for k in ('activity','material','palette','shape','pattern','cycles')}

def fingerprint(plan):
 return digest([scene_identity(s) for s in plan['scenes']])

def obj(properties):
 return dict(type='object',additionalProperties=False,properties=properties,required=list(properties))

def text(minimum,maximum):
 return dict(type='string',minLength=minimum,maxLength=maximum)

def metadata_schema():
 return obj(dict(title=text(20,90),description=text(80,1000),tags=dict(type='array',minItems=5,maxItems=12,uniqueItems=True,items=text(3,40))))

def schema(activities=None):
 scene=obj(dict(label=text(8,65),activity=dict(type='string',enum=list(activities or ACTIVITIES)),material=dict(type='string',enum=list(MATERIALS)),
  palette=dict(type='string',enum=list(PALETTES)),shape=dict(type='string',enum=list(SHAPES)),
  pattern=dict(type='string',enum=list(PATTERNS)),cycles=dict(type='integer',minimum=8,maximum=10)))
 return obj(dict(idea=text(40,350),video=metadata_schema(),shorts=metadata_schema(),
  scenes=dict(type='array',minItems=12,maxItems=12,items=scene),
  short_scenes=dict(type='array',minItems=3,maxItems=3,uniqueItems=True,items=dict(type='integer',minimum=0,maximum=11))))

def activity_issue(meta,scenes):
 words=set(re.findall(r'[a-z]+',(meta['title']+' '+meta['description']).lower()))
 aliases={'cutting':{'cutting','slicing','slices'},'pressing':{'pressing','squishing'},'pouring':{'pouring'},
  'tapping':{'tapping','taps'},'brushing':{'brushing','sweeping'},'crinkling':{'crinkling','crumpling'},
  'raking':{'raking'},'ripples':{'ripples','dripping'}}
 actual={s['activity'] for s in scenes}
 for activity,terms in aliases.items():
  if words&terms and activity not in actual:return 'Metadata promises an activity absent from the rendered scenes: '+activity
 return None

def short_issue(payload):
 meta=payload['shorts']
 words=set(re.findall(r'[a-z]+',(meta['title']+' '+meta['description']).lower()))
 available={payload['scenes'][i]['material'] for i in payload['short_scenes']}
 if any(material in words and material not in available for material in MATERIALS):return 'Short metadata promises a material absent from its selected scenes'
 issue=activity_issue(meta,[payload['scenes'][i] for i in payload['short_scenes']])
 if issue:return issue
 for duration in re.findall(r'\b(\d+)\s*[- ]?\s*(?:seconds?|secs?)\b',meta['title']+' '+meta['description']+' '+' '.join(meta['tags']),re.I):
  if int(duration)!=30:return 'The Short lasts 30 seconds; do not promise another duration'
 return None

def normalize_idea(payload):
 """Bound only editorial summary prose; never alter executable scene recipes."""
 payload=copy.deepcopy(payload)
 idea=payload.get('idea')
 if isinstance(idea,str):
  idea=' '.join(idea.split())
  if len(idea)>350:
   prefix=idea[:349]
   stops=list(re.finditer(r'[.!?](?=\s|$)',prefix))
   idea=prefix[:stops[-1].end()] if stops and stops[-1].end()>=40 else prefix.rsplit(' ',1)[0].rstrip(' ,;:.')+'.'
  payload['idea']=idea
 return payload

def repair_short(payload,ask,seed,kind='shorts'):
 """Keep the AI's recipes; rewrite only conflicting packaging."""
 indices=payload['short_scenes'] if kind=='shorts' else range(12)
 def check(candidate):
  if kind=='shorts':return short_issue(candidate)
  meta=candidate['video'];scenes=candidate['scenes']
  words=set(re.findall(r'[a-z]+',(meta['title']+' '+meta['description']).lower()))
  available={s['material'] for s in scenes}
  if any(m in words and m not in available for m in MATERIALS):return 'Full metadata promises an absent material'
  return activity_issue(meta,scenes)
 issue=check(payload)
 if not issue:return payload
 selected=[scene_identity(payload['scenes'][i]) for i in indices]
 subject='30-second animated ASMR Short, ten seconds from each selected scene' if kind=='shorts' else '4-5 minute animated ASMR episode'
 timing='Only mention duration as 30 seconds.' if kind=='shorts' else 'Omit duration references.'
 prompt=('Write English title, description and 5-12 relevant tags for this exact '+subject+'. '
  'It contains these scene recipes: '+json.dumps(selected)+'. '
  'Describe ONLY the selected activities and materials, palettes, shapes and patterns. Never call non-cutting scenes cutting or slicing. Title contains ASMR. '
  'Use a title of 35-75 characters and description of 150-350 characters. '
  'No health promises, real-footage claims or numeric event counts. '+timing+' '
  'Return only title, description and tags as JSON. Fix: '+issue)
 for attempt in range(3):
  candidate=ask(prompt,metadata_schema(),seed+attempt)
  try:
   validate(candidate,metadata_schema())
   payload=copy.deepcopy(payload);payload[kind]=candidate
   issue=check(payload)
   if not issue:return payload
   prompt+='\nCorrect: '+issue
  except ValidationError as error:
   prompt+='\nCorrect field '+'.'.join(map(str,error.absolute_path))+'; constraint '+error.validator+'='+str(error.validator_value)[:80]
 raise ValueError('ASMR metadata repair exhausted')

def validate_plan(plan):
 payload={k:plan[k] for k in ('idea','video','shorts','scenes','short_scenes')}
 scenes=copy.deepcopy(payload['scenes'])
 for scene in scenes:
  for k in ('index','seconds','start','seed'):scene.pop(k,None)
 payload['scenes']=scenes
 validate(payload,schema())
 if short_issue(payload):raise ValueError(short_issue(payload))
 if plan.get('version')!=VERSION or plan.get('seconds') not in (240,270,300):raise ValueError('Invalid ASMR version or duration')
 if not re.fullmatch(r'asmr-[A-Za-z0-9_-]{1,70}',plan.get('run_id','')):raise ValueError('Invalid ASMR identity')
 if len({digest(scene_identity(s)) for s in plan['scenes']})!=12:raise ValueError('Every scene must have a distinct rendered configuration')
 counts=Counter(s['activity'] for s in plan['scenes'])
 if len(counts)<3 or counts['cutting']>3:raise ValueError('Episode needs at least three actual activities; cutting is limited to three scenes')
 for i,scene in enumerate(plan['scenes']):
  if scene['material'] not in ACTIVITIES[scene['activity']]:raise ValueError('Material is incompatible with the selected activity')
  expected=plan['seconds']/12
  if scene['index']!=i or scene['seconds']!=expected or abs(scene['start']-i*expected)>1e-5:raise ValueError('ASMR scene timeline changed')
  if type(scene['seed']) is not int or not 0<=scene['seed']<2**31:raise ValueError('Invalid scene seed')
 if plan['video']['title'].casefold()==plan['shorts']['title'].casefold():raise ValueError('Full episode and Short need distinct titles')
 for kind,indices in [('video',range(12)),('shorts',plan['short_scenes'])]:
  meta=plan[kind];words=set(re.findall(r'[a-z]+',meta['title'].lower()))
  issue=activity_issue(meta,[plan['scenes'][i] for i in indices])
  if issue:raise ValueError(issue)
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
 result['description']+='\n\nDigitally animated ASMR with synthesized sounds synchronized to the visible activities. No talking or music.'
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
 rng=random.Random(seed)
 menu=rng.sample(list(ACTIVITIES),4)
 previous={r.get('activity') for r in (history[-1].get('recipes',[]) if history else [])}
 if set(menu)==previous:
  menu[-1]=rng.choice([a for a in ACTIVITIES if a not in menu])
 recent=[dict(title=h.get('title','')[:90],idea=h.get('idea','')[:220],recipes=h.get('recipes',[])[:3]) for h in history[-8:]]
 prompt=f'''Design an original satisfying multi-activity illustrated ASMR episode of {seconds} seconds.
The renderer has genuinely different animations and synchronized sounds for each activity, not photographs.
Invent one coherent fresh idea, then exactly 12 DISTINCT scene configurations that realize it.
This episode's randomly selected activity menu is {json.dumps(menu)}. Use EVERY activity in that menu,
at least three different activities total. Cutting may occupy AT MOST three scenes. Spread the remaining scenes across the others.
Activity/material compatibility: {json.dumps(ACTIVITIES)}.
Cutting: blade separates slices. Pressing: a press deforms soft slime/clay. Pouring: tilted container streams beads or water.
Tapping: mallets tap wood/glass. Brushing: brush sweeps loose sand. Crinkling: paper folds and crumples.
Raking: comb draws grooves in sand. Ripples: drops fall into water and expanding rings travel across its surface.
Shapes: bar, tapered, stepped. Patterns: rainbow (different colored slices), solid, layered,
striped. Palettes: {json.dumps(PALETTES)}. Each scene has 8-10 action cycles and lasts {seconds/12} seconds.
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
 prompt+='\nKeep idea to 120-220 CHARACTERS, titles to 35-75 CHARACTERS, descriptions to 150-350 CHARACTERS, labels to 15-45 CHARACTERS. Each scene MUST include label, activity, material, palette, shape, pattern and cycles. Include all twelve complete scenes. Titles and descriptions must describe the actual activities. Do not call everything cutting.'
 if ask is None:
  from .model import ask
 for attempt in range(3):
  try:
   payload=ask(prompt,schema(menu),seed+attempt)
   atomic(root/'draft.json',payload)
   payload=normalize_idea(payload)
   # Validate structural data before indexing it for targeted metadata repair.
   validate(payload,schema())
   payload=repair_short(payload,ask,seed+100+attempt*3)
   payload=repair_short(payload,ask,seed+200+attempt*3,kind='video')
   atomic(root/'candidate.json',payload)
   plan=finish(payload,run_id,seconds,seed)
   if any(h.get('fingerprint')==plan['fingerprint'] or h.get('title','').casefold()==plan['video']['title'].casefold() for h in history if h.get('run_id')!=run_id):raise ValueError('Duplicate ASMR title or render plan')
   diversity=[len({s[k] for s in plan['scenes']}) for k in ('material','shape','pattern','palette')]
   if sum(n>1 for n in diversity)<2:raise ValueError('Episode needs variation in two visual controls')
   atomic(path,plan);return plan
  except (ValueError,ValidationError) as e:
   print(json.dumps(dict(check='ASMR plan validation',attempt=attempt+1,error_type=type(e).__name__,field=list(e.absolute_path) if isinstance(e,ValidationError) else [])),flush=True)
   if attempt==2:raise
   reason=('field '+'.'.join(map(str,e.absolute_path))+' violates '+e.validator+'='+str(e.validator_value)[:100]) if isinstance(e,ValidationError) else str(e)
   prompt+='\nCorrect the previous candidate: '+reason[:400]+'. Return a complete new candidate.'
 raise RuntimeError('ASMR idea generation exhausted')
