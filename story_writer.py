"""Fresh Hindi emotional stories, persisted before expensive CPU generation."""
import copy
import hashlib
import json
import re
import unicodedata
import threading
import time
from pathlib import Path
from difflib import SequenceMatcher

from story_format import FORMAT, MIN_WORDS, MAX_WORDS, is_short

VERSION = 'hindi-emotional-story-v1'
SCENE_COUNT = 48
VOICES = {'narrator': 'hm_omega', 'male': 'hm_psi', 'female': 'hf_alpha'}
STYLE = ('Cute colorful 3D storybook cartoon. Rounded soft shapes, adorable expressive faces, '
         'bright pastel colors, soft cinematic lighting, large expressive eyes, polished 3D rendering, '
         'detailed beautiful environment, soft depth of field, '
         'wide landscape, no text.')


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


def normalized(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    return ' '.join(''.join(c if unicodedata.category(c)[0] in 'LNM' else ' ' for c in text).split())


def text_hash(text):
    return hashlib.sha256(normalized(text).encode()).hexdigest()


def novelty_reason(story, history):
    for entry in history:
        if normalized(entry['title']) == normalized(story['title']):
            return 'title'
        if entry.get('hash') == text_hash(story['lyrics']):
            return 'text'
        old = normalized(entry.get('summary', ''))
        if old and SequenceMatcher(None, old, normalized(story['summary'])).ratio() > .78:
            return 'plot'
        old_lines = {normalized(line) for line in entry.get('lines', [])}
        lines = [normalized(s['text']) for s in story['scenes']]
        if old_lines and sum(line in old_lines for line in lines) >= 3:
            return 'repeated scenes'
    return None


def speech_issues(text):
    """Speech validity is about content, not an exact per-scene word count."""
    if not isinstance(text,str) or not text.strip() or len(text)>400:
        return ['text']
    letters=[c for c in text if c.isalpha()]
    if not letters or sum('\u0900'<=c<='\u097f' for c in letters)/len(letters)<.9:
        return ['hindi']
    return []


def repeated_scenes(scenes):
    seen = []
    repeated = set()
    for index, scene in enumerate(scenes):
        for sentence in re.split(r'[।.!?\n]+', scene['text']):
            line = normalized(sentence)
            if len(line.split()) < 3:
                continue
            for old in seen:
                if line == old or (min(len(line.split()), len(old.split())) >= 10 and
                                   SequenceMatcher(None, old, line, autojunk=False).ratio() >= .92):
                    repeated.add(index)
                    break
            seen.append(line)
    return sorted(repeated)


def validate_story(story):
    if story.get('content_type') != 'hindi_story' or story.get('writer_version') != VERSION:
        raise ValueError('Not a supported Hindi story manifest')
    if not 1 <= len(story['title']) <= 100 or not 1 <= len(story['description']) <= 4400:
        raise ValueError('Invalid story metadata length')
    scenes = story['scenes']
    if len(scenes) != SCENE_COUNT:
        raise ValueError('A complete 48-scene story is required')
    for i, scene in enumerate(scenes):
        if scene['index'] != i or scene['speaker'] not in VOICES:
            raise ValueError('Invalid scene identity or speaker')
        words = scene['text'].split()
        if speech_issues(scene['text']):
            raise ValueError('Spoken scene must be nonempty bounded Devanagari Hindi text')
        letters = [c for c in scene['text'] if c.isalpha()]
        if not letters or sum('\u0900' <= c <= '\u097f' for c in letters)/len(letters) < .9:
            raise ValueError('Speech must be Hindi Devanagari')
        if not 20 <= len(scene['visual']) <= 360:
            raise ValueError('Scene image description is missing or overlong')
    total = sum(len(s['text'].split()) for s in scenes)
    minimum, maximum = (MIN_WORDS, MAX_WORDS) if is_short(story) else (1000, 1600)
    if not minimum<=total<=maximum:
        raise StoryValidationError('story_word_budget',dict(
            total_words=total,minimum_words=minimum,maximum_words=maximum))
    if is_short(story):
        if any(s['speaker'] != 'narrator' for s in scenes):
            raise ValueError('Short stories require one narrator')
        visuals=story.get('visuals',{})
        if (set(visuals)!={str(i) for i in range(SCENE_COUNT)} or
                any(not isinstance(v,str) or not 30<=len(v)<=360 for v in visuals.values()) or
                not isinstance(story.get('thumbnail_prompt'),str) or not 80<=len(story['thumbnail_prompt'])<=360 or
                type(story.get('thumbnail_scene')) is not int or not 0<=story['thumbnail_scene']<SCENE_COUNT):
            raise ValueError('Short story requires a complete story-grounded visual plan and thumbnail scene')
        repeated = repeated_scenes(scenes)
        if repeated:
            raise StoryValidationError('repeated_story_lines', dict(scenes=repeated))
    elif not 30 <= sum(s['speaker'] == 'narrator' for s in scenes) <= 40:
        raise ValueError('Story requires 30-40 narrator scenes and some dialogue')
    if story['lyrics'] != '\n'.join(s['text'] for s in scenes):
        raise ValueError('Spoken script differs from scene script')
    return story


class StoryValidationError(ValueError):
    """Safe validation diagnostics without raw model or credential content."""
    def __init__(self, code, details=None):
        super().__init__(code)
        self.code=code
        self.details=details or {}


def bound_prose(value, spec):
    """Bound planning prose at sentence/word boundaries, never spoken script."""
    value=' '.join(value.split())
    maximum=spec['maxLength']
    if len(value)<=maximum:
        return value
    prefix=value[:maximum]
    stops=[m.end() for m in re.finditer(r'[.!?।](?=\s|$)',prefix)]
    minimum=max(spec.get('minLength',0),maximum//2)
    if stops and stops[-1]>=minimum:
        return prefix[:stops[-1]]
    if len(value)>maximum and not value[maximum].isspace():
        prefix=prefix.rsplit(' ',1)[0] if ' ' in prefix else prefix
    return prefix.rstrip(' ,;:')


def planning_schema(schema):
    """Relax only prose limits at inference; never relax spoken-text limits."""
    result=copy.deepcopy(schema)
    if schema==OUTLINE:
        for field,spec in result['properties'].items():
            if field=='chapters':
                spec['items'].pop('maxLength',None)
            else:
                spec.pop('maxLength',None)
    else:
        def relax(node):
            if not isinstance(node,dict):
                return
            for field,spec in node.get('properties',{}).items():
                if field in ('visual','instruction'):
                    spec.pop('maxLength',None)
                else:
                    relax(spec)
            relax(node.get('items'))
        relax(result)
    return result


def normalize_planning(data, schema):
    result=copy.deepcopy(data)
    if schema==OUTLINE:
        for field,spec in schema['properties'].items():
            if field=='chapters':
                result[field]=[bound_prose(value,spec['items']) for value in result[field]]
            else:
                result[field]=bound_prose(result[field],spec)
    else:
        def normalize(value,spec):
            if isinstance(value,dict):
                for field,child in spec.get('properties',{}).items():
                    if field not in value:
                        continue
                    if field in ('visual','instruction'):
                        value[field]=bound_prose(value[field],child)
                    else:
                        normalize(value[field],child)
            elif isinstance(value,list) and 'items' in spec:
                for child in value:
                    normalize(child,spec['items'])
        normalize(result,schema)
    return result


def ask(schema, prompt, seed, tokens=3000, checkpoint=None):
    from lyrics_cpu import request_story, MODEL_ID
    from jsonschema import Draft202012Validator
    started=time.monotonic()
    stop=threading.Event()
    label=Path(checkpoint).name if checkpoint else 'story-request'
    def heartbeat():
        while not stop.wait(60):
            print(json.dumps(dict(phase='story model request running',request=label,elapsed_seconds=round(time.monotonic()-started))),flush=True)
    print(json.dumps(dict(phase='story model request started',request=label)),flush=True)
    reporter=threading.Thread(target=heartbeat,daemon=True)
    reporter.start()
    try:
        response = request_story('chat/completions', dict(model=MODEL_ID,
        messages=[{'role': 'system', 'content': 'You write original Hindi emotional motivational fiction for a general audience. Spoken text, title and description are Hindi Devanagari. Summary, characters, world, chapter planning, visual prompts and editorial instructions MUST be English with transliterated names. Return JSON only.'},
                  {'role': 'user', 'content': prompt}],
        response_format={'type': 'json_schema', 'json_schema': {'schema': planning_schema(schema)}},
        max_completion_tokens=tokens, seed=seed, temperature=.85))
    finally:
        stop.set()
        reporter.join(timeout=1)
    raw=json.loads(response['choices'][0]['message']['content'])
    if checkpoint:
        save_json(checkpoint,raw)
    result=normalize_planning(raw,schema)
    if result!=raw:
        fields=[field for field in result if result[field]!=raw[field]]
        print(json.dumps({'check':'story planning lengths normalized','fields':fields}),flush=True)
    Draft202012Validator(schema).validate(result)
    return result


def string(minimum, maximum):
    return {'type': 'string', 'minLength': minimum, 'maxLength': maximum}


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def english_planning(minimum,maximum):
    return dict(string(minimum,maximum),pattern=r'^[^\u0900-\u097f]*[A-Za-z][^\u0900-\u097f]*$')


OUTLINE = object_schema({
    'title': string(8, 90), 'description': string(30, 1200), 'summary': english_planning(100, 700),
    'characters': english_planning(60, 350), 'world': english_planning(30, 220),
    'chapters': {'type': 'array', 'minItems': 6, 'maxItems': 6, 'items': english_planning(40, 220)}})
ROW = object_schema({'speaker': {'type': 'string', 'enum': list(VOICES)},
                     'text': string(40, 400), 'visual': string(20, 360)})
CHAPTER = object_schema({'scenes': {'type': 'array', 'minItems': 8, 'maxItems': 8, 'items': ROW}})


def write_story(root, run_id, history):
    """Local sequential entry point uses the same repairable chapter writer."""
    from story_plan import prepare_outline,write_chapter,assemble_story
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    prepare_outline(root,run_id,history)
    for index in range(6):
        write_chapter(root,run_id,index)
    return assemble_story(root,run_id,history)


def scene_prompt(story, scene):
    # Same model and exact core style vocabulary as kids_rhymes.make_song.
    # Text conditioning guides consistency; it does not guarantee identical faces.
    return (scene['visual']+'. Cute colorful 3D storybook cartoon. '+story['characters']+'. '+
            story['world']+'. '+STYLE.replace('Cute colorful 3D storybook cartoon. ', ''))
