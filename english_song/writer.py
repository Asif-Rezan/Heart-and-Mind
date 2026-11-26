import copy
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from jsonschema import validate,ValidationError
from asmr.plan import atomic,digest,obj,text
from . import VERSION

COUNTS={'verse1':4,'prechorus':2,'chorus':4,'verse2':4,'bridge':4,'outro':2}
ORDER=[('Verse 1','verse1'),('Pre-Chorus','prechorus'),('Chorus','chorus'),('Verse 2','verse2'),('Pre-Chorus','prechorus'),('Chorus','chorus'),('Bridge','bridge'),('Chorus','chorus'),('Outro','outro')]
KEYS=('C major','D major','F major','G major','A minor','E minor','D minor')

def schema():
 return obj(dict(title=text(15,80),description=text(100,1000),story=text(60,700),production=text(40,260),
  bpm=dict(type='integer',minimum=78,maximum=104),key=dict(type='string',enum=list(KEYS)),
  tags=dict(type='array',minItems=5,maxItems=10,uniqueItems=True,items=text(3,40)),
  sections=obj({k:dict(type='array',minItems=n,maxItems=n,items=text(8,100)) for k,n in COUNTS.items()}),
  visuals=dict(type='array',minItems=6,maxItems=6,items=obj(dict(label=text(8,55),prompt=text(80,500))))))

def grammar(spec):
 """Small strict decoding rules, including fixed arrays; no generic-JSON fallback."""
 rules=[r'string ::= "\"" char* "\""',r'char ::= [^"\\\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})',r'ws ::= [ \t\n\r]{0,4}']
 def literal(value):return json.dumps(json.dumps(value))
 def visit(s,name):
  name=re.sub(r'[^A-Za-z0-9-]','-',name)
  kind=s['type']
  if 'enum' in s:rule=' | '.join(literal(v) for v in s['enum'])
  elif kind=='string':return 'string'
  elif kind=='integer':rule=' | '.join(json.dumps(str(v)) for v in range(s['minimum'],s['maximum']+1))
  elif kind=='object':
   parts=[literal(k)+' ws ":" ws '+visit(v,name+'-'+k) for k,v in s['properties'].items()]
   rule='"{" ws '+' ws "," ws '.join(parts)+' ws "}"'
  elif kind=='array':
   item=visit(s['items'],name+'-item');minimum=s['minItems'];maximum=s['maxItems']
   rule='"[" ws '+' ws "," ws '.join([item]*minimum)
   if minimum==0:rule+='('+item+' (ws "," ws '+item+'){0,'+str(maximum-1)+'})?'
   elif maximum>minimum:rule+=' (ws "," ws '+item+'){0,'+str(maximum-minimum)+'}'
   rule+=' ws "]"'
  else:raise ValueError('Unsupported writer schema')
  rules.append(name+' ::= '+rule);return name
 visit(spec,'root');return '\n'.join(rules)

def ask(prompt,spec,seed):
 from llama_cpp import LlamaGrammar
 from lyrics_cpu import load_model,inference_progress,CONTEXT_TOKENS
 model=load_model();messages=[dict(role='system',content='You are an original English songwriter and exacting music editor. Return complete JSON only.'),dict(role='user',content=prompt)]
 budget=3900
 if sum(len(model.tokenize(m['content'].encode(),add_bos=False))+16 for m in messages)+budget+32>CONTEXT_TOKENS:raise ValueError('English songwriter context budget exceeded')
 with inference_progress():
  result=model.create_chat_completion(messages=messages,grammar=LlamaGrammar.from_string(grammar(spec),verbose=False),max_tokens=budget,temperature=.65,seed=seed)
 choice=result['choices'][0]
 if choice.get('finish_reason')!='stop':raise ValueError('English songwriter output incomplete')
 return json.loads(choice['message']['content'])

