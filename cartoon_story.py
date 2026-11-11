"""Checkpointed English family stories; no nursery-rhyme or Hindi constraints."""
import hashlib
import json
import re
from pathlib import Path
from jsonschema import ValidationError, validate

VERSION = 'english-family-cartoon-v1'
CAST = {
    'narrator': {'voice': 'af_heart', 'description': 'Warm natural adult narrator'},
    'mira': {'voice': 'af_bella', 'description': 'Mira, a curious young adult woman with a short dark bob, teal jacket and brown trousers'},
    'theo': {'voice': 'am_michael', 'description': 'Theo, a thoughtful young adult man with curly brown hair, amber vest and navy trousers'},
}
STYLE = 'Expressive rounded 3D family adventure cartoon, warm cinematic light, richly illustrated natural setting, no text or panels. '
ACTIONS = ['approach_friend', 'follow_friend', 'approach_ball', 'react', 'wait']


def text(minimum, maximum):
    return {'type': 'string', 'minLength': minimum, 'maxLength': maximum, 'pattern': r'^[\x09\x0A\x0D\x20-\x7E\u00A0-\u024F\u1E00-\u1EFF\u2000-\u206F]+$'}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


OUTLINE = obj(dict(title=text(8, 90), summary=text(100, 700), setting=text(30, 220),
    lesson=text(15, 180), beats={'type': 'array', 'minItems': 20, 'maxItems': 20, 'items': text(20, 180)}))
SHOT = obj(dict(speaker={'enum': list(CAST)}, text=text(60, 240), visual=text(40, 350),
    action={'enum': ACTIONS}, emotion={'enum': ['curious', 'amused', 'worried', 'surprised', 'relieved', 'thoughtful']},
    sfx={'enum': ['none', 'footsteps', 'discovery']}))
SLOTS = [('narration_open','narrator'),('mira_line','mira'),('theo_line','theo'),('narration_close','narrator')]
SPOKEN_SHOT = obj({key: value for key, value in SHOT['properties'].items() if key != 'speaker'})
SPOKEN_SHOT['properties']['text'] = text(1, 240)
BATCH = obj({name:SPOKEN_SHOT for name,_ in SLOTS})


def atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False)); temp.replace(path)


def request(schema, prompt, seed):
    from lyrics_cpu import request_story, MODEL_ID
    response = request_story('chat/completions', dict(model=MODEL_ID, seed=seed, language='en',
        max_completion_tokens=3000, messages=[{'role': 'system', 'content':
            'You write original English family adventure cartoons that adults and children can enjoy together. '
            'Humor, believable mistakes, emotional reactions and satisfying consequences come before teaching. '
            'Never write nursery rhymes, songs, baby talk, lectures, dangerous demonstrations or factual claims you cannot support.'},
            {'role': 'user', 'content': prompt}], response_format={'type': 'json_schema',
            'json_schema': {'name': 'family_story', 'schema': schema}}))
    result = json.loads(response['choices'][0]['message']['content']); validate(result, schema)
    return result


def shot_issue(shot, others=(), speaker=None):
    spoken = shot.get('text')
    if isinstance(spoken, str):
        count = len(spoken.split())
        if not 18 <= count <= 38:
            return dict(reason='word_count', word_count=count, minimum=18, maximum=38)
    try:
        validate(shot,SHOT)
    except ValidationError as error:
        return dict(reason='schema_'+error.validator,field='.'.join(map(str,error.absolute_path)))
    if speaker and shot['speaker']!=speaker:
        return dict(reason='speaker',expected=speaker,actual=shot['speaker'])
    key=' '.join(shot['text'].split()).casefold()
    if any(' '.join(s['text'].split()).casefold()==key for s in others):
        return dict(reason='duplicate_dialogue')
    return None


