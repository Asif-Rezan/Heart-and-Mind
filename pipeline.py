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


def validate_song(song):
    for field in ('title', 'lyrics', 'prompt', 'description'):
        if not isinstance(song.get(field), str) or not song[field].strip():
            raise ValueError('Missing song ' + field)
    if len(song['title']) > 100 or len(song['description']) > 4400:
        raise ValueError('YouTube metadata too long')
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
    ('healing', 'Hindi uplifting folk pop', 'starting again after loss; rediscovering self-worth', 'grounded hopeful vocal, acoustic guitar, flute, warm percussion', 'PHIR SE JEE LE'),
    ('romance', 'Hindi celebratory dance pop', 'joyful reunion; choosing each other again', 'playful energetic vocal, dholak, bass, bright synths, danceable rhythm', 'DIL KA JASHN'),
    ('heartbreak', 'Hindi ghazal-inspired contemporary ballad', 'unspoken affection; a letter that never reaches its reader', 'measured expressive vocal, harmonium, tabla, sarangi, subtle piano', 'ANKAHI MOHABBAT'),
    ('healing', 'Hindi soulful cinematic pop', 'finding hope in solitude; courage for a new morning', 'soulful solo vocal, piano, strings, gradual percussion build', 'NAYI SUBAH'),
    ('romance', 'Hindi monsoon lo-fi pop', 'remembering a first meeting in the rain', 'soft intimate vocal, mellow keys, muted guitar, relaxed lo-fi beat', 'BAARISH AUR TUM'),
)


def song_profile(day):
    # Calendar rotation works even in the isolated lyrics job, which has no Drive history.
    return SONG_PROFILES[dt.date.fromisoformat(day).toordinal() % len(SONG_PROFILES)]


def make_song(day, history, draft_path=None):
    mood, genre, story, arrangement, hook = song_profile(day)
    prompt = f'''Write an ORIGINAL Hindi song for Heart and Mind on {day}.
    Today's direction: {genre}. Emotional story: {story}.
    Musical arrangement: {arrangement}. Visual mood: {mood}.
    Develop a specific original scene, characters and emotional progression in this direction.
    Do not recycle a generic love song. Use concrete sensory details, conversational poetic
    Hindi, fresh metaphors, natural breath-length phrases and consistent viewpoint.
    Plan a clear beginning, emotional turn in verse 2, and resolution in the bridge/outro.
    Write a memorable 2-4 line chorus with one distinctive central phrase; repeat that chorus
    consistently. Verses should advance the story, not paraphrase the chorus. Keep a singable
    syllable pattern within each section; avoid forced rhyme, filler and unrelated imagery.
    Structure: [Intro], [Verse 1] (6-8 lines), [Pre-Chorus] (2-4), [Chorus] (4),
    [Verse 2] (6-8), [Chorus], [Bridge] (4), [Final Chorus], [Outro] (2).
    Intro may be instrumental. Target 140-180 sung words for a complete 3-6 minute song.
    पूरा गीत हिंदी की देवनागरी लिपि में लिखो। रोमन लिपि में हिंदी मत लिखो।
    Every sung line must use Devanagari, never English transliteration; bracket labels in English.
    Never copy existing lyrics, melodies, titles, or imitate a named singer.
    Avoid these previous titles: {json.dumps(history, ensure_ascii=False)}.
    Return JSON only with these fields:
    title: unique Hindi song name plus romanized name and ONE accurate English genre/search
      phrase (e.g. Hindi Romantic Song), <=100 characters. Put the song name first.
      No famous artist names, film claims, clickbait, 'viral', keyword lists or invented popularity.
    lyrics: complete song as above. prompt: English musical production directions including
      {genre}, {arrangement}, tempo, dynamic arc and clear Hindi diction. No named artists.
    duration: integer seconds 180-360, aim 240.
    No spoken CTA. Keep the song concise: 140-180 sung words, including repeated choruses.
    Do not add metadata, descriptions, tags or image prompts to this response.
    Privately revise for originality, story, meter and singability before returning.'''
    from lyrics_cpu import MODEL_ID, request_story
    core_schema = {'type': 'object', 'additionalProperties': False,
        'required': ['title', 'lyrics', 'prompt', 'duration'],
        'properties': {
            'title': {'type': 'string', 'minLength': 1, 'maxLength': 100},
            'lyrics': {'type': 'string', 'minLength': 500, 'pattern': '[ऀ-ॿ]'},
            'prompt': {'type': 'string', 'minLength': 20, 'maxLength': 600},
            'duration': {'type': 'integer', 'minimum': 180, 'maximum': 360}}}
    def request(instructions, schema, tokens):
        result = request_story('chat/completions', {'model': MODEL_ID,
            'messages': [{'role': 'system', 'content': 'You are an original Hindi songwriter and truthful music editor. Write natural, singable Hindi in Devanagari.'},
                         {'role': 'user', 'content': instructions}],
            'response_format': {'type': 'json_schema', 'json_schema': {'schema': schema}},
            'max_completion_tokens': tokens})
        return json.loads(result['choices'][0]['message']['content'])

    # Keep the full song and packaging out of the same completion. Small CPU models
    # otherwise have to satisfy many tight text bounds while writing long Hindi lyrics.
    from jsonschema import Draft202012Validator
    if draft_path is not None and draft_path.exists():
        song = json.loads(draft_path.read_text())
        Draft202012Validator(core_schema).validate(song)
    else:
        song = request(prompt, core_schema, 6000)
        if draft_path is not None:
            temporary = draft_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(song, ensure_ascii=False, indent=2))
            temporary.replace(draft_path)
    packaging_schema = {'type': 'object', 'additionalProperties': False,
        'required': ['description', 'tags', 'thumbnail_text', 'background_prompt', 'thumbnail_prompt'],
        'properties': {
            'description': {'type': 'string', 'minLength': 20, 'maxLength': 1200},
            'tags': {'type': 'array', 'minItems': 8, 'maxItems': 12,
                     'items': {'type': 'string', 'minLength': 1, 'maxLength': 40}},
            'thumbnail_text': {'type': 'string', 'minLength': 3, 'maxLength': 26, 'pattern': '^[A-Za-z0-9 !?]+$'},
            'background_prompt': {'type': 'string', 'minLength': 40, 'maxLength': 380},
            'thumbnail_prompt': {'type': 'string', 'minLength': 40, 'maxLength': 380}}}
    packaging_prompt = f'''Package the supplied original Hindi song. Do not rewrite the song.
    Genre: {genre}. Visual mood: {mood}. Return only these five JSON fields.
    description: first two lines describe this specific song's story and genre naturally in
      Hindi and English. Follow with a short listening context, an accurate original AI music
      credit and at most 3 relevant hashtags. Maximum 1200 characters. No invented credits, links or keyword stuffing.
    tags: 8-12 distinct relevant search terms covering the Hindi and romanized song name,
      Hindi music, exact genre, mood and Heart and Mind. No unrelated artists/trends.
    thumbnail_text: 2-4 words in ASCII Romanized Hindi from the chorus or emotional promise,
      <=26 characters, not the channel name; sample mood only: {hook}.
    background_prompt: 20-30 English words depicting a specific scene from THIS song's story,
      setting, time, weather, colors and emotional action. For love/reunion show a fully clothed
      adult South Asian couple; for loss/healing show a reflective adult or symbolic landscape.
      Cinematic photorealism, subjects on right half, no lettering. Put the scene first.
    thumbnail_prompt: a DIFFERENT 20-25 word English visual composition of the same emotional
      story, closer expressive adult faces on the right, strong light contrast, dark empty left
      half for a hook. No celebrities, child subjects, text, logos, collages or stock-poster wording.
    Description: 60-100 words maximum. Tags must EACH be 40 characters or fewer.
    The thumbnail hook must contain ONLY ASCII English letters, spaces, ! or ?; no Devanagari.
    Keep both scene prompts under 380 characters each. Do not repeat lyrics in the response.
    Song to package: {json.dumps(song, ensure_ascii=False)}'''
    song.update(request(packaging_prompt, packaging_schema, 3000))
    song['visual_mood'] = mood  # Chosen locally, never ask the model to reproduce a fixed enum.
    return validate_song(song)


