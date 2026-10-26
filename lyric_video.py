"""Audio-timed lyric storyboards, fresh five-second scenes, and continuous-song rendering."""
import argparse
import difflib
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

INTERVAL = 5
SHARDS = 16
ASR_REPO = 'Systran/faster-whisper-small'
ASR_REVISION = '536b0662742c02347bc0e980a01041f333bce120'


def digest_file(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def save_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


def lyric_words(text):
    text = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', text)
    return re.findall(r'[\u0980-\u09ff]+', text)


def align_words(lyrics, words, seconds):
    """Match recognized vocal words to supplied lyrics; never invent singing timestamps."""
    original = lyric_words(lyrics)
    heard, timed = [], []
    previous_start = -1
    for word in words:
        start, end = float(word['start']), float(word['end'])
        if not math.isfinite(start+end) or not 0 <= start < end <= seconds + .25 or start < previous_start:
            raise RuntimeError('Invalid vocal timing')
        previous_start = start
        for token in lyric_words(word['word']):
            heard.append(token)
            timed.append(dict(start=start, end=min(end, seconds)))
    matcher = difflib.SequenceMatcher(None, original, heard, autojunk=False)
    matched = []
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            matched.append(dict(timed[block.b+offset], index=block.a+offset))
    if (len(matched) < 25 or len(matched)/max(len(heard), 1) < .3 or
            len(matched)/max(len(original), 1) < .25 or
            matched[-1]['end']-matched[0]['start'] < seconds*.4):
        raise RuntimeError('Sung Bangla lyrics could not be reliably timed; preserve song for review')
    return original, matched


def timed_shots(lyrics, words, seconds):
    original, matched = align_words(lyrics, words, seconds)
    shots = []
    for index in range(math.ceil(seconds/INTERVAL)):
        start, end = index*INTERVAL, min((index+1)*INTERVAL, seconds)
        active = [word for word in matched if word['start'] < end and word['end'] > start]
        anchor = (active[0] if active else min(matched, key=lambda word: abs(word['start']-(start+end)/2)))['index']
        context = ' '.join(original[max(0, anchor-5):min(len(original), anchor+15)])
        shots.append(dict(index=index, start=start, duration=end-start, lyrics=context,
                          instrumental=not bool(active)))
    return shots


def transcribe(root, song, audio_hash, seconds):
    path = root/'alignment.json'
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get('audio_hash') == audio_hash and cached.get('revision') == ASR_REVISION:
            return cached['words']
    from huggingface_hub import snapshot_download
    from faster_whisper import WhisperModel
    model_path = snapshot_download(ASR_REPO, revision=ASR_REVISION, token=False,
                                   allow_patterns=['*.json', '*.bin', '*.txt'])
    model = WhisperModel(model_path, device='cpu', compute_type='int8', cpu_threads=4, num_workers=1)
    segments, _ = model.transcribe(str(root/'song.wav'), language='bn', word_timestamps=True,
        beam_size=5, vad_filter=False, condition_on_previous_text=False)
    words = [dict(start=word.start, end=word.end, word=word.word)
             for segment in segments for word in (segment.words or [])]
    # Reject weak alignment before saving it as a reusable checkpoint.
    align_words(song['lyrics'], words, seconds)
    save_json(path, dict(audio_hash=audio_hash, revision=ASR_REVISION, words=words))
    del model
    gc.collect()
    return words


def validate_plan(plan, seconds=None):
    shots = plan.get('shots', [])
    seconds = float(plan.get('duration', 0) if seconds is None else seconds)
    if not 180 <= seconds <= 360 or len(shots) != math.ceil(seconds/INTERVAL):
        raise RuntimeError('Incomplete five-second storyboard')
    for index, shot in enumerate(shots):
        expected = min(INTERVAL, seconds-index*INTERVAL)
        if (shot.get('index') != index or shot.get('start') != index*INTERVAL or
                abs(shot.get('duration', 0)-expected) > .001 or
                not isinstance(shot.get('prompt'), str) or not 30 <= len(shot['prompt']) <= 320):
            raise RuntimeError('Invalid scene timing or prompt')
    return shots


def prepare_storyboard(root, song):
    from pipeline import duration, validate_duration
    root = Path(root)
    seconds = duration(root/'song.wav')
    validate_duration(seconds)
    audio_hash = digest_file(root/'song.wav')
    context = {key: song.get(key) for key in ('lyrics', 'prompt', 'visual_mood', 'thumbnail_prompt')}
    identity = hashlib.sha256((audio_hash + ASR_REVISION + json.dumps(context, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
    path = root/'storyboard.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    if previous.get('identity') == identity and previous.get('complete'):
        validate_plan(previous, seconds)
        return previous
    words = transcribe(root, song, audio_hash, seconds)
    shots = timed_shots(song['lyrics'], words, seconds)
    if previous.get('identity') == identity:
        for shot, old in zip(shots, previous.get('shots', [])):
            if old.get('index') == shot['index'] and old.get('lyrics') == shot['lyrics'] and old.get('prompt'):
                shot['prompt'] = old['prompt']
    plan = dict(identity=identity, audio_hash=audio_hash, duration=seconds, interval=INTERVAL,
                complete=False, shots=shots)
    save_json(path, plan)
    from lyrics_cpu import MODEL_ID, request_story
    for offset in range(0, len(shots), 6):
        batch = shots[offset:offset+6]
        if all(shot.get('prompt') for shot in batch):
            continue
        ids = [shot['index'] for shot in batch]
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['scenes'], 'properties': {
            'scenes': {'type': 'array', 'minItems': len(batch), 'maxItems': len(batch), 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['index', 'prompt'], 'properties': {
                    'index': {'type': 'integer', 'enum': ids},
                    'prompt': {'type': 'string', 'minLength': 30, 'maxLength': 320}}}}}}
        prompt = ('Storyboard this Bangla album song. For each timed lyric excerpt, write a DIFFERENT '
            '20-35 word English photographic scene that literally reflects its action, objects and emotion. '
            'For metaphorical lines use a clear visual symbol. For instrumental gaps use a related establishing shot. '
            'Consistent fictional Bangladeshi adult couple age 28: man with short black hair in navy shirt, '
            'woman with long black hair in a teal salwar kameez. Show them only where the lyrics fit; vary '
            'close-ups, river/city/rain/nature locations, props and camera angle. Fully clothed, cinematic light, '
            'no celebrities, text, logos or tool names. Do not repeat the same generic sunset scene. '
            'Return every index exactly once in input order. Song context: ' + song['prompt'] + '\n' +
            json.dumps([{key: shot[key] for key in ('index', 'lyrics', 'instrumental')} for shot in batch], ensure_ascii=False))
        result = request_story('chat/completions', dict(model=MODEL_ID,
            messages=[{'role': 'user', 'content': prompt}], max_completion_tokens=2500,
            response_format={'json_schema': {'schema': schema}}))
        scenes = json.loads(result['choices'][0]['message']['content'])['scenes']
        if [scene['index'] for scene in scenes] != ids:
            raise RuntimeError('Storyboard indices do not match the vocal timeline')
        for shot, scene in zip(batch, scenes):
            shot['prompt'] = scene['prompt']
        save_json(path, plan)
        print(json.dumps({'phase': 'lyric storyboard', 'completed': min(offset+6, len(shots)), 'total': len(shots)}), flush=True)
    validate_plan(plan, seconds)
    plan['complete'] = True
    save_json(path, plan)
    return plan


def generate_shard(root, song, shard=0, shards=SHARDS):
    from image_cpu import generate, MODEL, REVISION
    root = Path(root)
    plan = json.loads((root/'storyboard.json').read_text())
    shots = validate_plan(plan)
    if not plan.get('complete') or not 0 <= shard < shards <= 16:
        raise RuntimeError('Completed lyric storyboard and valid shard required')
    tasks = [(f"scene-{shot['index']:03}.png", shot['prompt'], str(shot['index']))
             for shot in shots if shot['index'] % shards == shard]
    if shard == 0:
        tasks.append(('thumbnail-source.png', song['thumbnail_prompt'] + ', expressive adults on right, dark empty left, no text', 'thumbnail'))
    manifest_path = root/f'image-shard-{shard}.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    # A resumed production may have used a different shard count. Remove only
    # restored files listed in this shard's own manifest and now owned elsewhere.
    assigned = {name for name, _, _ in tasks}
    for name in old:
        if re.fullmatch(r'scene-\d{3}\.png', name) and name not in assigned:
            (root/name).unlink(missing_ok=True)
    saved = {}
    for name, prompt, purpose in tasks:
        seed = int(hashlib.sha256((plan['identity']+purpose).encode()).hexdigest()[:8], 16)
        spec = dict(identity=plan['identity'], prompt=prompt, seed=seed, model=MODEL, revision=REVISION,
            width=int(os.getenv('CPU_IMAGE_WIDTH', '1024')), height=int(os.getenv('CPU_IMAGE_HEIGHT', '576')),
            steps=int(os.getenv('CPU_IMAGE_STEPS', '20')))
        target = root/name
        valid = False
        if target.exists() and old.get(name) == spec:
            try:
                from PIL import Image
                with Image.open(target) as image:
                    image.verify()
                valid = True
            except (OSError, ValueError):
                pass
        if not valid:
            temporary = target.with_suffix('.tmp.png')
            generate(prompt, temporary, seed=seed)
            temporary.replace(target)
        saved[name] = spec
        save_json(manifest_path, saved)
    return saved


def render_video(root):
    from pipeline import duration, validate_duration
    from artwork import create_artwork
    from PIL import Image
    root = Path(root)
    song = json.loads((root/'song.json').read_text())
    plan = json.loads((root/'storyboard.json').read_text())
    seconds = duration(root/'song.wav')
    validate_duration(seconds)
    shots = validate_plan(plan, seconds)
    if not plan.get('complete') or plan.get('audio_hash') != digest_file(root/'song.wav'):
        raise RuntimeError('Storyboard does not match the completed audio')
    lines = ['ffconcat version 1.0']
    for shot in shots:
        path = root/f"scene-{shot['index']:03}.png"
        with Image.open(path) as image:
            image.verify()
        # Internal filenames are fixed; quote paths for the ffconcat parser.
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines += [f"file '{escaped}'", f"duration {shot['duration']:.6f}"]
    lines.append(lines[-2])  # Retain the final still through its full duration.
    concat = root/'scenes.ffconcat'
    concat.write_text('\n'.join(lines)+'\n')
    create_artwork(root, song)
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat), '-i', str(root/'song.wav'),
        '-filter_complex', '[0:v]fps=25:start_time=0:round=down,scale=1920:1080,setsar=1[bg];[1:a]asplit=2[a][v];'
        '[v]showwaves=s=1600x90:mode=line:colors=0xf9b4cc:rate=25,format=rgba[w];'
        '[bg][w]overlay=160:980:shortest=1,format=yuv420p[out]',
        '-map', '[out]', '-map', '[a]', '-r', '25', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-c:a', 'aac', '-b:a', '320k', '-t', str(seconds), '-movflags', '+faststart', str(root/'video.mp4')],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    measured = duration(root/'video.mp4')
    validate_duration(measured)
    if abs(measured-seconds) > .1:
        raise RuntimeError('Rendered timeline differs from full song duration')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--stage', choices=['storyboard', 'images'], required=True)
    parser.add_argument('--shard', type=int, default=0)
    args = parser.parse_args()
    song = json.loads((args.root/'song.json').read_text())
    if args.stage == 'storyboard':
        prepare_storyboard(args.root, song)
    else:
        generate_shard(args.root, song, args.shard)
