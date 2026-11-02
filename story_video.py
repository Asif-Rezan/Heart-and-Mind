"""Reference-style SSD-1B illustrations and measured scene camera motion."""
from story_art_style import art_prompt, VERSION as ART_VERSION
from story_thumbnail import SOURCE_SIZE as THUMBNAIL_SOURCE_SIZE, EXPORT_SIZE as THUMBNAIL_EXPORT_SIZE, export_thumbnail
from story_visual_contract import require_visuals
from story_image_review import generate_reviewed, cache_current, VERSION as REVIEW_VERSION
import hashlib
import json
import math
import os
from pathlib import Path
from PIL import Image, ImageOps
from story_media import digest, run_ffmpeg
from story_writer import scene_prompt, save_json, StoryValidationError

from story_format import IMAGE_SECONDS, duration_bounds, is_short

VERSION = 'hindi-story-motion-v3-four-second-scenes'
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
    from story_image_cpu import MODEL, REVISION
    require_visuals(story)
    root = Path(root)
    shard, count = int(os.getenv('IMAGE_SHARD','0')), int(os.getenv('IMAGE_SHARDS','1'))
    if not 0 <= shard < count:
        raise ValueError('Invalid story image shard')
    manifest = root/f'image-manifest-{shard:02d}.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    complete = {}
    short=is_short(story)
    timing=json.loads((root/'timing.json').read_text()) if short or render_ready else None
    slots=visual_timeline(story,timing) if short else story['scenes']
    for slot in slots:
        i=slot['index']
        scene=story['scenes'][slot.get('story_scene',i)]
        if i % count != shard:
            continue
        prompt=art_prompt(story['visuals'][str(scene['index'])])
        if short:
            view='medium shot, clear expressive face and story object' if i%2 else 'wide shot, clear action and setting'
            prompt=art_prompt(story['visuals'][str(scene['index'])]+'. '+view)
        contract=story['visual_contracts'][str(scene['index'])]
        plan = dict(prompt=prompt, model=MODEL, revision=REVISION,art_version=ART_VERSION,review_version=REVIEW_VERSION,contract=contract,
                    width=1024, height=576, steps=20)
        plan['seed'] = int(hashlib.sha256((story['run_id']+str(i)).encode()).hexdigest()[:8],16)
        if short:
            plan.update(story_scene=scene['index'],start=slot['start'],end=slot['end'])
        target = root/f'scene-{i:03d}-source.png'
        valid = False
        if cache_current(previous.get(str(i)),plan,target):
            try:
                with Image.open(target) as image:
                    image.verify()
                valid = True
            except (OSError, ValueError):
                pass
        if not valid:
            temp = target.with_suffix('.tmp.png')
            review=generate_reviewed(plan['prompt'],temp,seed=plan['seed'],contract=contract,
                                     width=1024,height=576,steps=20)
            with Image.open(temp) as image:
                image.verify()
            temp.replace(target)
        complete[str(i)] = dict(plan,review=previous[str(i)]['review'] if valid else review)
        save_json(manifest, complete)
        if render_ready:
            # This frame can render now; no cross-worker image barrier.
            render_clips(root,story,timing,shard=shard,shards=count,only_indices={i})

    if short and shard==0:
        thumbnail_plan=dict(prompt=art_prompt(story['thumbnail_prompt'], 'thumbnail'),
            model=MODEL,revision=REVISION,art_version=ART_VERSION,width=THUMBNAIL_SOURCE_SIZE[0],height=THUMBNAIL_SOURCE_SIZE[1],steps=20,
            seed=int(hashlib.sha256((story['run_id']+':thumbnail-v2').encode()).hexdigest()[:8],16),
            story_scene=story['thumbnail_scene'],contract=story['thumbnail_contract'],
            viewer_question=story['thumbnail_question'],review_version=REVIEW_VERSION,export_size=list(THUMBNAIL_EXPORT_SIZE))
        target=root/'thumbnail-source.png'
        state=root/'thumbnail-manifest.json'
        current=False
        if state.exists() and cache_current(json.loads(state.read_text()),thumbnail_plan,target):
            try:
                with Image.open(target) as image:
                    image.verify()
                current=True
            except (OSError,ValueError):
                pass
        if not current:
            temp=target.with_suffix('.tmp.png')
            review=generate_reviewed(thumbnail_plan['prompt'],temp,seed=thumbnail_plan['seed'],
                     contract=story['thumbnail_contract'],kind='thumbnail',
                     width=thumbnail_plan['width'],height=thumbnail_plan['height'],
                     steps=20)
            with Image.open(temp) as image:
                image.verify()
            temp.replace(target)
            save_json(state,dict(thumbnail_plan,review=review))


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
    if is_short(story):
        files += [root/'thumbnail-source.png']
    return dict(version=VERSION,width=width,height=height,fps=FPS,sources={p.name:digest(p) for p in files})