def english(value):
 value=unicodedata.normalize('NFKC',value)
 if any(unicodedata.category(c).startswith('L') and 'LATIN' not in unicodedata.name(c,'') for c in value):raise ValueError('English Latin-script text required')
 if any(ord(c)<32 and c not in '\n\r\t' for c in value):raise ValueError('Control characters in song text')

def normalized(line):return ' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?",line.lower().replace('’',"'")))

def render_lyrics(sections):return '\n\n'.join('['+label+']\n'+'\n'.join(sections[key]) for label,key in ORDER)

def validate_payload(p):
 validate(p,schema())
 for value in (p['title'],p['description'],p['story'],p['production'],*p['tags']):english(value)
 verses=[]
 for name,lines in p['sections'].items():
  for line in lines:
   english(line);words=normalized(line).split()
   if not 4<=len(words)<=12:raise ValueError('Lyric lines need 4-12 natural English words: '+name)
   if name not in ('chorus','prechorus'):verses.append(normalized(line))
 if len(set(verses))!=len(verses):raise ValueError('Repeated verse filler is not accepted')
 if len(set(map(normalized,p['sections']['chorus'])))!=4:raise ValueError('Chorus needs four distinct lines')
 if len(render_lyrics(p['sections']))>3900:raise ValueError('Lyrics exceed the singing-model text budget')
 if sum(len(t)+2 for t in p['tags'])>450:raise ValueError('English tag budget exceeded')
 if len({normalized(v['prompt']) for v in p['visuals']})!=6:raise ValueError('Six distinct lyric-related image compositions required')
 for visual in p['visuals']:
  english(visual['prompt']);english(visual['label'])
  if re.search(r'\b(toddler|nursery|cartoon|anime|baby animal)\b',visual['prompt'],re.I):raise ValueError('Cinematic adult-song imagery required')
 return p

def review_schema():
 return obj(dict(scores=obj({k:dict(type='integer',minimum=1,maximum=5) for k in ('english','emotional_arc','hook','singability','imagery')}),
  issues=dict(type='array',minItems=0,maxItems=5,items=text(8,180))))

def validate_song(song):
 raw={k:song[k] for k in schema()['properties']};validate_payload(raw)
 if song.get('format')!=VERSION or song.get('language')!='en' or song.get('vocal_gender') not in ('female','male'):raise ValueError('English singing manifest required')
 if not re.fullmatch(r'english-song-[A-Za-z0-9_-]{1,60}',song.get('run_id','')) or song.get('duration') not in (180,210,240,270,300):raise ValueError('Invalid English song request')
 if song.get('lyrics')!=render_lyrics(song['sections']):raise ValueError('Sung lyrics differ from the accepted sections')
 if song.get('lyrics_sha256')!=hashlib.sha256(song['lyrics'].encode()).hexdigest():raise ValueError('Accepted English lyrics changed')
 report=song.get('review',{});validate(report,review_schema())
 if min(report['scores'].values())<4 or report['issues']:raise ValueError('English editorial review has not passed')
 if not 40<=len(song.get('prompt',''))<=512:raise ValueError('Invalid English music caption')
 return song

