"""Portrait-native, audio-energy-cut edits with readable editorial hook cards.

Cut points follow the generated audio's energy near the requested tempo grid.
Caption cards are editorial lyric excerpts, never claimed as forced-aligned words.
"""
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import music_video as mv
from music_cpu import validate_audio_duration
from pipeline import duration
from story_image_review import cache_current
from story_media import digest, run_ffmpeg
from story_thumbnail import export_thumbnail
from story_writer import save_json

VERSION='portrait-energy-hook-edit-v1'


def edit_plan(song, seconds, samples, rate=8000):
    if not math.isfinite(seconds) or not 0 < seconds <= 59:
        raise ValueError('Invalid Short edit duration')
    tempo=re.search(r'(\d{2,3})\s*BPM',song.get('prompt',''),re.I)
    bpm=max(60,min(160,int(tempo[1]))) if tempo else 90
    beat=60/bpm;hop=max(1,int(rate*.02))
    samples=np.asarray(samples,dtype=np.float32)
    padded=np.pad(samples,(0,(-len(samples))%hop))
    energy=np.sqrt(np.mean(padded.reshape(-1,hop)**2,axis=1)) if len(padded) else np.zeros(1)
    onset=np.maximum(0,np.diff(energy,prepend=energy[0]))
    starts=[0.0];ideal=2*beat
    while ideal < seconds-.75:
        low=max(0,int((ideal-.15)/.02));high=min(len(onset),int((ideal+.15)/.02)+1)
        window=onset[low:high]
        cut=round((low+int(np.argmax(window)))*.02,3) if len(window) and max(window)>.002 else round(ideal,3)
        if cut-starts[-1]>=.8 and seconds-cut>=.75:starts.append(cut)
        # Four-beat establishing shots alternate with two-beat punch cuts.
        ideal+=(4 if len(starts)%3 else 2)*beat
    slots=[dict(index=i,start=start,end=starts[i+1] if i+1<len(starts) else seconds,
                source=i%len(mv.planned_timeline(song)['slots']),
                move=('push-in','pull-out','pan-left','pan-right')[i%4],accent=i%4==0)
           for i,start in enumerate(starts)]
    lines=[x.strip() for x in song['lyrics'].splitlines() if x.strip() and not x.startswith('[')]
    cards=[dict(text=line,start=round(i*seconds/len(lines),3),end=round((i+1)*seconds/len(lines),3))
           for i,line in enumerate(lines)]
    return dict(version=VERSION,bpm=bpm,duration=seconds,slots=slots,cards=cards,
                alignment='editorial-lyric-cards-not-word-timestamps',cut_alignment='audio-energy-near-tempo-grid')


def caption_card(text,target,width,height):
    image=Image.new('RGBA',(width,height),(0,0,0,0));draw=ImageDraw.Draw(image)
    font_path=Path(__file__).resolve().parent/'assets/artwork/NotoSerifDevanagari.ttf'
    font=ImageFont.truetype(str(font_path),max(16,round(width*.062)))
    limit=width*.78;lines=[];line=''
    for word in text.split():
        trial=(line+' '+word).strip()
        if line and draw.textlength(trial,font=font)>limit:lines.append(line);line=word
        else:line=trial
    if line:lines.append(line)
    if len(lines)>3:raise ValueError('Short caption needs fewer words')
    spacing=round(width*.018);line_height=round(width*.09)
    top=round(height*.65);bottom=top+line_height*len(lines)+spacing*2
    draw.rounded_rectangle((width*.055,top-spacing,width*.89,bottom),radius=max(5,width*.025),fill=(12,10,20,180))
    for index,line in enumerate(lines):
        x=(width*.945-draw.textlength(line,font=font))/2
        draw.text((x,top+index*line_height),line,font=font,fill=(255,235,185,255),stroke_width=max(1,round(width/700)),stroke_fill=(20,12,28,255))
    image.save(target)


