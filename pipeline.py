"""Hindi song -> ACE-Step 1.5 -> HD visualizer -> verified public YouTube video."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from zoneinfo import ZoneInfo
from storage import Store, required


class DuplicateSongError(RuntimeError):
    """A safe diagnostic; never expose raw API responses or checkpoint contents."""


def pipeline_failure_message(error):
    from lyric_quality import LyricQualityError
    if isinstance(error, LyricQualityError):
        return ('Pipeline failed [lyrics_quality_rejected]: bounded lyric revisions did not pass. '
                'Saved draft and lyrics-quality.json contain recovery diagnostics; music was not started.')
    if isinstance(error, DuplicateSongError):
        return ('Pipeline failed [duplicate_song]: lyrics or title already published. '
                'Create a fresh song with a new run ID; do not retry duplicate media.')
    return ('Pipeline failed: ' + type(error).__name__ +
            '. Inspect checkpoint and configuration.')



def safe_api_details(error):
    """Expose only known API status/reason codes, never URLs or response prose."""
    status = getattr(getattr(error, 'resp', None), 'status', None)
    if not isinstance(status, int):
        return {}
    allowed = {'quotaExceeded', 'dailyLimitExceeded', 'rateLimitExceeded',
        'userRateLimitExceeded', 'storageQuotaExceeded', 'insufficientPermissions',
        'forbidden', 'authError', 'notFound', 'backendError', 'internalError',
        'uploadLimitExceeded', 'invalidTitle', 'invalidDescription', 'invalidTags',
        'invalidCategoryId', 'videoNotFound', 'youtubeSignupRequired'}
    reasons = set()
    try:
        payload = json.loads(error.content)
        for item in payload.get('error', {}).get('errors', []):
            if item.get('reason') in allowed:
                reasons.add(item['reason'])
    except (ValueError, TypeError, AttributeError):
        pass
    return {'http_status': status, 'reasons': sorted(reasons)}

def song_duplicate_reason(song, history, run_id=None):
    digest = hashlib.sha256(normalize_lyrics(song['lyrics']).encode()).hexdigest()
    entries = [entry for entry in history if run_id is None or entry.get('run') != run_id]
    if any(entry.get('hash') == digest for entry in entries):
        return 'lyrics'
    if any(entry.get('title') == song['title'] for entry in entries):
        return 'title'
    return None


def lyric_title_candidates(lyrics, search_term, year):
    """Bounded public titles from actual sung lines, without model retries."""
    candidates = []
    suffix = f' | {search_term} {year}'
    for line in normalize_lyrics(lyrics).splitlines():
        line = re.sub(r'\[[^]]*\]', '', line).strip()
        words = re.findall(r'[\u0900-\u097f]+', line)
        phrase = ' '.join(words[:6])
        if len(words) < 2 or not phrase:
            continue
        while len(phrase + suffix) > 100 and ' ' in phrase:
            phrase = phrase.rsplit(' ', 1)[0]
        title = phrase + suffix
        if len(title) <= 100 and title not in candidates:
            candidates.append(title)
    return candidates


def normalize_lyrics(text):
    """Repair escaped layout markers without changing the Hindi words."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\\+(?:r\\+n|n|r)', '\n', text)
    return re.sub(r'\\+t', ' ', text)


def validate_song(song):
    for field in ('title', 'lyrics', 'prompt', 'description'):
        if not isinstance(song.get(field), str) or not song[field].strip():
            raise ValueError('Missing song ' + field)
    if len(song['title']) > 100 or len(song['description']) > 4400:
        raise ValueError('YouTube metadata too long')
    song['lyrics'] = normalize_lyrics(song['lyrics'])
    if not re.search(r'[\u0900-\u097f]', song['lyrics']):
        raise ValueError('Hindi Devanagari lyrics required')
    if not 180 <= song.get('duration', 0) <= 360:
        raise ValueError('Song must be 180-360 seconds')
    if 'tags' in song and (not isinstance(song['tags'], list) or
            not all(isinstance(tag, str) and 0 < len(tag.strip()) <= 40 for tag in song['tags'])):
        raise ValueError('Invalid song tags')
    if 'visual_mood' in song and song['visual_mood'] not in ('romance', 'heartbreak', 'healing'):
        raise ValueError('Invalid visual mood')
    if 'thumbnail_text' in song and not re.fullmatch(r'[A-Za-z0-9 !?]{3,26}', song['thumbnail_text']):
        raise ValueError('Invalid thumbnail hook')
    for field in ('background_prompt', 'thumbnail_prompt'):
        if field in song and (not isinstance(song[field], str) or not 40 <= len(song[field]) <= 380):
            raise ValueError('Invalid image prompt')
    return song