def validate_shots(shots):
    if len(shots) not in (16, 20):
        raise ValueError('A complete family story needs twenty shots (or a saved sixteen-shot episode)')
    for shot in shots:
        validate({k: shot[k] for k in SHOT['required']}, SHOT)
        if not 18 <= len(shot['text'].split()) <= 38:
            raise ValueError('Spoken shot needs 18-38 English words; regenerate the affected batch')
    if len({s['text'].lower() for s in shots}) != len(shots):
        raise ValueError('Repeated spoken shots are not accepted')
    if not {'mira', 'theo', 'narrator'}.issubset({s['speaker'] for s in shots}):
        raise ValueError('Story needs narration and both character voices')


def image_prompt(outline, shot):
    cast = '. '.join(CAST[k]['description'] for k in ('mira', 'theo'))
    staging = {'approach_friend': 'Mira starts on the left, separated from waiting Theo on the right by a clear walkway. ',
        'follow_friend': 'Theo leads on a clear path; Mira follows a few steps behind. ',
        'approach_ball': 'A single ball is visible on the ground beside the clear path. ',
        'react': 'A clear expressive reaction, separate full bodies visible. ', 'wait': 'The friends pause thoughtfully. '}[shot['action']]
    return ('Warm 3D family cartoon. Mira: short dark bob, teal jacket, brown trousers. '
            'Theo: curly brown hair, amber vest, navy trousers. Two young adult friends. '
            +staging+shot['visual']+'. Expression: '+shot['emotion']+'. '+outline['setting']+
            '. Same faces and clothes, separate full bodies, visible feet, open ground, no text.')


