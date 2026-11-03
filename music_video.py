"""Five-second, lyric-directed 3D music visuals and a measured cinematic edit.

Uses the current story image backend/style; singing remains the saved ACE-Step path.
Scene progression is editorial pacing, not a claim of word-level lyric alignment.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil

from PIL import Image
from artwork import visual_mood
from story_art_style import VERSION as ART_VERSION, art_prompt
from story_image_review import VERSION as REVIEW_VERSION, cache_current, generate_reviewed
from story_image_cpu import MODEL, REVISION
from story_media import digest, run_ffmpeg
from story_thumbnail import SOURCE_SIZE, export_thumbnail
from story_visual_contract import compile_contract, REVIEW_VERSION as PLAN_REVIEW_VERSION
from story_writer import save_json

FORMAT = 'hindi-music-storybook-5s-v1'
VERSION = 'cinematic-music-edit-v2'
MUSIC_ART_VERSION = 'romantic-couple-outfits-v7'
IMAGE_SECONDS = 5
FPS = 25
DISSOLVE = .4
SHARDS = 14


def song_identity(song):
    fields = {k: song.get(k) for k in ('title', 'lyrics', 'visual_mood', 'background_prompt', 'thumbnail_prompt', 'visual_scenes')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def visual_timeline(seconds):
    if not math.isfinite(seconds) or not 0 < seconds <= 360:raise ValueError('Invalid music duration')
    return [dict(index=i,start=i*IMAGE_SECONDS,end=min((i+1)*IMAGE_SECONDS,seconds))
            for i in range(math.ceil(seconds/IMAGE_SECONDS))]


def planned_timeline(song):
    """Image identities use requested duration so synthesis never blocks image workers."""
    return dict(slots=visual_timeline(song['duration']))


def source_index(song, index):
    return min(index, len(planned_timeline(song)['slots'])-1)


def prepare_timeline(root, song, allow_short=False):
    from pipeline import duration, validate_duration
    root=Path(root);seconds=duration(root/'song.wav')
    if not allow_short:validate_duration(seconds)
    plan=dict(version=VERSION,format=FORMAT,song_identity=song_identity(song),
              audio_sha256=digest(root/'song.wav'),duration=seconds,fps=FPS,image_seconds=IMAGE_SECONDS,
              alignment='editorial-progression-not-lyric-transcription',slots=visual_timeline(seconds))
    save_json(root/'music-video-timing.json',plan)
    return plan


def load_timeline(root, song):
    plan=json.loads((Path(root)/'music-video-timing.json').read_text())
    if (plan.get('version')!=VERSION or plan.get('song_identity')!=song_identity(song) or
            plan.get('slots')!=visual_timeline(plan['duration'])):
        raise ValueError('Music visual timeline is stale; rebuild from the saved audio')
    return plan


def scene_contract(song, index, count, kind='background'):
    mood=visual_mood(song)
    defaults={
        'romance':'An adult couple share a tender reunion beside a warm courtyard lamp',
        'heartbreak':'An adult couple part quietly on a rainy railway platform, with reflected station lights',
        'healing':'An adult woman walks toward a soft sunrise, beginning again with quiet hope'}
    field='thumbnail_prompt' if kind=='thumbnail' else 'background_prompt'
    scenes=song.get('visual_scenes')
    scenes=[s for s in scenes if isinstance(s,str) and 40<=len(s)<=160 and not re.search(r'[\u0900-\u097f]',s)] if isinstance(scenes,list) else []
    scenes=scenes or [song.get('background_prompt') or defaults[mood]]
    selected=min(len(scenes)-1,int((index+.5)/max(1,count)*len(scenes)))
    event=song.get(field) if kind=='thumbnail' else scenes[selected]
    if not isinstance(event,str) or re.search(r'[\u0900-\u097f]',event):event=defaults[mood]
    # Keep lyric-specific action; discard historical typography directions.
    clauses=[s.strip() for s in re.split(r'[.;]+',event) if s.strip() and not re.search(r'\b(?:lettering|typography|watermark|poster|logo|caption)\b',s,re.I)]
    event='; '.join(clauses) or defaults[mood]
    if len(event)>160:event=event[:161].rsplit(' ',1)[0]
    if len(event)<15:event=defaults[mood]
    # Select one outfit per image rather than asking diffusion to draw alternatives.
    outfit_key=int(hashlib.sha256((song_identity(song)+':outfit:'+kind+':'+str(index)).encode()).hexdigest()[:8],16)
    male_outfit=('shirt','T-shirt')[outfit_key % 2]
    female_outfit=('casual top','sari','stylish fitted dress')[(outfit_key // 2) % 3]
    people='woman, 28, Indian, '+female_outfit
    if mood!='healing':people+='; man, 30, Indian, '+male_outfit
    lines=[x.strip() for x in song['lyrics'].splitlines() if x.strip() and not x.lstrip().startswith('[')]
    evidence=(lines[min(len(lines)-1,int(index/max(1,count)*len(lines)))] if lines else song['lyrics'])[:300]
    checks=[dict(question='Who is shown in this scene?',answers=['woman'] if mood=='healing' else ['couple'])]
    if mood!='healing':
        checks.extend([dict(question='How many people are shown?',answers=['two']),
                       dict(question='How many faces are visible?',answers=['two'])])
    record=compile_contract(dict(event=event,people=people,setting='The lyric-specific music video setting',evidence=evidence,checks=checks))
    record['music_portrait']=dict(version=MUSIC_ART_VERSION,couple=mood!='healing',
                                 male_outfit=male_outfit,female_outfit=female_outfit)
    record['fallback']=dict(mode='authored-scene',literal_event=event,reason='songwriter-visual-direction')
    record['planning_review']=dict(version=PLAN_REVIEW_VERSION,passed=False,
        issues=['Creative interpretation of the song; not independently verified lyric alignment.'])
    return record


def image_plan(song, timing, index, kind='background'):
    timing=planned_timeline(song);count=len(timing['slots']);contract=scene_contract(song,index,count,kind)
    width,height=SOURCE_SIZE if kind=='thumbnail' else ((576,1024) if song.get('media_kind')=='shorts' else (1024,576))
    plan=dict(kind=kind,contract=contract,prompt=art_prompt(contract['prompt'] + ('; vertical portrait composition, subjects centred, generous headroom' if song.get('media_kind')=='shorts' else ''),kind),
              model=MODEL,revision=REVISION,art_version=ART_VERSION,review_version=REVIEW_VERSION,
              music_art_version=MUSIC_ART_VERSION,music_format=FORMAT,song_identity=song_identity(song),width=width,height=height,steps=20,
              seed=int(hashlib.sha256((song_identity(song)+':'+kind+':'+str(index)).encode()).hexdigest()[:8],16))
    if kind=='background':plan.update(timing['slots'][index])
    return plan


def generate_images(root, song, shard=None, shards=None):
    root=Path(root);timing=planned_timeline(song)
    shard=int(os.getenv('IMAGE_SHARD','0')) if shard is None else shard
    shards=int(os.getenv('IMAGE_SHARDS','1')) if shards is None else shards
    if not 0<=shard<shards:raise ValueError('Invalid music image shard')
    path=root/f'music-image-manifest-{shard:02d}.json'
    previous=json.loads(path.read_text()) if path.exists() else {};completed={}
    for slot in timing['slots']:
        i=slot['index']
        if i%shards!=shard:continue
        plan=image_plan(song,timing,i);target=root/f'music-scene-{i:03d}-source.png'
        if cache_current(previous.get(str(i)),plan,target):report=previous[str(i)]['review']
        else:
            temp=target.with_suffix('.tmp.png')
            report=generate_reviewed(plan['prompt'],temp,plan['seed'],plan['contract'],width=plan['width'],height=plan['height'],steps=plan['steps'])
            with Image.open(temp) as image:image.verify()
            temp.replace(target)
        completed[str(i)]=dict(plan,review=report);save_json(path,completed)
    if shard==0:
        shutil.copyfile(root/'music-scene-000-source.png',root/'background-source.png')
        if song.get('media_kind')=='shorts':
            return completed
        plan=image_plan(song,timing,0,'thumbnail');target=root/'thumbnail-source.png';state=root/'music-thumbnail-manifest.json'
        old=json.loads(state.read_text()) if state.exists() else {}
        if not cache_current(old,plan,target):
            temp=target.with_suffix('.tmp.png')
            report=generate_reviewed(plan['prompt'],temp,plan['seed'],plan['contract'],kind='thumbnail',width=plan['width'],height=plan['height'],steps=plan['steps'])
            temp.replace(target);save_json(state,dict(plan,review=report))
        export_thumbnail(target,root/'thumbnail.jpg')
    return completed


def package_images(root, destination, shard, shards):
    root=Path(root);target=Path(destination)/root.name;target.mkdir(parents=True,exist_ok=True)
    manifest=root/f'music-image-manifest-{shard:02d}.json'
    if not manifest.is_file():return
    records=json.loads(manifest.read_text());owned={k:v for k,v in records.items() if int(k)%shards==shard}
    save_json(target/manifest.name,owned)
    for key in owned:shutil.copyfile(root/f'music-scene-{int(key):03d}-source.png',target/f'music-scene-{int(key):03d}-source.png')
    if shard==0:
        for name in ('background-source.png','thumbnail-source.png','thumbnail.jpg','music-thumbnail-manifest.json'):
            if (root/name).exists():shutil.copyfile(root/name,target/name)


def render(root, song, width=1920, height=1080, allow_short=False):
    from pipeline import duration,validate_duration
    root=Path(root);timing=load_timeline(root,song);seconds=timing['duration'];slots=timing['slots']
    if not allow_short:validate_duration(seconds)
    if digest(root/'song.wav')!=timing['audio_sha256']:raise ValueError('Music audio changed; rebuild its visual timeline')
    sources=[root/f"music-scene-{source_index(song,s['index']):03d}-source.png" for s in slots]
    if not allow_short or song.get('media_kind')=='shorts':
        records={}
        for file in root.glob('music-image-manifest-*.json'):records.update(json.loads(file.read_text()))
        if any(not cache_current(records.get(str(source_index(song,s['index']))),image_plan(song,timing,source_index(song,s['index'])),p) for s,p in zip(slots,sources)):
            raise ValueError('Music scene assets are missing or stale')
        thumb=json.loads((root/'music-thumbnail-manifest.json').read_text())
        if not cache_current(thumb,image_plan(song,timing,0,'thumbnail'),root/'thumbnail-source.png'):
            raise ValueError('Music thumbnail is missing or stale')
    export_thumbnail(root/'thumbnail-source.png',root/'thumbnail.jpg')
    identity=dict(version=VERSION,width=width,height=height,fps=FPS,timing=timing,
                  images={p.name:digest(p) for p in sources},thumbnail=digest(root/'thumbnail-source.png'))
    state=root/'music-render-state.json'
    if (root/'video.mp4').exists() and state.exists() and json.loads(state.read_text()).get('identity')==identity and json.loads(state.read_text()).get('video_sha256')==digest(root/'video.mp4') and json.loads(state.read_text()).get('thumbnail_sha256')==digest(root/'thumbnail.jpg'):return
    export_thumbnail(root/'thumbnail-source.png',root/'thumbnail.jpg')
    work=root/'music-motion';work.mkdir(exist_ok=True);clips=[]
    bpm_match=re.search(r'(\d{2,3})\s*BPM',song.get('prompt',''),re.I)
    bpm=max(40,min(180,int(bpm_match[1]))) if bpm_match else 80
    overlaps=[min(DISSOLVE,max(1/FPS,slots[i+1]['end']-slots[i+1]['start'])) for i in range(len(slots)-1)]
    for i,slot in enumerate(slots):
        length=slot['end']-slot['start']+(overlaps[i] if i<len(overlaps) else 0)
        frames=max(1,math.ceil(length*FPS-1e-7));clip=work/f'clip-{i:03d}.mp4';clips.append(clip)
        clip_state=clip.with_suffix('.json');key=dict(source=digest(sources[i]),frames=frames,width=width,height=height,version=VERSION,bpm=bpm)
        if clip.exists() and clip_state.exists() and json.loads(clip_state.read_text()).get('identity')==key:
            if json.loads(clip_state.read_text()).get('sha256')==digest(clip):continue
        progress=f'on/{max(1,frames-1)}'
        zoom=f'1.035+0.04*{progress}' if i%2==0 else f'1.075-0.04*{progress}'
        travel=f'(iw-iw/zoom)*{progress}' if i%4<2 else f'(iw-iw/zoom)*(1-{progress})'
        vf=(f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2},"
            f"zoompan=z='{zoom}':x='{travel}':y='(ih-ih/zoom)/2':d={frames}:s={width}x{height}:fps={FPS},"
            f"eq=contrast=1.025:saturation=1.04:brightness='0.006*sin(2*PI*(t+{slot['start']})*{bpm}/60)':eval=frame,"
            'vignette=PI/8,setsar=1,format=yuv420p')
        temp=clip.with_suffix('.tmp.mp4')
        run_ffmpeg(['-i',str(sources[i]),'-vf',vf,'-an','-frames:v',str(frames),'-r',str(FPS),
                    '-c:v','libx264','-threads','4','-preset','fast','-crf','20',str(temp)])
        if abs(duration(temp)-frames/FPS)>.06:raise ValueError('Music clip duration mismatch')
        temp.replace(clip);save_json(clip_state,dict(identity=key,sha256=digest(clip)))
    filters=[f'[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]' for i in range(len(clips))]
    tail='v0'
    for i in range(1,len(clips)):
        out=f'blend{i}';filters.append(f'[{tail}][v{i}]xfade=transition=fade:duration={overlaps[i-1]}:offset={slots[i]["start"]}[{out}]');tail=out
    audio_index=len(clips)
    filters += [f'[{audio_index}:a]asplit=2[audio][meter]',
        f'[meter]showwaves=s={min(1600,width-80)}x64:mode=line:colors=0xffdbaf:rate=25,format=rgba,colorkey=black:0.05:0.1,colorchannelmixer=aa=0.55[wave]',
        f'[{tail}][wave]overlay=(W-w)/2:H-100:eof_action=repeat:shortest=0,fade=t=in:d=0.3,fade=t=out:st={max(0,seconds-.6)}:d=0.6,format=yuv420p[out]']
    script=work/'edit.ffscript';script.write_text(';\n'.join(filters))
    args=['-filter_complex_threads','1']
    for clip in clips:args+=['-threads','1','-i',str(clip)]
    args+=['-i',str(root/'song.wav'),'-filter_complex',script.read_text(),'-map','[out]','-map','[audio]',
           '-c:v','libx264','-threads','4','-preset','fast','-crf','20','-c:a','aac','-b:a','320k',
           '-t',str(seconds),'-movflags','+faststart',str(root/'video.tmp.mp4')]
    run_ffmpeg(args)
    if abs(duration(root/'video.tmp.mp4')-seconds)>.12:raise ValueError('Music/video duration mismatch')
    (root/'video.tmp.mp4').replace(root/'video.mp4');save_json(state,dict(identity=identity,video_sha256=digest(root/'video.mp4'),thumbnail_sha256=digest(root/'thumbnail.jpg')))


def validate_rendered(root,song):
    from pipeline import duration,validate_duration
    root=Path(root);state=json.loads((root/'music-render-state.json').read_text())
    key=state['identity']
    if (key['version']!=VERSION or key['timing']['song_identity']!=song_identity(song) or
            state['video_sha256']!=digest(root/'video.mp4') or state['thumbnail_sha256']!=digest(root/'thumbnail.jpg') or
            key['timing']['audio_sha256']!=digest(root/'song.wav')):
        raise ValueError('Prepared music video is stale or modified')
    validate_duration(duration(root/'video.mp4'))



if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--stage',choices=['timeline','images','package','render'],required=True)
    parser.add_argument('--destination',type=Path,default=Path('artifacts/music-images'))
    args=parser.parse_args();song=json.loads((args.root/'song.json').read_text())
    if args.stage=='timeline':prepare_timeline(args.root,song)
    elif args.stage=='images':generate_images(args.root,song)
    elif args.stage=='package':package_images(args.root,args.destination,int(os.getenv('IMAGE_SHARD','0')),int(os.getenv('IMAGE_SHARDS','1')))
    else:render(args.root,song)
