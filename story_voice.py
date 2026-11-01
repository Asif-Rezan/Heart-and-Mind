"""Hindi CPU narration with native pacing and measured scene timings."""
import hashlib
import json
import math
from pathlib import Path
from story_writer import VOICES, save_json, validate_story

SAMPLE_RATE = 24000
from story_format import duration_bounds, is_short

VOICE_VERSION = 'hindi-native-voice-v4-pause-profile'
from story_voice_model import voice_profile, load_pipeline


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


def voice_identity(story, speed, profile=None):
    return hashlib.sha256(json.dumps(dict(script=story['scenes'], voices=VOICES,
        speed=speed, version=VOICE_VERSION, format=story.get('format'),
        profile=profile or voice_profile(legacy=not is_short(story))), sort_keys=True).encode()).hexdigest()


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


def prepare_speech(samples):
    """Remove excessive model edge silence while retaining breath/consonant tails."""
    import numpy as np
    samples=np.asarray(samples,dtype=np.float32)
    if samples.ndim!=1 or not len(samples) or not np.isfinite(samples).all():
        raise RuntimeError('Invalid narration waveform')
    active=np.flatnonzero(np.abs(samples)>.0005)
    if not len(active):raise RuntimeError('Narration is silent')
    start=max(0,int(active[0]) - round(.1*SAMPLE_RATE))
    end=min(len(samples),int(active[-1])+1+round(.16*SAMPLE_RATE))
    result=samples[start:end].copy()
    fade=min(round(.005*SAMPLE_RATE),len(result)//2)
    if fade:
        result[:fade]*=np.linspace(0,1,fade)
        result[-fade:]*=np.linspace(1,0,fade)
    return result


def scene_pause(story,index):
    if index==len(story['scenes'])-1:return 0
    if (index+1)%8==0:return .28
    return .12 if story['scenes'][index]['text'].rstrip().endswith(('?','？','!')) else .08


def next_native_speed(story,speed,seconds):
    minimum,maximum=duration_bounds(story)
    if minimum<=seconds<=maximum:return speed
    target=(minimum+10 if seconds<minimum else maximum-10) if is_short(story) else 600
    lower,upper=(.90,1.08) if is_short(story) else (.80,1.15)
    return round(max(lower,min(upper,speed*seconds/target)),3)


def generate_voice(root, story):
    import numpy as np
    import soundfile as sf
    import torch
    validate_story(story)
    minimum, maximum = duration_bounds(story)
    root = Path(root)
    profile=voice_profile(legacy=not is_short(story))
    profile_path=root/'voice-profile.json'
    if profile_path.exists():
        saved_profile=json.loads(profile_path.read_text())
        if saved_profile!=profile:
            raise ValueError('Saved narration voice differs; use a new run ID to select another voice')
    else:
        save_json(profile_path,profile)
    timing_path = root/'timing.json'
    if timing_path.exists() and (root/'narration.wav').exists():
        timing = json.loads(timing_path.read_text())
        if timing.get('identity') == voice_identity(story, timing['speed'],profile):
            info = sf.info(root/'narration.wav')
            if abs(info.duration-timing['duration']) < .001 and minimum <= timing['duration'] <= maximum:
                return timing
    torch.set_num_threads(4)
    pipeline,narrator=load_pipeline(profile)
    speed=1.0 if is_short(story) else .95
    for attempt in range(3):
        identity = voice_identity(story, speed,profile)
        work = root/'voice'/identity
        work.mkdir(parents=True, exist_ok=True)
        scenes, parts, offset = [], [], 0
        for scene in story['scenes']:
            path = work/f"voice-{scene['index']:03d}.wav"
            if not path.exists():
                chunks = synthesize_chunks(pipeline,scene['text'],
                    narrator if is_short(story) else VOICES[scene['speaker']],speed)
                if not chunks or not all(np.isfinite(c).all() and len(c) > 0 for c in chunks):
                    raise RuntimeError('Kokoro returned invalid or empty Hindi speech')
                samples=prepare_speech(np.concatenate(chunks))
                pause=scene_pause(story,scene['index']) if is_short(story) else .18
                samples=np.concatenate([samples,np.zeros(round(pause*SAMPLE_RATE),dtype=np.float32)])
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
                model=profile['model'],profile=profile,voices={'narrator':profile['voice']} if is_short(story) else VOICES,sample_rate=SAMPLE_RATE)
            save_json(timing_path, timing)
            return timing
        # Re-synthesize at a modest adjusted native speaking rate. Never loop,
        # pad minutes of silence, truncate the story or time-stretch final speech.
        adjusted=next_native_speed(story,speed,seconds)
        if math.isclose(adjusted, speed):
            break
        speed = adjusted
    raise RuntimeError('Natural Hindi narration is outside the required duration; saved script retained for review')