def plan(root, run_id, topic='A funny everyday misunderstanding resolved through cooperation', history=()):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    identity = dict(version=VERSION, run_id=run_id, topic=topic, cast=CAST)
    draft_path = root/'cartoon-draft.json'
    draft = json.loads(draft_path.read_text()) if draft_path.exists() else dict(identity=identity, batches=[])
    if draft.get('identity') != identity:
        raise ValueError('Saved cartoon request differs; use a new run ID')
    seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:7], 16)
    if not draft.get('outline'):
        draft['outline'] = request(OUTLINE, 'Plan a complete 2-3 minute adventure for Mira and Theo. Topic: '+topic+
            '. Twenty sequential story beats: opening problem, discovery, believable mistake, funny complication, '
            'cooperation and earned resolution. One shared story for all ages, no separate adult/child versions. '
            'Use exactly these recurring characters: '+json.dumps(CAST)+'. Avoid these recent titles: '+
            json.dumps([h.get('title') for h in history[-20:]]), seed)
        atomic(draft_path, draft)
    outline = draft['outline']
    # Keep accepted sixteen-shot checkpoints resumable without rewriting their story.
    outline_schema = json.loads(json.dumps(OUTLINE))
    outline_schema['properties']['beats'].update(minItems=16, maxItems=20)
    validate(outline, outline_schema)
    if len(outline['beats']) not in (16, 20):
        raise ValueError('Saved outline must have sixteen or twenty complete story beats')
    while len(draft['batches']) < len(outline['beats'])//4:
        batch = len(draft['batches']); prior = [s for b in draft['batches'] for s in b]
        context = ('Outline: '+json.dumps(outline)+'. Write ONLY beats '+str(batch*4+1)+' to '+str(batch*4+4)+
            '. Earlier accepted shots: '+json.dumps(prior)+'. Each shot has 22-30 spoken English words '
            '(hard limit 18-38), no stage directions in spoken text. The four named fields are sequential shots: '
            'narration_open is narrator, mira_line is Mira, theo_line is Theo, narration_close is narrator. '
            'Visual shows the same event with Mira and Theo, preserving their clothes. '
            'Use meaningful movement: approach_friend means Mira approaches waiting Theo, follow_friend means Mira '
            'follows leading Theo, approach_ball requires a real visible ball in this story beat. Otherwise react/wait. '
            'No obligatory dancing, no repeated dialogue.')
        pending=draft.get('pending_batch')
        if pending is None:
            result=request(BATCH,context,seed+batch*100)
            # Old saved/test array responses remain readable; new constrained
            # generation uses named slots so voice coverage is guaranteed.
            pending=(result['shots'] if 'shots' in result else
                [dict(result[name],speaker=speaker) for name,speaker in SLOTS])
            if len(pending)!=4: raise ValueError('Story batch must contain four complete shots')
            draft['pending_batch']=pending
            atomic(draft_path,draft)
        for index in range(4):
            others=prior+pending[:index]+pending[index+1:]
            for attempt in range(3):
                issue=shot_issue(pending[index],others,SLOTS[index][1])
                if issue is None: break
                rejection=dict(batch=batch,shot=index,attempt=attempt,**issue)
                draft.setdefault('batch_rejections',[]).append(rejection)
                atomic(draft_path,draft)
                print(json.dumps(dict(phase='repair rejected cartoon shot',**rejection)),flush=True)
                if attempt==2:
                    raise ValueError(f'Cartoon batch {batch} shot {index} failed two targeted repairs: '+issue['reason']+
                                     '; accepted shots and rejection diagnostics retained')
                from lyrics_cpu import CARTOON_WORD_PATTERN
                slot, speaker = SLOTS[index]
                spec = obj({**SHOT['properties'], 'speaker': {'enum': [speaker]},
                            'text': {**SHOT['properties']['text'], 'pattern': CARTOON_WORD_PATTERN}})
                beat = outline['beats'][batch * 4 + index]
                repaired = request(
                    spec, f'Rewrite only {slot} as {speaker}. Story summary: {outline["summary"]}. '
                    f'Exact story beat: {beat}. Rejected shot: {json.dumps(pending[index])}. '
                    f'Exact rejection: {json.dumps(issue)}. Keep the same event with 22–30 spoken English words. '
                    'Use plain ASCII punctuation and no stage directions. Preserve established story continuity. '
                    f'Do not repeat these lines: {json.dumps([shot["text"] for shot in others])}',
                    seed + batch * 100 + 10 + index * 3 + attempt)
                pending[index]=repaired
                atomic(draft_path,draft)
        draft['batches'].append(pending)
        draft.pop('pending_batch',None)
        atomic(draft_path,draft)
        print(json.dumps(dict(phase='cartoon batch accepted',batch=batch+1,shots=len(draft['batches'])*4)),flush=True)
    shots = [s for b in draft['batches'] for s in b]; validate_shots(shots)
    if any(h.get('title') == outline['title'] for h in history):
        raise ValueError('Story title already used; choose a new run ID/topic')
    scenes = [dict(s, index=i, prompt=image_prompt(outline, s)) for i, s in enumerate(shots)]
    song = dict(format=VERSION, language='en', title=outline['title'], description=outline['summary']+
        '\n\nAn original Heart and Mind family cartoon about '+outline['lesson']+
        '\nAI-assisted illustrations, animation and synthetic character voices.',
        lyrics='\n'.join(s['text'] for s in shots), prompt=topic, story_summary=outline['summary'],
        cast=CAST, scenes=scenes, tags=['Heart and Mind', 'family cartoon', 'animated story', 'learning through stories'])
    atomic(root/'song.json', song)
    return song


def validate_manifest(song, timed=False):
    if song.get('format') != VERSION or song.get('language') != 'en' or song.get('cast') != CAST:
        raise ValueError('Unsupported cartoon format, language or voice cast')
    validate_shots(song['scenes'])
    if not 1 <= len(song['title']) <= 100 or not 1 <= len(song['description']) <= 4400:
        raise ValueError('Invalid cartoon public metadata')
    if [s['index'] for s in song['scenes']] != list(range(len(song['scenes']))):
        raise ValueError('Cartoon shot indices must be continuous')
    if timed:
        end = 0
        for scene in song['scenes']:
            if scene['start'] != end or not 1 <= scene['end']-scene['start'] <= 25:
                raise ValueError('Invalid voice-derived cartoon timeline')
            end = scene['end']
        if abs(end-song['duration']) > .001 or not 120 <= end <= 300:
            raise ValueError('Cartoon must contain 2-5 minutes of complete speech and scene timing')
    return song