def clip_identity(root, scene, width, height):
    return dict(version=VERSION,index=scene['index'],start=scene['start'],end=scene['end'],
        width=width,height=height,fps=FPS,source=digest(Path(root)/f"scene-{scene['index']:03d}-source.png"))


def clip_is_current(root, scene, width=1920, height=1080):
    work=Path(root)/'story-motion'
    target=work/f"clip-{scene['index']:03d}.mp4"
    manifest=target.with_suffix('.json')
    if not target.is_file() or not manifest.is_file():
        return False
    try:
        saved=json.loads(manifest.read_text())
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
        if (only_indices is not None and i not in only_indices) or i%shards!=shard or clip_is_current(root,scene,width,height):
            continue
        frames=round(scene['end']*FPS)-round(scene['start']*FPS)
        # A final sub-frame tail still needs a visible frame; audio is never cut.
        frames=max(1,frames)
        source=root/f'scene-{i:03d}-source.png'
        with Image.open(source) as image:
            image.verify()
        clip=work/f'clip-{i:03d}.mp4'
        temp=clip.with_suffix('.tmp.mp4')
        zoom=f'1.04+0.045*on/{max(1,frames-1)}'
        travel=f'(iw-iw/zoom)*on/{max(1,frames-1)}' if i%2 else f'(iw-iw/zoom)*(1-on/{max(1,frames-1)})'
        vf=(f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2},"
            f"zoompan=z='{zoom}':x='{travel}':y='(ih-ih/zoom)/2':d={frames}:s={width}x{height}:fps={FPS},"
            'setsar=1,format=yuv420p')
        run_ffmpeg(['-i',str(source),'-vf',vf,'-an','-frames:v',str(frames),'-r',str(FPS),
            '-c:v','libx264','-threads','4','-preset','fast','-crf','20',str(temp)])
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
        raise StoryValidationError('render_audio_duration_mismatch',dict(expected_seconds=timing['duration'],actual_seconds=duration(root/'song.wav')))
    required=[root/'story.json',root/'timing.json',root/'song.wav']
    required += [root/f"scene-{s['index']:03d}-source.png" for s in visual_timeline(story,timing)]
    if is_short(story):required.append(root/'thumbnail-source.png')
    missing=[p.name for p in required if not p.is_file()]
    if missing:raise StoryValidationError('render_assets_missing',dict(files=missing))
    thumbnail_source=root/'thumbnail-source.png' if is_short(story) else root/'scene-000-source.png'
    export_thumbnail(thumbnail_source,root/'thumbnail.jpg')
    identity=render_identity(root,story,width,height)
    state_path=root/'render-state.json'
    if (root/'video.mp4').exists() and state_path.exists() and json.loads(state_path.read_text())==identity:
        return
    if not prepared_clips:
        render_clips(root,story,timing,width,height)
    invalid=[s['index'] for s in visual_timeline(story,timing) if not clip_is_current(root,s,width,height)]
    if invalid:
        raise StoryValidationError('render_clips_missing_or_stale',dict(scenes=invalid))
    work=root/'story-motion'
    listing=work/'clips.txt'
    clips=[work/f"clip-{s['index']:03d}.mp4" for s in visual_timeline(story,timing)]
    listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    temp=root/'video.tmp.mp4'
    run_ffmpeg(['-f','concat','-safe','1','-i',str(listing),'-i',str(root/'song.wav'),
        '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
        '-t',str(timing['duration']),'-movflags','+faststart',str(temp)])
    measured=duration(temp)
    minimum,maximum=duration_bounds(story)
    if not minimum<=measured<=maximum or abs(measured-timing['duration'])>.1:
        raise StoryValidationError('render_duration_mismatch',dict(expected_seconds=timing['duration'],actual_seconds=measured))
    temp.replace(root/'video.mp4')
    save_json(state_path,identity)