SONG_PROFILES = (
    ('romance', 'Hindi romantic acoustic pop', 'new love; an ordinary shared moment becomes unforgettable', 'warm intimate solo vocal, acoustic guitar, piano, gentle live drums', 'TERE SAATH'),
    ('heartbreak', 'Hindi sad piano ballad', 'a quiet goodbye; acceptance rather than blame', 'restrained vulnerable solo vocal, felt piano, cello, spacious drums', 'ADHURI BAATEIN'),
    ('romance', 'Hindi indie dream pop', 'long-distance love; two lives connected by a small daily ritual', 'airy expressive vocal, clean electric guitar, atmospheric synths, soft groove', 'DOOR HOKE BHI'),
    ('healing', 'Hindi uplifting folk pop', 'learning to trust love again after a painful separation', 'grounded hopeful vocal, acoustic guitar, flute, warm percussion', 'PHIR SE JEE LE'),
    ('romance', 'Hindi celebratory dance pop', 'joyful reunion; choosing each other again', 'playful energetic vocal, dholak, bass, bright synths, danceable rhythm', 'DIL KA JASHN'),
    ('heartbreak', 'Hindi ghazal-inspired contemporary ballad', 'unspoken affection; a letter that never reaches its reader', 'measured expressive vocal, harmonium, tabla, sarangi, subtle piano', 'ANKAHI MOHABBAT'),
    ('healing', 'Hindi soulful cinematic pop', 'missing a loved one in solitude; a tender promise to meet again', 'soulful solo vocal, piano, strings, gradual percussion build', 'NAYI SUBAH'),
    ('romance', 'Hindi monsoon lo-fi pop', 'remembering a first meeting in the rain', 'soft intimate vocal, mellow keys, muted guitar, relaxed lo-fi beat', 'BAARISH AUR TUM'),
)


def song_profile(day):
    # Calendar rotation works even in the isolated lyrics job, which has no Drive history.
    return SONG_PROFILES[dt.date.fromisoformat(day).toordinal() % len(SONG_PROFILES)]


def vocal_gender_for_day(day):
    # Calendar days, not day-of-month parity: stays alternating across month/leap boundaries.
    anchor = dt.date(2026, 10, 28)
    return ('male', 'female')[(dt.date.fromisoformat(day)-anchor).days % 2]


