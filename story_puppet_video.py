"""Python 2D puppet animation on the measured narration timeline."""
import json
import math
import os
from pathlib import Path
from PIL import Image, ImageOps
from story_media import digest, run_ffmpeg
from story_writer import save_json

from story_format import IMAGE_SECONDS, duration_bounds, is_short

VERSION = 'hindi-story-puppet-v1'
FPS = 25


def visual_timeline(story, timing):
    validate_timing(story,timing)
    if not is_short(story):
        return timing['scenes']
    result=[]
    for i in range(math.ceil(timing['duration']/IMAGE_SECONDS)):
        start=i*IMAGE_SECONDS
        end=min((i+1)*IMAGE_SECONDS,timing['duration'])
        # Select the spoken beat occupying most of this exact display interval.
        spoken=max(timing['scenes'],key=lambda s:max(0,min(end,s['end'])-max(start,s['start'])))
        result.append(dict(index=i,start=start,end=end,story_scene=spoken['index']))
    return result


def thumbnail_slot(story, timing):
    slots=visual_timeline(story,timing)
    if not is_short(story):
        return 0
    desired=story['thumbnail_scene']
    return min(slots,key=lambda slot:abs(slot['story_scene']-desired))['index']


def generate_images(root, story, render_ready=False):
    """Compatibility stage name: prepare Python puppet plans and poster frames."""
    from story_puppet import scene_plan, Stage
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    shard,count=int(os.getenv('IMAGE_SHARD','0')),int(os.getenv('IMAGE_SHARDS','1'))
    if not 0<=shard<count:
        raise ValueError('Invalid story image shard')
    timing=json.loads((root/'timing.json').read_text()) if is_short(story) or render_ready else None
    slots=visual_timeline(story,timing) if timing else story['scenes']
    manifest=root/f'image-manifest-{shard:02d}.json'
    previous=json.loads(manifest.read_text()) if manifest.exists() else {}
    complete={}
    for slot in slots:
        i=slot['index']
        if i%count!=shard:
            continue
        plan=scene_plan(story,slot)
        plan['renderer_sha256']=digest(Path(__file__).with_name('story_puppet.py'))
        target=root/f'scene-{i:03d}-source.png'
        plan_path=root/f'scene-{i:03d}-puppet.json'
        valid=False
        if previous.get(str(i))==plan and target.exists() and plan_path.exists():
            try:
                valid=json.loads(plan_path.read_text())==plan
                with Image.open(target) as image:image.verify()
            except (OSError,ValueError):pass
        if not valid:
            temp=target.with_suffix('.tmp.png')
            Stage(plan).frame(.7,speaking=False).save(temp)
            temp.replace(target)
            save_json(plan_path,plan)
        complete[str(i)]=plan
        save_json(manifest,complete)
        if render_ready:
            render_clips(root,story,timing,shard=shard,shards=count,only_indices={i})
    if is_short(story) and shard==0:
        desired=story['thumbnail_scene']
        plan=scene_plan(story,dict(index=desired,story_scene=desired))
        plan['renderer_sha256']=digest(Path(__file__).with_name('story_puppet.py'))
        Stage(plan).frame(.7,speaking=False).save(root/'thumbnail-source.png')
        save_json(root/'thumbnail-manifest.json',plan)


def validate_timing(story, timing):
    minimum,maximum=duration_bounds(story)
    if not minimum <= timing['duration'] <= maximum or len(timing['scenes']) != len(story['scenes']):
        raise ValueError('Incomplete narration timeline or duration outside the story format')
    end = 0
    for i, scene in enumerate(timing['scenes']):
        if scene['index'] != i or abs(scene['start']-end) > .001 or scene['end'] <= scene['start']:
            raise ValueError('Non-contiguous narration timeline')
        end = scene['end']
    if abs(end-timing['duration']) > .001:
        raise ValueError('Timeline does not match narration duration')


def render_identity(root, story, width=1920, height=1080):
    root = Path(root)
    files = [root/'story.json',root/'timing.json',root/'song.wav']
    timing=json.loads((root/'timing.json').read_text())
    files += [root/f"scene-{s['index']:03d}-source.png" for s in visual_timeline(story,timing)]
    files += [root/f"scene-{s['index']:03d}-puppet.json" for s in visual_timeline(story,timing)]
    files += [Path(__file__).with_name('story_puppet.py')]
    if is_short(story):
        files += [root/'thumbnail-source.png']
    return dict(version=VERSION,width=width,height=height,fps=FPS,sources={p.name:digest(p) for p in files})


