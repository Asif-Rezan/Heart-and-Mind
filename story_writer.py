"""Fresh Hindi emotional stories, persisted before expensive CPU generation."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

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
        if not 18 <= len(words) <= 38:
            raise ValueError('Each spoken scene requires 18-38 words')
        letters = [c for c in scene['text'] if c.isalpha()]
        if not letters or sum('\u0900' <= c <= '\u097f' for c in letters)/len(letters) < .9:
            raise ValueError('Speech must be Hindi Devanagari')
        if not 20 <= len(scene['visual']) <= 360:
            raise ValueError('Scene image description is missing or overlong')
    total = sum(len(s['text'].split()) for s in scenes)
    if not 1100 <= total <= 1500:
        raise ValueError('Story needs 1100-1500 Hindi words for 8-12 minutes')
    if not 30 <= sum(s['speaker'] == 'narrator' for s in scenes) <= 40:
        raise ValueError('Story requires 30-40 narrator scenes and some dialogue')
    if story['lyrics'] != '\n'.join(s['text'] for s in scenes):
        raise ValueError('Spoken script differs from scene script')
    return story


def ask(schema, prompt, seed, tokens=3000):
    from lyrics_cpu import request_story, MODEL_ID
    response = request_story('chat/completions', dict(model=MODEL_ID,
        messages=[{'role': 'system', 'content': 'You write original Hindi emotional motivational fiction for a general audience. Return JSON only.'},
                  {'role': 'user', 'content': prompt}],
        response_format={'type': 'json_schema', 'json_schema': {'schema': schema}},
        max_completion_tokens=tokens, seed=seed, temperature=.85))
    return json.loads(response['choices'][0]['message']['content'])


def string(minimum, maximum):
    return {'type': 'string', 'minLength': minimum, 'maxLength': maximum}


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


OUTLINE = object_schema({
    'title': string(8, 90), 'description': string(30, 1200), 'summary': string(100, 700),
    'characters': string(60, 350), 'world': string(30, 220),
    'chapters': {'type': 'array', 'minItems': 6, 'maxItems': 6, 'items': string(40, 220)}})
ROW = object_schema({'speaker': {'type': 'string', 'enum': list(VOICES)},
                     'text': string(40, 400), 'visual': string(20, 360)})
CHAPTER = object_schema({'scenes': {'type': 'array', 'minItems': 8, 'maxItems': 8, 'items': ROW}})


def write_story(root, run_id, history):
    root = Path(root)
    manifest = root/'story.json'
    if manifest.exists():
        return validate_story(json.loads(manifest.read_text()))
    others = [h for h in history if h.get('run') != run_id]
    recent = [{'title': h['title'], 'summary': h.get('summary', '')} for h in others[-20:]]
    draft_path = root/'story-draft.json'
    draft = json.loads(draft_path.read_text()) if draft_path.exists() else {}
    seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:7], 16)
    for revision in range(draft.get('revision', 0), 3):
        if 'outline' not in draft:
            outline = ask(OUTLINE,
                'Create a NEW complete 8-12 minute Hindi emotional motivational story. '
                'Use everyday Indian family/work/study situations, credible struggle, a meaningful choice and an earned hopeful ending. '
                'No instant millionaire miracles, sermons, copied plots or nursery rhymes. '
                'One male narrator, at most one male and one female speaking character; no other dialogue speakers. '
                'Hindi Devanagari title/description. English summary, six chronological chapter beats, '
                'compact fixed character ages/clothes/faces and pastel 3D storybook world. '
                'Characters may be adults/parents; match the existing cute colorful 3D illustration aesthetic. '
                'Each chapter will contain eight scenes and approximately 200-240 Hindi words. '
                'Avoid these previous stories: '+json.dumps(recent, ensure_ascii=False), seed+revision*10000, 2800)
            draft = {'revision': revision, 'outline': outline, 'chapters': []}
            save_json(draft_path, draft)
        outline = draft['outline']
        while len(draft['chapters']) < 6:
            chapter = len(draft['chapters'])
            previous = draft['chapters'][-1]['scenes'][-2:] if chapter else []
            correction = ''
            for attempt in range(3):
                data = ask(CHAPTER,
                    'Write chapter '+str(chapter+1)+' of this fixed story: '+json.dumps(outline, ensure_ascii=False)+
                    '\nPrior ending: '+json.dumps(previous, ensure_ascii=False)+
                    '\nReturn exactly eight consecutive scenes: six narrator scenes and two dialogue scenes (male or female). '
                    'Each text must contain 24-30 space-separated Hindi Devanagari words; write full natural sentences. '
                    'Do not include speaker names, stage directions or emotion tags in spoken text. '
                    'Narrator narrates; dialogue uses only the established male/female characters. '
                    'English visual describes the exact action, character and setting in that scene, under 220 characters. '
                    'Do not repeat earlier scenes. Last chapter resolves the conflict through action. '+correction,
                    seed+revision*10000+chapter*100+attempt*10, 4000)
                counts = [len(s['text'].split()) for s in data['scenes']]
                if all(22 <= n <= 34 for n in counts) and sum(s['speaker']=='narrator' for s in data['scenes']) == 6:
                    break
                correction = 'Prior attempt failed word/speaker counts '+str(counts)+'. Use six narrator scenes and two dialogue scenes; 24-30 words each.'
            else:
                raise ValueError('Hindi chapter failed word/speaker requirements; saved draft retained')
            draft['chapters'].append(data)
            save_json(draft_path, draft)
        scenes = []
        for chapter in draft['chapters']:
            for row in chapter['scenes']:
                scenes.append(dict(row, index=len(scenes)))
        story = dict(content_type='hindi_story', writer_version=VERSION, run_id=run_id,
            title=outline['title'], description=outline['description']+'\n\nयह एक मौलिक काल्पनिक कहानी है। आवाज़, चित्र और संगीत AI की सहायता से बनाए गए हैं।\n#HindiStory #MotivationalStory',
            summary=outline['summary'], characters=outline['characters'], world=outline['world'],
            scenes=scenes, lyrics='\n'.join(s['text'] for s in scenes),
            tags=['Hindi motivational story','Hindi emotional story','प्रेरणादायक कहानी','Hindi kahani'])
        try:
            validate_story(story)
            reason = novelty_reason(story, others)
        except ValueError:
            reason = 'story length or language validation'
        if not reason:
            save_json(manifest, story)
            return story
        draft = {'revision': revision+1}
        save_json(draft_path, draft)
    raise ValueError('Fresh story validation failed; no template or duplicate will be uploaded')


def scene_prompt(story, scene):
    # Same model and exact core style vocabulary as kids_rhymes.make_song.
    # Text conditioning guides consistency; it does not guarantee identical faces.
    return (scene['visual']+'. Cute colorful 3D storybook cartoon. '+story['characters']+'. '+
            story['world']+'. '+STYLE.replace('Cute colorful 3D storybook cartoon. ', ''))