def make_song(day, history, draft_path=None, generation_id=None, vocal_gender_override='auto'):
    mood, genre, story, arrangement, hook = song_profile(day)
    if vocal_gender_override not in ('auto', 'male', 'female'):
        raise ValueError('Vocal choice must be auto, male or female')
    vocal_gender = (vocal_gender_for_day(day) if vocal_gender_override == 'auto' else vocal_gender_override)
    opposite_gender = 'female' if vocal_gender == 'male' else 'male'
    search_term = {'romance': 'Hindi Romantic Song', 'heartbreak': 'Hindi Sad Song',
                   'healing': 'Heart Touching Hindi Song'}[mood]
    hindi_term = {'romance': 'हिंदी रोमांटिक गाना', 'heartbreak': 'हिंदी दर्द भरा गाना',
                  'healing': 'दिल छू लेने वाला हिंदी गाना'}[mood]
    year = day[:4]
    identity = generation_id or day
    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:4], 'big') % (2**31 - 3)
    places = ('a quiet railway platform', 'a rooftop garden', 'a riverside tea stall',
              'a bookshop at closing time', 'a lantern-lit courtyard', 'a seaside promenade',
              'a mountain bus stop', 'a rain-washed city street')
    objects = ('a folded letter', 'a shared umbrella', 'an old photograph', 'a cup of tea',
               'a handwritten note', 'a train ticket', 'a pressed flower', 'a familiar scarf')
    scene = f'{places[seed % len(places)]}, with {objects[(seed // len(places)) % len(objects)]}'
    from lyric_quality import GUIDE, VERSION as LYRIC_VERSION, assess, review
    prompt = f'''Write an original romantic/emotional Hindi album song.
    Genre: {genre}. Feeling: {story}. Setting inspiration: {scene}.
    Unique brief {identity}; do not sing this identifier. Write for a solo {vocal_gender} singer.
    सरल, स्वाभाविक हिंदी में प्रेम और रिश्ते की बात लिखो। हर पंक्ति का साफ़ अर्थ हो।
    प्यार, इंतज़ार, दूरी, मिलने की चाह या मन की अनकही बात चुनो। उपदेश मत लिखो।
    {GUIDE}
    Return title, lyrics and duration only. lyrics is an OBJECT of line arrays:
    verse_1 (4), pre_chorus (2), chorus (4), verse_2 (4), bridge (2), outro (2).
    Each array item is ONE sung Hindi line, no heading or newline. Write the chorus
    once; the editor repeats it automatically. The final repeated song has 26 lines.
    title: original Hindi name | short Romanized name | {search_term} {year}, <=100 characters.
    duration: 195. No famous singer/film claims, no translations or copied lyrics.
    Avoid previous titles: {json.dumps([entry['title'] for entry in history if entry.get('title')], ensure_ascii=False)}.'''
    from lyrics_cpu import MODEL_ID, request_story
    core_schema = {'type': 'object', 'additionalProperties': False,
        'required': ['title', 'lyrics', 'prompt', 'duration'],
        'properties': {
            'title': {'type': 'string', 'minLength': 1, 'maxLength': 100},
            'lyrics': {'type': 'string', 'minLength': 500, 'pattern': '[ऀ-ॿ]'},
            'prompt': {'type': 'string', 'minLength': 20, 'maxLength': 600},
            'duration': {'type': 'integer', 'minimum': 180, 'maximum': 360},
            'vocal_gender': {'type': 'string', 'enum': ['male', 'female']},
            'song_date': {'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$'}}}
    # Production directions are controlled input, not creative prose. Keeping them
    # outside the completion prevents maxLength retries from discarding good lyrics.
    tempos = (86, 72, 92, 96, 112, 76, 82, 80)
    bpm = tempos[SONG_PROFILES.index(song_profile(day))]
    prompt += f'\nWrite for {bpm} BPM in 4/4 with two-bar vocal phrases.'
    production_prompt = (f'Solo {vocal_gender} lead vocal; no {opposite_gender} singer or duet. '
        f'{genre}; {arrangement}; {bpm} BPM, 4/4. '
        'Warm melodic tone, natural Hindi diction, legato phrasing. '
        'Two-bar vocal phrases; match melody to Hindi word stress, never rush syllables. '
        'Repeat the chorus melody; leave breath gaps between lines. '
        'Vocal entry within 8s; catchy chorus by 40s. Intimate verses, lifted chorus, '
        'sparse bridge, final chorus, resolved ending. Vocal-forward balanced mix, '
        'warm bass, restrained reverb; no speech or long solos.')
    generation_schema = dict(core_schema, required=['title', 'lyrics', 'duration'],
        properties={key: value for key, value in core_schema['properties'].items()
                    if key in ('title', 'lyrics', 'duration')})
    def request(instructions, schema, tokens, seed_offset=0):
        from copy import deepcopy
        from lyric_quality import section_schema, render_sections
        from jsonschema import Draft202012Validator
        wire_schema = deepcopy(schema)
        structured_lyrics = 'lyrics' in wire_schema.get('properties', {})
        if structured_lyrics:
            wire_schema['properties']['lyrics'] = section_schema()
            instructions += ('\nReturn lyrics as an object of six line arrays: verse_1 (4), '
                'pre_chorus (2), chorus (4), verse_2 (4), bridge (2), outro (2). '
                'Each item is one sung Devanagari line without headings or newlines. '
                'Write chorus once; repeated choruses are inserted locally.')
        result = request_story('chat/completions', {'model': MODEL_ID,
            'messages': [{'role': 'system', 'content': 'तुम मौलिक हिंदी प्रेमगीत लिखने वाले गीतकार और सख़्त संपादक हो। स्वाभाविक, अर्थपूर्ण और गाने योग्य हिंदी लिखो।'},
                         {'role': 'user', 'content': instructions}],
            'response_format': {'type': 'json_schema', 'json_schema': {'schema': wire_schema}},
            'max_completion_tokens': tokens, 'seed': (seed + seed_offset) % (2**31 - 3)})
        value = json.loads(result['choices'][0]['message']['content'])
        # Validate at this boundary too: a malformed transport response must never
        # become a cacheable song, even when request_story is replaced by a client.
        Draft202012Validator(wire_schema).validate(value)
        if structured_lyrics:
            value['lyrics'] = render_sections(value['lyrics'])
        return value

    # Keep the full song and packaging out of the same completion. Small CPU models
    # otherwise have to satisfy many tight text bounds while writing long Hindi lyrics.
    from jsonschema import Draft202012Validator
    fresh_core = not (draft_path is not None and draft_path.exists())
    if not fresh_core:
        song = json.loads(draft_path.read_text())
        Draft202012Validator(core_schema).validate(song)
        if vocal_gender_override != 'auto' and song.get('vocal_gender') != vocal_gender_override:
            raise ValueError('Saved song voice differs from the request; use a new run ID')
    else:
        song = request(prompt, generation_schema, 6000)
        song['prompt'] = production_prompt
        song['vocal_gender'] = vocal_gender
        song['song_date'] = day
        # Keep the new lyric form matched to a focused 3m15s arrangement.
        song['duration'] = 195
        Draft202012Validator(core_schema).validate(song)
        song['lyrics'] = normalize_lyrics(song['lyrics'])
    if draft_path is not None:
        temporary = draft_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(song, ensure_ascii=False, indent=2))
        temporary.replace(draft_path)
    if song_duplicate_reason(song, history) == 'lyrics':
        raise DuplicateSongError()
    # Saved cores retain their original voice, even when retried on the next calendar day.
    editorial_voice = song.get('vocal_gender')
    narrator_instruction = (f'Keep the first-person narrator consistent with a solo {editorial_voice} singer.'
                            if editorial_voice else 'Preserve the original narrator and grammatical gender.')
    # Revision checkpoints apply to new/versioned drafts only. Never rewrite historical
    # unversioned cores that may already have matching generated audio.
    quality_path = draft_path.with_name('lyrics-quality.json') if draft_path is not None else None
    quality = json.loads(quality_path.read_text()) if quality_path is not None and quality_path.exists() else {}
    needs_review = fresh_core or bool(quality.get('version'))
    if needs_review and not (quality.get('version') == LYRIC_VERSION and
            quality.get('passed') and quality.get('semantic_review', {}).get('passed') and quality.get('lyrics_hash') == assess(song['lyrics'])['lyrics_hash']):
        edit_schema = {'type': 'object', 'additionalProperties': False, 'required': ['lyrics'],
            'properties': {'lyrics': core_schema['properties']['lyrics']}}
        report = assess(song['lyrics'])
        for attempt in range(3):
            # Save a pending report before inference so an interruption cannot silently
            # promote an unreviewed draft to an approved song on resume.
            if quality_path is not None:
                quality_path.write_text(json.dumps(dict(report, passed=False), ensure_ascii=False, indent=2))
            edit_prompt = f'''Act as a native Hindi romantic lyricist and vocal arranger.
            Polish this song for {genre}, {bpm} BPM in 4/4. Keep usable romantic ideas and the narrator.
            Replace nonsensical imagery or broken Hindi entirely; do not preserve a bad hook.
            Relationship direction: {story}. Setting inspiration: {scene}.
            {narrator_instruction}
            {GUIDE}
            Read/sing each phrase aloud privately. Check idiomatic meaning, grammar,
            natural end-rhyme, emotional sincerity and breath points, not just word count.
            Fix these written-phrasing problems: {json.dumps(report['issues']+report.get('warnings',[]), ensure_ascii=False)}
            Estimated vowel lengths (heuristic, not exact sung matra):
            {json.dumps(report['sections'], ensure_ascii=False)}
            Return only JSON lyrics, never commentary, translations or credits.
            Original lyrics: {song['lyrics']}'''
            song['lyrics'] = normalize_lyrics(request(edit_prompt, edit_schema, 5000, 100+attempt)['lyrics'])
            report = assess(song['lyrics'])
            if report['passed']:
                critique = review(request, song['lyrics'], genre, bpm, editorial_voice, attempt,
                    phrasing_warnings=report.get('warnings',[]))
                report['semantic_review'] = critique
                report['passed'] = critique['passed']
                report['issues'] += critique['issues']
                if not critique['passed'] and not report['issues']:
                    report['issues'].append('Editorial critique failed; revise meaning, Hindi, rhyme and phrasing')
            print(json.dumps({'phase':'lyric revision checked','attempt':attempt+1,
                'passed':report['passed'],'word_count':report['word_count'],
                'issue_count':len(report['issues'])}),flush=True)
            if draft_path is not None:
                temporary = draft_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(song, ensure_ascii=False, indent=2))
                temporary.replace(draft_path)
                temporary = quality_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                temporary.replace(quality_path)
            if report['passed']:
                quality = report
                break
        else:
            from lyric_quality import LyricQualityError
            raise LyricQualityError('Lyrics need revision before music generation: ' + '; '.join(report['issues']))
    # Check saved cores too: resumed artifacts may predate the current history.
    # A title-only correction keeps good lyrics instead of regenerating the music.
    if song_duplicate_reason(song, history) == 'lyrics':
        raise DuplicateSongError()
    avoided_titles = [entry['title'] for entry in history if entry.get('title')]
    if song['title'] in avoided_titles:
        # Models can repeat a rejected title despite instructions and new seeds.
        # Select a real sung phrase instead; no random suffix or internal run ID.
        candidates = lyric_title_candidates(song['lyrics'], search_term, year)
        song['title'] = next((title for title in candidates if title not in avoided_titles), '')
        if not song['title']:
            raise DuplicateSongError()
        print(json.dumps({'phase': 'title conflict recovered', 'source': 'song lyrics'}), flush=True)
    if draft_path is not None:
        temporary = draft_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(song, ensure_ascii=False, indent=2))
        temporary.replace(draft_path)
    from story_visual_contract import ENGLISH_PATTERN
    packaging_schema = {'type': 'object', 'additionalProperties': False,
        'required': ['description', 'tags', 'thumbnail_text', 'background_prompt', 'thumbnail_prompt'],
        'properties': {
            'description': {'type': 'string', 'minLength': 20, 'maxLength': 1200},
            'tags': {'type': 'array', 'minItems': 8, 'maxItems': 12,
                     'items': {'type': 'string', 'minLength': 1, 'maxLength': 40}},
            'thumbnail_text': {'type': 'string', 'minLength': 3, 'maxLength': 26, 'pattern': '^[A-Za-z0-9 !?]+$'},
            'background_prompt': {'type': 'string', 'minLength': 40, 'maxLength': 380, 'pattern':ENGLISH_PATTERN},
            'thumbnail_prompt': {'type': 'string', 'minLength': 40, 'maxLength': 380, 'pattern':ENGLISH_PATTERN},
            'visual_scenes': {'type':'array','minItems':4,'maxItems':8,'items':{'type':'string','minLength':40,'maxLength':160,'pattern':ENGLISH_PATTERN}}}}
    packaging_prompt = f'''Package the supplied original Hindi song. Do not rewrite the song.
    Genre: {genre}. Visual mood: {mood}. Return the listed JSON fields.
    description: 60-100 words, readable Hindi and English. The first 150 characters must
      naturally include this song's name and "{search_term}". The first two lines should explain
      its specific emotion/story and include "{hindi_term}". Then give one natural listening
      context and an honest sentence about the arrangement. Include "new Hindi song {year}"
      and "original Hindi music" only once each where they fit naturally. Do not repeat a list
      of keywords. No invented artist/label credits, external links, technical explanations,
      internal tool names, model names, providers or software names. Do not add hashtags or
      production credits; the publisher adds the channel credit and three relevant hashtags.
    tags: 8-12 distinct relevant search phrases, each <=40 characters. Prioritize this song's
      short Devanagari name, Romanized name, "{search_term}", "{hindi_term}",
      "new Hindi song {year}", the actual musical genre, one suitable listening context,
      "original Hindi music", and "Heart and Mind". Use specific Hindi/English searches,
      not broad unrelated self-help terms. No other singers, films, tools, models or trend bait.
    thumbnail_text: 2-4 familiar Romanized Hindi words, <=26 ASCII characters, expressing
      the chorus's emotional promise. Use natural Hindi transliteration, never mixed English
      slogans such as MILE AGAIN. Prefer a complete relatable phrase over generic love labels.
      Complement the title instead of copying it. No channel name, fake claims or punctuation bait.
      Mood reference only, do not copy mechanically: {hook}.
    background_prompt: 16-22 English words describing one beautiful, lyric-specific music-video scene.
      Show the emotional action and the actual location, weather, meaningful prop and light from these lyrics.
      Romance: a beautiful South Asian adult couple sharing a tender moment. Separation: the same young
      adult couple visibly apart, with quiet longing. Healing: a beautiful young adult South Asian woman
      in a hopeful moment. All adults are 25-35, fully clothed; use original fictional faces.
      Use a medium-wide environmental view with recognizable people, scenic depth and a clear lower edge
      for the waveform. Natural skin, soft diffused face light, balanced warm/cool color and an uncluttered
      scene. Keep both people within the frame. No enormous cropped male face, elderly man, copied actor,
      vintage poster, collage, title lettering, captions, logos or watermarks.
    thumbnail_prompt: a DIFFERENT 16-22 word English scene selling this song's real emotional promise.
      Romance: exactly one beautiful young adult South Asian couple, tender eye contact or a joyful reunion.
      Separation: exactly that adult couple with readable longing and a little distance; no fake cheerful
      romance or exaggerated tears. Healing: one beautiful young adult South Asian woman with hopeful relief.
      All adults are 25-35, naturally expressive and fully clothed. Close chest-up framing, both couple
      faces clearly separated, sharp eyes, soft natural skin light and a softly blurred lyric-specific setting.
      One clear emotional moment that reads at phone size; no unrelated older man, collage or busy props.
      Use the full frame for the scene; no blank typography panel, no red paint strokes.
      This is a TEXT-FREE cinematic scene: no Hindi, Romanized Hindi or English lettering, song title, hook,
      year, badge, logo, watermark or signature. Do not ask the image model to draw writing.
      The thumbnail_text field is retained only as metadata;
      it is never rendered on the thumbnail or sent to the image model.
    visual_scenes: 4-8 concise English scenes (40-160 characters each) following THIS song's
      actual verse/chorus/bridge emotional progression. Use the same fully clothed adult
      couple (healing: adult woman), the lyric-specific setting and meaningful objects.
      Describe visible actions, not camera/typography. No unrelated drama or wealth.
      They will be illustrated in realistic cinematic 3D storybook style.
    Description: 60-100 words maximum. Tags must EACH be 40 characters or fewer.
    The thumbnail hook must contain ONLY ASCII English letters, spaces, ! or ?; no Devanagari.
    Keep both scene prompts under 380 characters each. Do not repeat lyrics in the response.
    Song to package: {json.dumps(song, ensure_ascii=False)}'''
    song['lyrics'] = normalize_lyrics(song['lyrics'])
    song.update(request(packaging_prompt, packaging_schema, 3000))
    song['visual_mood'] = mood  # Chosen locally, never ask the model to reproduce a fixed enum.
    if needs_review:
        song['lyric_quality_version'] = LYRIC_VERSION
        song['lyric_quality'] = quality
    return validate_song(song)


