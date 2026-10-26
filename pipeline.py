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
    return song


def make_song(day, history):
    prompt = f'''Write an ORIGINAL Hindi song for Heart and Mind on {day}.
    Themes: love, longing, healing, hope. Natural poetic Hindi in Devanagari.
    पूरा गीत हिंदी की देवनागरी लिपि में लिखो। रोमन लिपि में हिंदी मत लिखो।
    Example of the required script: तेरी यादों में मेरा दिल खो गया।
    Every sung line must use Hindi characters, never English transliteration.
    Never copy existing lyrics, melodies, titles, or imitate a named singer.
    Avoid these previous titles: {json.dumps(history, ensure_ascii=False)}.
    Return JSON only: title (Hindi plus short English, <=100 chars), lyrics
    (complete verses, chorus, bridge, outro with bracket section labels),
    prompt (English musical style, instruments and vocal direction), duration
    (integer seconds 180-360, aim 240), description (Hindi/English, <=4000 chars).
    Lyrics should support a complete 3-6 minute vocal song. No spoken CTA.'''
    from lyrics_cpu import MODEL_ID, request_story
    schema = {'type': 'object', 'additionalProperties': False,
        'required': ['title', 'lyrics', 'prompt', 'duration', 'description'],
        'properties': {
            'title': {'type': 'string', 'minLength': 1, 'maxLength': 100},
            'lyrics': {'type': 'string', 'minLength': 500, 'pattern': '[ऀ-ॿ]'},
            'prompt': {'type': 'string', 'minLength': 20},
            'duration': {'type': 'integer', 'minimum': 180, 'maximum': 360},
            'description': {'type': 'string', 'minLength': 20, 'maxLength': 4000}}}
    result = request_story('chat/completions', {'model': MODEL_ID,
        'messages': [{'role': 'system', 'content': 'You are an original Hindi songwriter. Write natural Hindi in Devanagari.'},
                     {'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_schema', 'json_schema': {'schema': schema}},
        'max_completion_tokens': 5000})
    return validate_song(json.loads(result['choices'][0]['message']['content']))



def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of', 'default=nw=1:nk=1', str(path)], text=True))


def validate_duration(seconds):
    if not 180 <= seconds <= 360:
        raise ValueError('Measured song/video duration outside 3-6 minutes')


def render(root):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1920, 1080), '#131827')
    draw = ImageDraw.Draw(image)
    for radius in range(450, 0, -5):
        color = (25 + radius // 9, 25, 65 + radius // 5)
        draw.ellipse((960-radius, 540-radius, 960+radius, 540+radius), fill=color)
    font = ImageFont.truetype('DejaVuSans.ttf', 76)
    draw.text((960, 400), 'HEART & MIND', font=font, fill='white', anchor='mm')
    draw.text((960, 520), 'ORIGINAL HINDI MUSIC', font=ImageFont.truetype('DejaVuSans.ttf', 36),
              fill='#f9b4cc', anchor='mm')
    image.save(root/'cover.png')
    image.resize((1280, 720)).save(root/'thumbnail.jpg', quality=90)
    subprocess.run(['ffmpeg', '-y', '-loop', '1', '-i', str(root/'cover.png'), '-i', str(root/'song.wav'),
        '-filter_complex', '[1:a]asplit=2[a][v];[v]showwaves=s=1600x180:mode=line:colors=0xf9b4cc:rate=25,format=rgba[w];[0:v][w]overlay=160:750:shortest=1,format=yuv420p[out]',
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
                'tags': ['Heart and Mind', 'Hindi song', 'original Hindi music', 'AI music']},
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


def run(run_id):
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
        print('Already published: ' + state['video_id'])
        return
    if not state.get('song'):
        day = dt.datetime.now(ZoneInfo('Asia/Dhaka')).date().isoformat()
        song = (validate_song(json.loads((root/'song.json').read_text()))
                if (root/'song.json').exists() else make_song(day, [h['title'] for h in history[-30:]]))
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
            render(root)
        validate_duration(duration(root/'video.mp4'))
        for name in ('song.json', 'video.mp4', 'thumbnail.jpg'):
            store.upload(root/name, f'runs/{run_id}/{name}')
    elif not (root/'thumbnail.jpg').exists():
        store.download(store.find(f'runs/{run_id}/thumbnail.jpg'), root/'thumbnail.jpg')
    publish(client, root, song, state, save)
    if not any(h['run'] == run_id for h in history):
        history.append({'run': run_id, 'title': song['title'], 'hash': state['hash'], 'video_id': state['video_id']})
        store.save('history.json', history)
    print(json.dumps({'phase': state['phase'], 'video_id': state['video_id']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        run(args.run_id)
    except Exception as error:
        # Avoid leaking OAuth/API credentials through raw exception response bodies.
        print('Pipeline failed: ' + type(error).__name__ + '. Inspect checkpoint and configuration.')
        raise SystemExit(1)
