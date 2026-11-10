"""Checkpointed English family stories; no nursery-rhyme or Hindi constraints."""
import hashlib
import json
import re
from pathlib import Path
from jsonschema import validate

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
    lesson=text(15, 180), beats={'type': 'array', 'minItems': 16, 'maxItems': 16, 'items': text(20, 180)}))
SHOT = obj(dict(speaker={'enum': list(CAST)}, text=text(60, 240), visual=text(40, 350),
    action={'enum': ACTIONS}, emotion={'enum': ['curious', 'amused', 'worried', 'surprised', 'relieved', 'thoughtful']},
    sfx={'enum': ['none', 'footsteps', 'discovery']}))
BATCH = obj(dict(shots={'type': 'array', 'minItems': 4, 'maxItems': 4, 'items': SHOT}))


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


def validate_shots(shots):
    if len(shots) != 16:
        raise ValueError('A complete family story needs sixteen shots')
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
            '. Sixteen sequential story beats: opening problem, discovery, believable mistake, funny complication, '
            'cooperation and earned resolution. One shared story for all ages, no separate adult/child versions. '
            'Use exactly these recurring characters: '+json.dumps(CAST)+'. Avoid these recent titles: '+
            json.dumps([h.get('title') for h in history[-20:]]), seed)
        atomic(draft_path, draft)
    outline = draft['outline']; validate(outline, OUTLINE)
    while len(draft['batches']) < 4:
        batch = len(draft['batches']); prior = [s for b in draft['batches'] for s in b]
        feedback = ''
        for attempt in range(3):
            result = request(BATCH, 'Outline: '+json.dumps(outline)+'. Write ONLY beats '+str(batch*4+1)+' to '+str(batch*4+4)+
                '. Earlier accepted shots: '+json.dumps(prior)+'. Each shot has one speaker, 22-30 spoken English words '
                '(hard limit 18-38); narrator carries action and characters speak naturally. No stage directions in spoken text. '
                'Visual shows the same story event with Mira and Theo, preserving their clothes. Meaningful movement only: '
                'approach_friend means Mira approaches waiting Theo, follow_friend means Mira follows leading Theo; '
                'approach_ball only if this story event really involves a visible ball. Otherwise choose react/wait. '
                'No obligatory dancing. Include narrator, Mira and Theo in every four-shot batch. '+feedback, seed+batch*10+attempt)
            if (all(18 <= len(s['text'].split()) <= 38 for s in result['shots'])
                    and {'narrator','mira','theo'}.issubset({s['speaker'] for s in result['shots']})
                    and len({s['text'].lower() for s in prior+result['shots']}) == len(prior)+4):
                break
            feedback = 'Rewrite these four shots: use 22-30 words each, include all three speakers and never repeat accepted dialogue.'
        else:
            raise ValueError('Cartoon batch word count failed three attempts; accepted batches retained')
        draft['batches'].append(result['shots']); atomic(draft_path, draft)
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
    if [s['index'] for s in song['scenes']] != list(range(16)):
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