PUBLIC_INTERNAL_NAMES = re.compile(r'(?i)\b(?:ace[- ]?step|ssd[- ]?1b|segmind|qwen[\w.-]*|whisper|diffusers|hugging\s*face|llama|openai|gpt[- ]?\d|github actions)\b')


def upload_description(song):
    """Keep the song summary public, with only verified channel credit and hashtags."""
    text = re.sub(r'#[^\s#]+', '', song['description'])
    sentences = re.split(r'(?<=[.!?।])\s+|\n+', text)
    sentences = [part.strip() for part in sentences if part.strip() and
        not PUBLIC_INTERNAL_NAMES.search(part) and
        not re.search(r'(?i)(?:created|produced|sung|composed|music|lyrics|vocals)\s+(?:by|:)', part)]
    mood = song.get('visual_mood', 'romance')
    hashtag = {'romance': '#HindiRomanticSong', 'heartbreak': '#HindiSadSong',
               'healing': '#HeartTouchingSong'}.get(mood, '#HindiMusic')
    return ('\n'.join(sentences) + '\n\nOriginal Hindi music by Heart and Mind.\n\n'
            '#HindiSong #HindiMusic ' + hashtag)


def metadata_tags(song):
    # Old saved songs remain publishable; new songs carry their own search terms.
    candidates = song.get('tags', []) + ['Heart and Mind', 'Hindi song', 'original Hindi music']
    result = []
    for tag in candidates:
        tag = tag.strip()
        if tag and not PUBLIC_INTERNAL_NAMES.search(tag) and tag.casefold() not in {item.casefold() for item in result}:
            # YouTube counts quotes around tags containing spaces toward its 500-character limit.
            if sum(len(item) + (2 if ' ' in item else 0) + 1 for item in result + [tag]) <= 480:
                result.append(tag)
    return result