def render(root,song,width=1080,height=1920,allow_test=False):
    root=Path(root);seconds=duration(root/'song.wav')
    if not allow_test:validate_audio_duration(song,seconds)
    timing=mv.load_timeline(root,song)
    if digest(root/'song.wav')!=timing['audio_sha256']:raise ValueError('Short audio changed')
    count=len(mv.planned_timeline(song)['slots']);records={}
    for path in root.glob('music-image-manifest-*.json'):records.update(json.loads(path.read_text()))
    sources=[root/f'music-scene-{i:03d}-source.png' for i in range(count)]
    for i,path in enumerate(sources):
        if not cache_current(records.get(str(i)),mv.image_plan(song,{},i),path):
            raise ValueError('Portrait source is missing or stale')
        with Image.open(path) as image:
            if image.size!=(576,1024):raise ValueError('Short sources must be independently generated portrait images')
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(root/'song.wav'),'-ac','1','-ar','8000','-f','f32le','-'])
    plan=edit_plan(song,seconds,np.frombuffer(raw,dtype='<f4'))
    save_json(root/'short-edit-plan.json',plan)
    shutil.copyfile(sources[0],root/'thumbnail-source.png');export_thumbnail(root/'thumbnail-source.png',root/'thumbnail.jpg')
    identity=dict(version=VERSION,width=width,height=height,fps=25,timing=timing,edit_plan=plan,
        images={p.name:digest(p) for p in sources},thumbnail=digest(root/'thumbnail-source.png'))
    state=root/'music-render-state.json'
    if state.exists() and (root/'video.mp4').exists():
        previous=json.loads(state.read_text())
        if previous.get('identity')==identity and previous.get('video_sha256')==digest(root/'video.mp4') and previous.get('thumbnail_sha256')==digest(root/'thumbnail.jpg'):return
    work=root/'short-edit';work.mkdir(exist_ok=True);clips=[]
    # Round boundaries once, keeping the total edit within a single video frame.
    for slot in plan['slots']:
        frames=max(1,round(slot['end']*25)-round(slot['start']*25));i=slot['index']
        progress=f'on/{max(1,frames-1)}'
        zoom=f'1.02+0.12*{progress}' if i%2==0 else f'1.16-0.12*{progress}'
        x=f'(iw-iw/zoom)*{progress}' if i%4<2 else f'(iw-iw/zoom)*(1-{progress})'
        vf=(f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2},"
            f"zoompan=z='{zoom}':x='{x}':y='(ih-ih/zoom)/2':d={frames}:s={width}x{height}:fps=25,"
            "eq=contrast=1.04:saturation=1.08,setsar=1,format=yuv420p")
        if slot['accent'] and i>0:vf+=',fade=t=in:st=0:d=0.08:color=white'
        clip=work/f'cut-{i:03d}.mp4';clips.append(clip)
        key=dict(source=digest(sources[slot['source']]),frames=frames,vf=vf,version=VERSION)
        checkpoint=clip.with_suffix('.json')
        if clip.exists() and checkpoint.exists():
            old=json.loads(checkpoint.read_text())
            if old.get('identity')==key and old.get('sha256')==digest(clip):continue
        run_ffmpeg(['-i',str(sources[slot['source']]),'-vf',vf,'-an','-frames:v',str(frames),'-c:v','libx264',
            '-threads','4','-preset','fast','-crf','20',str(clip)])
        save_json(checkpoint,dict(identity=key,sha256=digest(clip)))
    concat=work/'cuts.txt';concat.write_text(''.join("file '"+p.name+"'\n" for p in clips))
    run_ffmpeg(['-f','concat','-safe','0','-i',str(concat),'-c','copy',str(work/'picture.mp4')])
    args=['-filter_complex_threads','1','-i',str(work/'picture.mp4'),'-i',str(root/'song.wav')]
    filters=[];tail='0:v'
    for i,card in enumerate(plan['cards']):
        path=work/f'card-{i:02d}.png';caption_card(card['text'],path,width,height)
        args+=['-i',str(path)];out=f'caption{i}'
        filters.append(f"[{tail}][{i+2}:v]overlay=0:0:enable='between(t,{card['start']},{card['end']})'[{out}]");tail=out
    filters.append(f'[{tail}]fade=t=out:st={max(0,seconds-.18)}:d=0.18,format=yuv420p[out]')
    args+=['-filter_complex',';'.join(filters),'-map','[out]','-map','1:a','-c:v','libx264','-threads','4',
        '-preset','fast','-crf','20','-c:a','aac','-b:a','256k','-t',str(seconds),'-movflags','+faststart',str(root/'video.tmp.mp4')]
    run_ffmpeg(args)
    if abs(duration(root/'video.tmp.mp4')-seconds)>.12:raise ValueError('Short edit duration mismatch')
    (root/'video.tmp.mp4').replace(root/'video.mp4')
    save_json(state,dict(identity=identity,video_sha256=digest(root/'video.mp4'),thumbnail_sha256=digest(root/'thumbnail.jpg')))
