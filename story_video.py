"""Reference-style SSD-1B illustrations and measured scene camera motion."""
import hashlib
import json
import math
import os
from pathlib import Path
from PIL import Image, ImageOps
from story_media import digest, run_ffmpeg
from story_writer import scene_prompt, save_json

VERSION = 'hindi-story-motion-v1'
FPS = 25


def generate_images(root, story):
    from story_image_cpu import generate, MODEL, REVISION
    root = Path(root)
    shard, count = int(os.getenv('IMAGE_SHARD','0')), int(os.getenv('IMAGE_SHARDS','1'))
    if not 0 <= shard < count:
        raise ValueError('Invalid story image shard')
    manifest = root/f'image-manifest-{shard:02d}.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    complete = {}
    for i, scene in enumerate(story['scenes']):
        if i % count != shard:
            continue
        plan = dict(prompt=scene_prompt(story, scene), model=MODEL, revision=REVISION,
                    width=1024, height=576, steps=20)
        plan['seed'] = int(hashlib.sha256((story['run_id']+str(i)).encode()).hexdigest()[:8],16)
        target = root/f'scene-{i:03d}-source.png'
        valid = False
        if previous.get(str(i)) == plan and target.exists():
            try:
                with Image.open(target) as image:
                    image.verify()
                valid = True
            except (OSError, ValueError):
                pass
        if not valid:
            temp = target.with_suffix('.tmp.png')
            generate(plan['prompt'], temp, seed=plan['seed'], width=1024, height=576, steps=20)
            with Image.open(temp) as image:
                image.verify()
            temp.replace(target)
        complete[str(i)] = plan
        save_json(manifest, complete)


def validate_timing(story, timing):
    if not 480 <= timing['duration'] <= 720 or len(timing['scenes']) != len(story['scenes']):
        raise ValueError('Incomplete narration timeline or duration outside 8-12 minutes')
    end = 0
    for i, scene in enumerate(timing['scenes']):
        if scene['index'] != i or abs(scene['start']-end) > .001 or scene['end'] <= scene['start']:
            raise ValueError('Non-contiguous narration timeline')
        end = scene['end']
    if abs(end-timing['duration']) > .001:
        raise ValueError('Timeline does not match narration duration')


def render_identity(root, story):
    root = Path(root)
    files = [root/'story.json',root/'timing.json',root/'song.wav']
    files += [root/f"scene-{s['index']:03d}-source.png" for s in story['scenes']]
    return dict(version=VERSION, sources={p.name:digest(p) for p in files})


def render(root, story, timing, width=1920, height=1080):
    from pipeline import duration
    root = Path(root)
    validate_timing(story, timing)
    if abs(duration(root/'song.wav')-timing['duration']) > .05:
        raise ValueError('Mixed audio does not match narration timeline')
    identity = render_identity(root, story)
    state_path = root/'render-state.json'
    if (root/'video.mp4').exists() and state_path.exists() and json.loads(state_path.read_text()) == identity:
        return
    work = root/'story-motion'
    work.mkdir(exist_ok=True)
    listing = work/'clips.txt'
    clips = []
    for scene in timing['scenes']:
        i = scene['index']
        # Round cumulative boundaries, avoiding 48 individual rounding errors.
        frames = round(scene['end']*FPS)-round(scene['start']*FPS)
        source = root/f'scene-{i:03d}-source.png'
        with Image.open(source) as image:
            image.verify()
        clip = work/f'clip-{i:03d}.mp4'
        zoom = f'1.04+0.045*on/{max(1, frames-1)}'
        travel = f'(iw-iw/zoom)*on/{max(1, frames-1)}' if i%2 else f'(iw-iw/zoom)*(1-on/{max(1, frames-1)})'
        vf = (f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2},"
              f"zoompan=z='{zoom}':x='{travel}':y='(ih-ih/zoom)/2':d={frames}:s={width}x{height}:fps={FPS},"
              'setsar=1,format=yuv420p')
        run_ffmpeg(['-i',str(source),'-vf',vf,'-an','-frames:v',str(frames),'-r',str(FPS),
                    '-c:v','libx264','-threads','4','-preset','fast','-crf','20',str(clip)])
        clips.append(clip)
        print(json.dumps({'phase':'render story','scene':i+1,'total':len(timing['scenes'])}), flush=True)
    listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    with Image.open(root/'scene-000-source.png') as image:
        ImageOps.fit(image.convert('RGB'),(1280,720)).save(root/'thumbnail.jpg',quality=92)
    temp = root/'video.tmp.mp4'
    run_ffmpeg(['-f','concat','-safe','1','-i',str(listing),'-i',str(root/'song.wav'),
        '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
        '-t',str(timing['duration']),'-movflags','+faststart',str(temp)])
    measured = duration(temp)
    if not 480 <= measured <= 720 or abs(measured-timing['duration']) > .1:
        raise ValueError('Rendered story duration failed verification')
    temp.replace(root/'video.mp4')
    save_json(state_path, identity)