def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of', 'default=nw=1:nk=1', str(path)], text=True))


def validate_duration(seconds):
    if not 180 <= seconds <= 360:
        raise ValueError('Measured song/video duration outside 3-6 minutes')


def render(root):
    from artwork import create_artwork
    song = json.loads((root/'song.json').read_text())
    if song.get('video_format')=='hindi-music-storybook-5s-v1':
        from music_video import render as render_motion
        return render_motion(root,song)
    create_artwork(root, song)
    subprocess.run(['ffmpeg', '-y', '-loop', '1', '-i', str(root/'cover.png'), '-i', str(root/'song.wav'),
        '-filter_complex', '[1:a]asplit=2[a][v];[v]showwaves=s=1600x90:mode=line:colors=0xf9b4cc:rate=25,format=rgba[w];[0:v][w]overlay=160:980:shortest=1,format=yuv420p[out]',
        '-map', '[out]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-c:a', 'aac', '-b:a', '320k', '-t', str(duration(root/'song.wav')), '-shortest', '-movflags', '+faststart', str(root/'video.mp4')],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    validate_duration(duration(root/'video.mp4'))


def youtube_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    client = build('youtube', 'v3', credentials=Credentials.from_authorized_user_info(
        json.loads(required('YOUTUBE_TOKEN_JSON'))), cache_discovery=False)
    items = client.channels().list(part='id,snippet', mine=True).execute().get('items', [])
    expected = required('EXPECTED_CHANNEL_ID')
    if len(items) != 1 or items[0]['id'] != expected:
        raise RuntimeError('Wrong YouTube channel; select Heart and Mind')
    return client


def publish(client, root, song, state, save):
    from googleapiclient.http import MediaFileUpload
    if not state.get('video_id'):
        if state.get('upload_started'):
            raise RuntimeError('Ambiguous upload; reconcile YouTube before retry to avoid duplicates')
        state['upload_description'] = upload_description(song)
        state['upload_started'] = True
        save()
        request = client.videos().insert(part='snippet,status', body={
            'snippet': {'title': song['title'], 'description': state['upload_description'],
                'categoryId': '10', 'defaultLanguage': 'hi', 'defaultAudioLanguage': 'hi',
                'tags': metadata_tags(song)},
            'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False,
                       'containsSyntheticMedia': True}},
            media_body=MediaFileUpload(str(root/'video.mp4'), resumable=True, chunksize=8*1024*1024))
        result = None
        while result is None:
            _, result = request.next_chunk(num_retries=5)
        state['video_id'] = result['id']
        save()
    if not state.get('thumbnail_uploaded'):
        client.thumbnails().set(videoId=state['video_id'],
            media_body=MediaFileUpload(str(root/'thumbnail.jpg'))).execute()
        state['thumbnail_uploaded'] = True
        save()
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        items = client.videos().list(part='snippet,status,processingDetails,contentDetails',
                                    id=state['video_id']).execute().get('items', [])
        if not items:
            raise RuntimeError('Uploaded video unavailable')
        video = items[0]
        if video['snippet']['channelId'] != required('EXPECTED_CHANNEL_ID'):
            raise RuntimeError('Uploaded channel mismatch')
        status = video['status']
        if status.get('uploadStatus') in ('failed', 'rejected', 'deleted'):
            raise RuntimeError('YouTube rejected upload')
        if status.get('privacyStatus') != 'public':
            raise RuntimeError('YouTube did not retain public visibility; inspect project/channel restrictions')
        if status.get('uploadStatus') == 'processed' and video.get('contentDetails', {}).get('definition') == 'hd':
            state['phase'] = 'published'
            save()
            return
        time.sleep(20)
    raise TimeoutError('HD processing pending; rerun same run ID')


