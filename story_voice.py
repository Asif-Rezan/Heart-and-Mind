"""Hindi Kokoro CPU speech, scene timing derived from actual audio samples."""
import hashlib
import json
import math
from pathlib import Path
from story_writer import VOICES, save_json, validate_story

SAMPLE_RATE = 24000
from story_format import NARRATOR, TARGET_SECONDS, duration_bounds, is_short

VOICE_VERSION = 'kokoro-0.9.4-hindi-v3-single-voice'


def speech_chunks(text,max_words=30,max_characters=200):
    """Break only at word boundaries; preserve every spoken word/punctuation."""
    words=text.split()
    chunks=[]
    start=0
    while start<len(words):
        end=start
        chars=0
        while end<len(words) and end-start<max_words:
            extra=len(words[end])+(1 if end>start else 0)
            if end>start and chars+extra>max_characters:
                break
            chars+=extra
            end+=1
        if end<len(words):
            stops=[i+1 for i in range(start,end) if words[i].endswith(('।','.','!','?'))]
            if stops and stops[-1]>start+(end-start)//2:
                end=stops[-1]
        chunks.append(' '.join(words[start:end]))
        start=end
    return chunks


def voice_identity(story, speed):
    return hashlib.sha256(json.dumps(dict(script=story['scenes'], voices=VOICES,
        speed=speed, version=VOICE_VERSION, format=story.get('format')), sort_keys=True).encode()).hexdigest()


def synthesize_chunks(pipeline, text, voice, speed):
    """Feed bounded chunks once and reject echoed or missing spoken text."""
    from story_writer import normalized
    chunks=[]
    for source in speech_chunks(text):
        spoken=[]
        for graphemes, _, audio in pipeline(source,voice=voice,speed=speed,split_pattern=None):
            spoken.append(graphemes)
            chunks.append(audio.detach().cpu().numpy())
        if normalized(' '.join(spoken)) != normalized(source):
            raise RuntimeError('Narration text coverage mismatch; possible duplicated or missing speech')
    return chunks


def generate_voice(root, story):
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KPipeline
    validate_story(story)
    minimum, maximum = duration_bounds(story)
    root = Path(root)
    timing_path = root/'timing.json'
    if timing_path.exists() and (root/'narration.wav').exists():
        timing = json.loads(timing_path.read_text())
        if timing.get('identity') == voice_identity(story, timing['speed']):
            info = sf.info(root/'narration.wav')
            if abs(info.duration-timing['duration']) < .001 and minimum <= timing['duration'] <= maximum:
                return timing
    torch.set_num_threads(4)
    pipeline = KPipeline(lang_code='h', device='cpu', repo_id='hexgrad/Kokoro-82M')
    speed = .95
    for attempt in range(3):
        identity = voice_identity(story, speed)
        work = root/'voice'/identity
        work.mkdir(parents=True, exist_ok=True)
        scenes, parts, offset = [], [], 0
        for scene in story['scenes']:
            path = work/f"voice-{scene['index']:03d}.wav"
            if not path.exists():
                chunks = synthesize_chunks(pipeline,scene['text'],
                    NARRATOR if is_short(story) else VOICES[scene['speaker']],speed)
                if not chunks or not all(np.isfinite(c).all() and len(c) > 0 for c in chunks):
                    raise RuntimeError('Kokoro returned invalid or empty Hindi speech')
                samples = np.concatenate(chunks)
                # Natural short scene pause, included in the measured timeline.
                samples = np.concatenate([samples, np.zeros(round(.18*SAMPLE_RATE), dtype=np.float32)])
                temp = path.with_suffix('.tmp.wav')
                sf.write(temp, samples, SAMPLE_RATE, subtype='PCM_16')
                temp.replace(path)
            samples, rate = sf.read(path, dtype='float32')
            if rate != SAMPLE_RATE or samples.ndim != 1 or not len(samples) or not np.isfinite(samples).all():
                raise RuntimeError('Invalid saved speech segment')
            end = offset+len(samples)
            scenes.append(dict(index=scene['index'], start=offset/SAMPLE_RATE, end=end/SAMPLE_RATE))
            parts.append(samples)
            offset = end
            print(json.dumps({'phase':'Hindi narration','scene':scene['index']+1,'total':len(story['scenes'])}), flush=True)
        seconds = offset/SAMPLE_RATE
        if minimum <= seconds <= maximum:
            temp = root/'narration.tmp.wav'
            sf.write(temp, np.concatenate(parts), SAMPLE_RATE, subtype='PCM_16')
            temp.replace(root/'narration.wav')
            timing = dict(identity=identity, speed=speed, duration=seconds, scenes=scenes,
                model='hexgrad/Kokoro-82M', voices={'narrator':NARRATOR} if is_short(story) else VOICES, sample_rate=SAMPLE_RATE)
            save_json(timing_path, timing)
            return timing
        # Re-synthesize at a modest adjusted native speaking rate. Never loop,
        # pad minutes of silence, truncate the story or time-stretch final speech.
        adjusted = round(max(.80, min(1.15, speed*seconds/(TARGET_SECONDS if is_short(story) else 600))), 3)
        if math.isclose(adjusted, speed):
            break
        speed = adjusted
    raise RuntimeError('Natural Hindi narration is outside the required duration; saved script retained for review')