def clip_identity(root, scene, width, height):
    return dict(version=VERSION,index=scene['index'],start=scene['start'],end=scene['end'],
        width=width,height=height,fps=FPS,source=digest(Path(root)/f"scene-{scene['index']:03d}-source.png"),
        plan=digest(Path(root)/f"scene-{scene['index']:03d}-puppet.json"),
        renderer=digest(Path(__file__).with_name('story_puppet.py')))


def clip_is_current(root, scene, width=1920, height=1080, story=None):
    work=Path(root)/'story-motion'
    target=work/f"clip-{scene['index']:03d}.mp4"
    manifest=target.with_suffix('.json')
    if not target.is_file() or not manifest.is_file():
        return False
    try:
        saved=json.loads(manifest.read_text())
        if story is not None:
            from story_puppet import scene_plan
            expected=scene_plan(story,scene)
            expected['renderer_sha256']=digest(Path(__file__).with_name('story_puppet.py'))
            if json.loads((Path(root)/f"scene-{scene['index']:03d}-puppet.json").read_text())!=expected:
                return False
        return saved['identity']==clip_identity(root,scene,width,height) and saved['sha256']==digest(target)
    except (ValueError,KeyError,OSError):
        return False


def render_clips(root,story,timing,width=1920,height=1080,shard=0,shards=1,only_indices=None):
    from pipeline import duration
    validate_timing(story,timing)
    if not 0<=shard<shards:
        raise ValueError('Invalid render shard')
    root=Path(root)
    work=root/'story-motion'
    work.mkdir(exist_ok=True)
    slots=visual_timeline(story,timing)
    for scene in slots:
        i=scene['index']
        if (only_indices is not None and i not in only_indices) or i%shards!=shard or clip_is_current(root,scene,width,height,story=story):
            continue
        frames=round(scene['end']*FPS)-round(scene['start']*FPS)
        # A final sub-frame tail still needs a visible frame; audio is never cut.
        frames=max(1,frames)
        source=root/f'scene-{i:03d}-source.png'
        with Image.open(source) as image:
            image.verify()
        clip=work/f'clip-{i:03d}.mp4'
        temp=clip.with_suffix('.tmp.mp4')
        from story_puppet import encode, scene_plan
        plan=json.loads((root/f'scene-{i:03d}-puppet.json').read_text())
        expected=scene_plan(story,scene)
        expected['renderer_sha256']=digest(Path(__file__).with_name('story_puppet.py'))
        if plan!=expected:
            raise ValueError('Stale puppet plan; rerun the images preparation stage')
        encode(plan,temp,frames,FPS,width,height)
        if abs(duration(temp)-frames/FPS)>.05:
            raise ValueError('Rendered scene duration failed verification')
        temp.replace(clip)
        save_json(clip.with_suffix('.json'),dict(identity=clip_identity(root,scene,width,height),sha256=digest(clip)))
        print(json.dumps({'phase':'render story scene','scene':i+1,'total':len(slots),
                         'shard':shard,'shards':shards}),flush=True)


def render(root,story,timing,width=1920,height=1080,prepared_clips=False):
    from pipeline import duration
    root=Path(root)
    validate_timing(story,timing)
    if abs(duration(root/'song.wav')-timing['duration'])>.05:
        raise ValueError('Mixed audio does not match narration timeline')
    identity=render_identity(root,story,width,height)
    state_path=root/'render-state.json'
    if (root/'video.mp4').exists() and state_path.exists() and json.loads(state_path.read_text())==identity:
        return
    if not prepared_clips:
        render_clips(root,story,timing,width,height)
    if not all(clip_is_current(root,s,width,height,story=story) for s in visual_timeline(story,timing)):
        raise ValueError('Missing or stale rendered scenes; resume render jobs before joining')
    work=root/'story-motion'
    listing=work/'clips.txt'
    clips=[work/f"clip-{s['index']:03d}.mp4" for s in visual_timeline(story,timing)]
    listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    thumbnail_source=root/'thumbnail-source.png' if is_short(story) else root/'scene-000-source.png'
    with Image.open(thumbnail_source) as image:
        ImageOps.fit(image.convert('RGB'),(1280,720)).save(root/'thumbnail.jpg',quality=92)
    temp=root/'video.tmp.mp4'
    run_ffmpeg(['-f','concat','-safe','1','-i',str(listing),'-i',str(root/'song.wav'),
        '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
        '-t',str(timing['duration']),'-movflags','+faststart',str(temp)])
    measured=duration(temp)
    minimum,maximum=duration_bounds(story)
    if not minimum<=measured<=maximum or abs(measured-timing['duration'])>.1:
        raise ValueError('Rendered story duration failed verification')
    temp.replace(root/'video.mp4')
    save_json(state_path,identity)
