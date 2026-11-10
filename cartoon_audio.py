"""CPU Kokoro cast voices, measured timing, original instrumental bed and cues."""
import hashlib
import json
import math
from pathlib import Path
import time
import wave
import numpy as np
from cartoon_story import CAST, atomic, validate_manifest

REPO = 'hexgrad/Kokoro-82M'
REVISION = 'f3ff3571791e39611d31c381e3a41a3af07b4987'
VERSION = 'kokoro-cast-24000-v1'
RATE = 24000
FPS = 25


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_wave(path, audio):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp.wav')
    with wave.open(str(temp), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(RATE)
        out.writeframes((np.clip(audio, -.98, .98)*32767).astype('<i2').tobytes())
    temp.replace(path)


def read_wave(path):
    with wave.open(str(path)) as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, RATE):
            raise ValueError('Unexpected speech sample format')
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').astype(np.float32)/32768
    if not RATE*.5 <= len(audio) <= RATE*24 or not np.isfinite(audio).all() or np.sqrt(np.mean(audio**2)) < .002:
        raise ValueError('Speech is empty, silent or outside the bounded shot duration')
    return audio


def load_voice_engine():
    from huggingface_hub import snapshot_download
    from kokoro import KModel, KPipeline
    import torch
    torch.set_num_threads(3)
    for attempt in range(3):
        try:
            folder = Path(snapshot_download(REPO, revision=REVISION,
                allow_patterns=['config.json', 'kokoro-v1_0.pth']+['voices/'+v['voice']+'.pt' for v in CAST.values()],
                max_workers=2, token=False))
            break
        except (OSError, RuntimeError):
            if attempt == 2: raise
            print(json.dumps({'phase': 'retry Kokoro model download', 'attempt': attempt+1}), flush=True)
            time.sleep(5*(attempt+1))
    model = KModel(repo_id=REPO, config=str(folder/'config.json'), model=str(folder/'kokoro-v1_0.pth')).to('cpu').eval()
    pipeline = KPipeline(lang_code='a', repo_id=REPO, model=model, device='cpu')
    def speak(text, voice):
        chunks = [result.audio.detach().cpu().numpy() for result in pipeline(text, voice=str(folder/'voices'/(voice+'.pt')), speed=.95)]
        if not chunks:
            raise ValueError('Kokoro returned no spoken audio')
        return np.concatenate(chunks).astype(np.float32)
    return speak


def instrumental(samples, offset=0):
    """Original deterministic evolving chord score; never a looped speech/song file."""
    t = (np.arange(samples, dtype=np.float64)+offset)/RATE
    chords = np.array([[130.8128,164.8138,195.9977],[110,130.8128,164.8138],
                       [87.3071,110,130.8128],[97.9989,123.4708,146.8324]])
    index = (t//8).astype(int)%4
    bed = np.zeros(samples, dtype=np.float64)
    # Soft electric-piano-like harmonics, with a quiet changing upper melody.
    for note in range(3):
        freq = chords[index,note]
        phase = np.cumsum(2*np.pi*freq/RATE)
        bed += np.sin(phase)*.006*(.7+.3*np.sin(t*.4+note))
    melody = np.array([261.6256,329.6276,391.9954,329.6276,293.6648,261.6256,220,293.6648])
    phase = np.cumsum(2*np.pi*melody[(t//2).astype(int)%8]/RATE)
    bed += .004*np.sin(phase)*np.exp(-(t%2)*2)
    return bed.astype(np.float32)


def mix_scene(speech, scene, offset=0):
    frames = math.ceil((len(speech)/RATE+.8)*FPS-1e-9)
    samples = frames*(RATE//FPS)
    output = instrumental(samples, offset)
    onset = round(.25*RATE)
    # Voice remains dominant; the score is deliberately low beneath speech.
    gain = min(3., .13/max(.01, float(np.sqrt(np.mean(speech**2)))))
    output[onset:onset+len(speech)] *= .35
    output[onset:onset+len(speech)] += speech*gain
    if scene['sfx'] == 'discovery':
        count = min(round(.35*RATE), samples); t = np.arange(count)/RATE
        output[-count:] += (.025*np.sin(2*np.pi*880*t)*np.exp(-t*12)).astype(np.float32)
    elif scene['sfx'] == 'footsteps' and scene['action'] in ('approach_friend','follow_friend','approach_ball'):
        for second in (.08,.43):
            start = round(second*RATE); n = round(.06*RATE); t = np.arange(n)/RATE
            output[start:start+n] += (.025*np.sin(2*np.pi*100*t)*np.exp(-t*70)).astype(np.float32)
    fade = min(round(.03*RATE), samples//2)
    output[:fade] *= np.linspace(0,1,fade); output[-fade:] *= np.linspace(1,0,fade)
    peak = float(np.max(np.abs(output)))
    if peak > .95: output *= .95/peak
    return output, frames


def prepare_audio(root, engine=None):
    root = Path(root); song = validate_manifest(json.loads((root/'song.json').read_text()))
    folder = root/'speech'; folder.mkdir(exist_ok=True)
    speak = engine
    timeline = []; tracks = []; cursor_frames = 0
    for scene in song['scenes']:
        voice = CAST[scene['speaker']]['voice']; path = folder/f"shot-{scene['index']:03d}.wav"
        record = path.with_suffix('.json')
        identity = dict(version=VERSION, revision=REVISION, text=scene['text'], voice=voice, speed=.95)
        cached = False
        if path.exists() and record.exists():
            try:
                saved = json.loads(record.read_text())
                cached = saved['identity'] == identity and saved['sha256'] == digest(path)
                if cached: speech = read_wave(path)
            except (OSError, ValueError, KeyError, wave.Error): cached = False
        if not cached:
            if speak is None: speak = load_voice_engine()
            speech = np.asarray(speak(scene['text'], voice), dtype=np.float32)
            if speech.ndim != 1 or not np.isfinite(speech).all():
                raise ValueError('Kokoro returned invalid speech samples')
            # Validate a candidate before committing its checkpoint.
            candidate = folder/'candidate.wav'; write_wave(candidate, speech); speech = read_wave(candidate)
            candidate.replace(path); atomic(record, dict(identity=identity, sha256=digest(path)))
        audio, frames = mix_scene(speech, scene, cursor_frames*(RATE//FPS))
        scene.update(start=cursor_frames/FPS, end=(cursor_frames+frames)/FPS,
                     speech_start=cursor_frames/FPS+.25, speech_seconds=len(speech)/RATE)
        cursor_frames += frames; tracks.append(audio); timeline.append(scene)
        print(json.dumps({'phase':'cartoon speech ready','shot':scene['index'],'speaker':scene['speaker'],'frames':frames,'cached':cached}), flush=True)
    song.update(scenes=timeline, duration=cursor_frames/FPS, audio_engine=VERSION)
    validate_manifest(song, timed=True)
    write_wave(root/'song.wav', np.concatenate(tracks))
    atomic(root/'song.json', song)
    atomic(root/'audio-state.json', dict(version=VERSION, source_sha256=digest(root/'song.json'), sha256=digest(root/'song.wav'), duration=song['duration']))
    return song