def metadata_tags(song):
    # Old saved songs remain publishable; new songs carry their own search terms.
    candidates = song.get('tags', []) + ['Heart and Mind', 'Hindi song', 'original Hindi music']
    result = []
    for tag in candidates:
        tag = tag.strip()
        if tag and tag.casefold() not in {item.casefold() for item in result}:
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
        state['upload_started'] = True
        save()
        request = client.videos().insert(part='snippet,status', body={
            'snippet': {'title': song['title'], 'description': song['description'] +
                '\n\nOriginal AI-generated Hindi music by Heart and Mind. Created with ACE-Step 1.5.',
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


def run(run_id, defer_drive_cleanup=False):
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
                if (root/'song.json').exists() else make_song(day, [h['title'] for h in history[-30:]], root/'song-draft.json'))
        digest = hashlib.sha256(song['lyrics'].encode()).hexdigest()
        if any(h.get('hash') == digest or h['title'] == song['title'] for h in history):
            raise RuntimeError('Duplicate song rejected')
        state.update(song=song, hash=digest)
        save()
    song = validate_song(state['song'])
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
            from song_images import generate_song_images
            generate_song_images(root, song)
            render(root)
        validate_duration(duration(root/'video.mp4'))
        for name in ('song.json', 'video.mp4', 'thumbnail.jpg', 'background-source.png', 'thumbnail-source.png', 'image-manifest.json'):
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
    parser.add_argument('--defer-drive-cleanup', action='store_true',
                        help='Leave verified media cleanup to the separate workflow job')
    args = parser.parse_args()
    try:
        run(args.run_id, defer_drive_cleanup=args.defer_drive_cleanup)
    except Exception as error:
        # Avoid leaking OAuth/API credentials through raw exception response bodies.
        print('Pipeline failed: ' + type(error).__name__ + '. Inspect checkpoint and configuration.')
        raise SystemExit(1)