def run(run_id, defer_drive_cleanup=False, require_prepared=False):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
        raise ValueError('Invalid run ID')
    root = Path('output')/run_id
    root.mkdir(parents=True, exist_ok=True)
    store = Store()
    client = youtube_client()  # Verify accounts before expensive generation.
    key = f'runs/{run_id}/state.json'
    state = store.load(key, {})
    save = lambda: store.save(key, state)
    history = store.load('history.json', [])
    if state.get('phase') == 'published':
        if not any(h['run'] == run_id for h in history):
            history.append({'run': run_id, 'title': state['song']['title'],
                            'hash': state['hash'], 'video_id': state['video_id']})
            store.save('history.json', history)
        if not defer_drive_cleanup:
            from cleanup_drive import cleanup
            cleanup(store, client, run_id, state)
        print('Already published: ' + state['video_id'])
        return
    if not state.get('song'):
        day = dt.datetime.now(ZoneInfo('Asia/Dhaka')).date().isoformat()
        song = (validate_song(json.loads((root/'song.json').read_text()))
                if (root/'song.json').exists() else make_song(day, history, root/'song-draft.json', generation_id=run_id))
        if not (root/'song.json').exists():song['video_format']='hindi-music-storybook-5s-v1'
        digest = hashlib.sha256(song['lyrics'].encode()).hexdigest()
        if song_duplicate_reason(song, history, run_id):
            raise DuplicateSongError()
        state.update(song=song, hash=digest)
        save()
    if require_prepared and (root/'song.json').is_file():
        prepared=validate_song(json.loads((root/'song.json').read_text()))
        if normalize_lyrics(prepared['lyrics'])!=normalize_lyrics(state['song']['lyrics']):
            raise RuntimeError('Prepared song differs from the reserved music')
        if song_duplicate_reason(prepared,history,run_id):raise DuplicateSongError()
        state['song']=prepared
        state['hash']=hashlib.sha256(prepared['lyrics'].encode()).hexdigest()
        save()
    song = validate_song(state['song'])
    if require_prepared:
        missing=[name for name in ('song.wav','video.mp4','thumbnail.jpg') if not (root/name).is_file()]
        if missing:raise RuntimeError('Prepared music publication assets missing')
    (root/'song.json').write_text(json.dumps(song, ensure_ascii=False, indent=2))
    if not (root/'song.wav').exists():
        fid = store.find(f'runs/{run_id}/song.wav')
        if fid:
            store.download(fid, root/'song.wav')
        else:
            from music_cpu import generate
            generate(song, root/'song.wav', state, save)
    validate_duration(duration(root/'song.wav'))
    if not state.get('video_id'):
        store.upload(root/'song.wav', f'runs/{run_id}/song.wav')
        if not (root/'video.mp4').exists():
            if song.get('video_format')=='hindi-music-storybook-5s-v1':
                from music_video import prepare_timeline,generate_images
                prepare_timeline(root,song);generate_images(root,song)
            else:
                from song_images import generate_song_images
                generate_song_images(root, song)
            render(root)
        validate_duration(duration(root/'video.mp4'))
        if song.get('video_format')=='hindi-music-storybook-5s-v1':
            from music_video import validate_rendered
            validate_rendered(root,song)
        for name in ('song.json', 'video.mp4', 'thumbnail.jpg', 'background-source.png', 'thumbnail-source.png', 'image-manifest.json','music-video-timing.json','music-render-state.json'):
            if (root/name).exists():
                store.upload(root/name, f'runs/{run_id}/{name}')
    elif not (root/'thumbnail.jpg').exists():
        store.download(store.find(f'runs/{run_id}/thumbnail.jpg'), root/'thumbnail.jpg')
    publish(client, root, song, state, save)
    if not any(h['run'] == run_id for h in history):
        history.append({'run': run_id, 'title': song['title'], 'hash': state['hash'], 'video_id': state['video_id']})
        store.save('history.json', history)
    if not defer_drive_cleanup:
        from cleanup_drive import cleanup
        cleanup(store, client, run_id, state)
    print(json.dumps({'phase': state['phase'], 'video_id': state['video_id']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--require-prepared',action='store_true',help='Publish only completed local media; never synthesize in the publish job')
    parser.add_argument('--defer-drive-cleanup', action='store_true',
                        help='Leave verified media cleanup to the separate workflow job')
    args = parser.parse_args()
    try:
        run(args.run_id, defer_drive_cleanup=args.defer_drive_cleanup,require_prepared=args.require_prepared)
    except Exception as error:
        # Avoid leaking OAuth/API credentials through raw exception response bodies.
        print(pipeline_failure_message(error))
        raise SystemExit(1)