def write(root,run_id,seconds=210,voice='female',history=(),request='Original emotional pop / soft-pop',model=ask):
 root=Path(root);path=root/'song.json'
 if path.exists():
  song=validate_song(json.loads(path.read_text()))
  if (song['run_id'],song['duration'],song['vocal_gender'],song['request'])!=(run_id,seconds,voice,request):raise ValueError('Saved song request differs; use a fresh identity')
  return song
 seed=int(digest(run_id)[:7],16)
 recent=[dict(title=h.get('title',''),chorus=h.get('chorus',[])) for h in history[-6:]]
 prompt=('Write an ORIGINAL English emotional soft-pop song for adult listeners, about a specific relationship moment with a hopeful or bittersweet emotional turn. '
  'Brief: '+request+'. Avoid existing songs, named artists, imitation, nursery chants and generic motivational slogans. '
  'Use natural conversational English, concrete sensory details and a memorable concise chorus. No forced inverted grammar or meaningless mixed metaphors. '
  'Verse 1 sets a real scene; verse 2 advances events, bridge changes perspective; outro resolves the central image. '
  'Each lyric line is 4-12 words, ideally 6-9, with comfortable two-bar phrasing. Use natural near-rhyme and varied line openings. '
  'Return sections verse1=4 lines, prechorus=2, chorus=4, verse2=4, bridge=4, outro=2. Do not repeat choruses yourself; software repeats the EXACT chorus. '
  'Title 20-65 characters: a specific memorable phrase grounded in the chorus, emotionally intriguing but accurate, no clickbait claims or artist names. English description 150-600 characters: name the central relationship moment and emotional payoff in the first two sentences, natural English, no keyword stuffing. Story 100-450 characters, 5-10 relevant music/mood tags, bpm 78-104, key one of '+str(KEYS)+'. '
  'Production caption 80-240 characters describing instruments and arrangement, no artist names. Target '+str(seconds)+' seconds, mature '+voice+' lead, clear English singing. '
  'Six cinematic landscape background prompts, each 120-350 characters with a short label. Depict six different moments/places/objects from this lyric story. '
  'Repeat one coherent complementary warm amber/cool teal color palette/time of day. Bright luminous focal subject, rich saturated color, clear tonal separation, readable at mobile size; avoid muddy underexposed scenes. Opening composition doubles as thumbnail: one large story-related focal object off-center, clean upper quarter for title overlay. Prefer landscapes and meaningful objects over faces/hands. No nursery cartoons, lettering, split screens or cloned compositions. '
  'Avoid recent titles and chorus wording: '+json.dumps(recent)+'. Return only the structured song JSON.')
 for attempt in range(3):
  try:
   candidate=model(prompt,schema(),seed+attempt);atomic(root/f'lyrics-draft-{attempt}.json',candidate);validate_payload(candidate)
   lyrics=render_lyrics(candidate['sections']);lyric_hash=hashlib.sha256(lyrics.encode()).hexdigest()
   if any(h.get('lyrics_sha256')==lyric_hash or h.get('title','').casefold()==candidate['title'].casefold() or [normalized(x) for x in h.get('chorus',[])]==list(map(normalized,candidate['sections']['chorus'])) for h in history if h.get('run_id')!=run_id):raise ValueError('Song title, chorus or lyrics already reserved')
   critique=model('Independently critique this English emotional pop song. Score 1-5 for idiomatic English, emotional arc, memorable hook, singability and concrete imagery. '
    'List specific defects, including forced rhyme, filler and awkward word stress; empty issues only if release-ready as WRITTEN. Do not score the unheard audio. '+json.dumps(candidate),review_schema(),seed+100+attempt)
   atomic(root/f'lyrics-review-{attempt}.json',critique);validate(critique,review_schema())
   if min(critique['scores'].values())<4 or critique['issues']:
    prompt+='\nRewrite a complete improved song addressing these editorial issues: '+json.dumps(critique);continue
   song=dict(candidate,format=VERSION,run_id=run_id,request=request,language='en',duration=seconds,vocal_gender=voice,lyrics=lyrics,lyrics_sha256=lyric_hash,review=critique)
   song['prompt']=(f'English emotional soft-pop, {voice} adult lead vocals, intimate clear diction, {song["bpm"]} BPM, {song["key"]}, 4/4. '+song['production']+' Expressive sung verses, memorable repeated chorus, evolving full arrangement, short natural ending. No narration.')[:512]
   validate_song(song);atomic(path,song);return song
  except (ValueError,ValidationError) as e:
   reason=('field '+'.'.join(map(str,e.absolute_path))+' violates '+e.validator+'='+str(e.validator_value)[:80]) if isinstance(e,ValidationError) else str(e)
   print(json.dumps(dict(stage='English lyrics',attempt=attempt+1,error_type=type(e).__name__,reason=reason)),flush=True)
   prompt+='\nCorrect: '+reason+'. Return the complete improved song.'
 raise ValueError('English lyric quality failed three attempts; no canned lyrics substituted')
