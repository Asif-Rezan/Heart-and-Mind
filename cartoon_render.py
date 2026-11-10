"""Voice-timed cutout acting and bounded two-shot transitions."""
import json
import math
import os
from pathlib import Path
import subprocess
from PIL import Image
from cartoon_story import VERSION, atomic, validate_manifest
from cartoon_audio import digest

RENDER_VERSION = 'voice-timed-family-cutouts-v1'
FPS = 25


def acting_plan(scene):
    from cartoon_actions import plan_scene
    cues = {'approach_friend': 'left friend walks toward waiting friend to greet and help',
        'follow_friend': 'friends walk to follow the leader along the path',
        'approach_ball': 'walk to fetch the ball', 'react': 'friends react', 'wait': 'friends wait'}
    plan = plan_scene(cues[scene['action']], scene['index'])
    plan.update(opening=False, prop='ball' if scene['action']=='approach_ball' else None,
                dance_variant='step', second_variant='wave', beat_seconds=.7)
    if scene['action'] in ('react','wait'):
        plan.update(action='sway', kind='conversation', intent=None, locomotion=None)
    return plan


def clip_identity(root, scene, width, height):
    from cartoon_actions import VERSION as movement
    source = Path(root)/f"scene-{scene['index']:03d}-source.png"
    return dict(version=RENDER_VERSION, movement=movement, source=digest(source), scene=scene, width=width,height=height)


def valid_clip(path, frames, width, height):
    result = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
    stream = next(s for s in result['streams'] if s['codec_type']=='video')
    if (stream['width'],stream['height'],int(stream['nb_frames'])) != (width,height,frames):
        raise ValueError('Cartoon clip does not match measured speech timing')


def render_shot(root, scene, width=1920, height=1080):
    from character_motion import prepare_layers, InvalidForegroundMask
    from cartoon_actions import actor_parts, compose_scene, apply_camera
    root = Path(root); folder = root/'cartoon-motion'; folder.mkdir(exist_ok=True)
    target = folder/f"clip-{scene['index']:03d}.mp4"; record = target.with_suffix('.json')
    identity = clip_identity(root,scene,width,height)
    frames = round((scene['end']-scene['start'])*FPS)
    if target.exists() and record.exists():
        try:
            saved = json.loads(record.read_text())
            if saved['identity'] == identity and saved['sha256'] == digest(target):
                valid_clip(target,frames,width,height); return target
        except (OSError,ValueError,KeyError,subprocess.CalledProcessError): pass
    source = root/f"scene-{scene['index']:03d}-source.png"
    layers = root/'characters'/source.stem; plan = acting_plan(scene); fallback = False
    try:
        prepare_layers(source,layers)
        background = Image.open(layers/'background.png').convert('RGBA')
        parts = actor_parts(Image.open(layers/'foreground.png').convert('RGBA'), split_touching=True)
        if not parts: raise InvalidForegroundMask('No separable cartoon actors')
    except InvalidForegroundMask:
        background = Image.open(source).convert('RGBA'); parts = []; fallback = True
    temp = target.with_suffix('.tmp.mp4')
    command = ['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{background.width}x{background.height}',
        '-r',str(FPS),'-i','pipe:0','-an','-vf',f'scale={width}:{height}:flags=lanczos',
        '-c:v','libx264','-threads','3','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(temp)]
    proc = subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for frame in range(frames):
            # One complete action over this spoken shot; no repeated five-second loop.
            t = 4.96*frame/max(1,frames-1)
            image = (apply_camera(background,(0,0,*background.size),plan,t).convert('RGB') if fallback
                     else compose_scene(background,parts,plan,t))
            proc.stdin.write(image.tobytes())
        proc.stdin.close()
        error = proc.stderr.read(); code = proc.wait(timeout=90)
        if code: raise RuntimeError('Cartoon encoder failed: '+error.decode(errors='replace')[-1000:])
        valid_clip(temp,frames,width,height); temp.replace(target)
        atomic(record,dict(identity=identity,sha256=digest(target),camera_only_fallback=fallback))
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        if not proc.stdin.closed:
            try: proc.stdin.close()
            except BrokenPipeError: pass
        proc.stderr.close(); temp.unlink(missing_ok=True)
    return target


def identity(root):
    root = Path(root); song = validate_manifest(json.loads((root/'song.json').read_text()),timed=True)
    sources = [root/'song.json',root/'song.wav',root/'thumbnail-source.png']
    sources += [root/'cartoon-motion'/f"clip-{s['index']:03d}.mp4" for s in song['scenes']]
    return dict(version=RENDER_VERSION, sources={str(p.relative_to(root)):digest(p) for p in sources})


def is_current(root):
    root = Path(root)
    try:
        saved = json.loads((root/'render-state.json').read_text())
        return (saved['identity'] == identity(root) and saved['video_sha256'] == digest(root/'video.mp4'))
    except (OSError,ValueError,KeyError): return False


def assemble(root, width=1920, height=1080):
    from thumbnail_export import export_thumbnail
    root = Path(root); song = validate_manifest(json.loads((root/'song.json').read_text()),timed=True)
    signature = identity(root)
    clips = []; folder = root/'cartoon-motion'
    for index,scene in enumerate(song['scenes']):
        clip = folder/f'clip-{index:03d}.mp4'
        frames = round((scene['end']-scene['start'])*FPS); valid_clip(clip,frames,width,height)
        if index:
            previous = song['scenes'][index-1]; length = previous['end']-previous['start']
            target = folder/f'blend-{index:03d}.mp4'
            graph = (f'[0:v]trim=start={length-1/FPS:.6f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=0.16,fps=25,settb=AVTB[a];'
                '[1:v]setpts=PTS-STARTPTS,fps=25,settb=AVTB[b];[a][b]xfade=transition=fade:duration=0.16:offset=0,format=yuv420p[v]')
            subprocess.run(['ffmpeg','-y','-v','error','-i',str(folder/f'clip-{index-1:03d}.mp4'),'-i',str(clip),
                '-filter_complex_threads','1','-filter_complex',graph,'-map','[v]','-frames:v',str(frames),
                '-an','-c:v','libx264','-threads','3','-preset','fast','-crf','20',str(target)],check=True,timeout=300)
            valid_clip(target,frames,width,height); clip = target
        clips.append(clip)
    listing = folder/'clips.txt'; listing.write_text(''.join("file '"+p.name+"'\n" for p in clips))
    temp = root/'video.tmp.mp4'
    try:
        subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-i',str(root/'song.wav'),
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(song['duration']),'-movflags','+faststart',str(temp)],check=True,timeout=600)
        from pipeline import duration
        if abs(duration(temp)-song['duration']) > .1: raise ValueError('Cartoon final audio/video timing mismatch')
        export_thumbnail(root/'thumbnail-source.png',root/'thumbnail.jpg')
        temp.replace(root/'video.mp4'); atomic(root/'render-state.json',dict(identity=signature, video_sha256=digest(root/'video.mp4')))
    finally: temp.unlink(missing_ok=True)
