"""One-minute preview: current Kokoro narration + fresh SSD-1B story illustrations."""
import argparse
import json
import math
import os
from pathlib import Path
from story_writer import save_json
from story_media import run_ffmpeg,digest

ROOT=Path('output/background-story-demo')
BEATS=[
('राम अपनी छोटी दुकान बंद कर रहा था। तभी दरवाज़े के नीचे एक पुरानी चिट्ठी दिखी। उसे उठाते हुए उसके हाथ कुछ पल रुक गए।',
 'Ram, adult Indian man, short black hair, blue kurta, discovers an envelope at his small village shop door at sunset.'),
('सीता ने पूछा, क्या बात है? राम बोला, शायद किसी उधार की याद दिलाई गई है। सीता मुस्कुराई और बोली, पहले पढ़ तो लो।',
 'Ram, adult Indian man in blue kurta, holds an envelope. Sita, adult Indian woman in green sari, gently encourages him inside the shop.'),
('चिट्ठी उसके पुराने शिक्षक की थी। उन्होंने लिखा था कि राम ने जिस बच्चे को मुफ्त किताबें दी थीं, वह अब डॉक्टर बन गया है।',
 'Ram, adult Indian man, short black hair, blue kurta, reads a letter beside neatly stacked schoolbooks inside his small village shop, thoughtful face.'),
('राम को वह बरसात का दिन याद आया। बच्चे के पास पैसे नहीं थे। उसने किताबें थमाकर बस इतना कहा था, मन लगाकर पढ़ना।',
 'Ram, adult Indian man in blue kurta, remembers handing schoolbooks to a fully clothed Indian student at his village shop doorway on a rainy afternoon.'),
('आज उसी बच्चे ने गाँव में एक छोटा अस्पताल खोला था। चिट्ठी में राम और सीता को उसके उद्घाटन का निमंत्रण भेजा गया था।',
 'Ram, adult Indian man in blue kurta, and Sita, adult Indian woman in green sari, happily hold an invitation outside a modest village clinic, no lettering.'),
('राम की आँखें भर आईं। सीता ने धीरे से उसका हाथ थाम लिया। छोटी सी मदद, इतने साल बाद, पूरे गाँव की उम्मीद बन गई थी।',
 'Ram, adult Indian man in blue kurta, and Sita, adult Indian woman in green sari, hold hands outside a modest village clinic at golden sunset, hopeful smiles.')]


def voice(root):
    import numpy as np
    import soundfile as sf
    import torch
    from story_voice import SAMPLE_RATE,synthesize_chunks,prepare_speech
    from story_voice_model import voice_profile,load_pipeline
    torch.set_num_threads(4)
    profile=voice_profile('kokoro','hm_omega')
    pipeline,speaker=load_pipeline(profile)
    speed=1.0
    for attempt in range(2):
        parts=[];lengths=[]
        for i,(text,_) in enumerate(BEATS):
            samples=prepare_speech(np.concatenate(synthesize_chunks(pipeline,text,speaker,speed)))
            if i<5:samples=np.concatenate([samples,np.zeros(round(.08*SAMPLE_RATE),dtype=np.float32)])
            lengths.append(len(samples)/SAMPLE_RATE);parts.append(samples)
        seconds=sum(lengths)
        if seconds<=59.5:break
        speed=min(1.08,round(speed*seconds/58,3))
    if not 45<=seconds<=59.5:
        raise RuntimeError(f'Natural demo narration outside 45-59.5 seconds: {seconds}; no speech truncation/time stretching')
    sf.write(root/'narration.wav',np.concatenate(parts),SAMPLE_RATE,subtype='PCM_16')
    start=0;scenes=[]
    for i,length in enumerate(lengths):
        scenes.append(dict(index=i,start=start,end=start+length));start+=length
    save_json(root/'timing.json',dict(duration=seconds,video_duration=60,speed=speed,scenes=scenes,profile=profile,
        outro_seconds=60-seconds,speech_truncated=False,time_stretched=False))
    (root/'script.txt').write_text('\n'.join(text for text,_ in BEATS))
    print(json.dumps(dict(phase='natural demo narration',duration=seconds,speed=speed,outro=60-seconds)),flush=True)


def image(root,index):
    from story_image_cpu import generate,MODEL,REVISION
    if not 0<=index<len(BEATS):raise ValueError('Invalid scene index')
    prompt=BEATS[index][1]+'. Colorful polished 3D storybook illustration, expressive faces, beautiful warm pastel Indian setting, cinematic light, wide landscape, no text.'
    target=root/f'scene-{index:02d}.png'
    seed=20261101+index*1009
    generate(prompt,target,seed=seed,width=1024,height=576,steps=20)
    save_json(root/f'image-{index:02d}.json',dict(model=MODEL,revision=REVISION,prompt=prompt,seed=seed,width=1024,height=576,steps=20,sha256=digest(target)))


def render(root):
    import numpy as np
    import soundfile as sf
    from PIL import Image,ImageOps
    timing=json.loads((root/'timing.json').read_text())
    clips=[]
    for i,scene in enumerate(timing['scenes']):
        end=60 if i==5 else scene['end']
        frames=round(end*25)-round(scene['start']*25)
        target=root/f'clip-{i:02d}.mp4';clips.append(target)
        source=root/f'scene-{i:02d}.png'
        with Image.open(source) as picture:picture.verify()
        zoom=f'1.04+0.045*on/{max(1,frames-1)}'
        travel=f'(iw-iw/zoom)*on/{max(1,frames-1)}'
        vf=f"scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440,zoompan=z='{zoom}':x='{travel}':y='(ih-ih/zoom)/2':d={frames}:s=1280x720:fps=25,setsar=1,format=yuv420p"
        run_ffmpeg(['-i',str(source),'-vf',vf,'-an','-frames:v',str(frames),'-c:v','libx264','-threads','4','-preset','fast','-crf','20',str(target)])
    # Original quiet synthesized music bed; the narrator remains dominant.
    rate=24000;t=np.arange(rate*60)/rate;music=np.zeros_like(t)
    for start,notes in [(0,(146.83,185.,220.)),(15,(196.,246.94,293.66)),(30,(164.81,220.,261.63)),(45,(146.83,185.,220.))]:
        active=(t>=start)&(t<start+15);local=t[active]-start
        envelope=np.minimum(local/1.5,1)*np.minimum((15-local)/1.5,1)
        for note in notes:music[active]+=.014*np.sin(2*np.pi*note*local)*envelope
    music*=np.minimum((60-t)/2,1)
    sf.write(root/'music.wav',music,rate)
    (root/'clips.txt').write_text(''.join(f"file '{p.name}'\n" for p in clips))
    run_ffmpeg(['-f','concat','-safe','1','-i',str(root/'clips.txt'),'-i',str(root/'narration.wav'),'-i',str(root/'music.wav'),
        '-filter_complex','[1:a]loudnorm=I=-16:TP=-1.5:LRA=9[v];[v][2:a]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=false[a]',
        '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-t','60','-movflags','+faststart',str(root/'sample-video-60s.mp4')])
    sheet=Image.new('RGB',(1920,720))
    for i in range(6):
        with Image.open(root/f'scene-{i:02d}.png') as picture:sheet.paste(ImageOps.fit(picture.convert('RGB'),(640,360)),((i%3)*640,(i//3)*360))
    sheet.save(root/'storyboard.jpg',quality=92)
    import subprocess
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(root/'sample-video-60s.mp4')]))
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    if abs(float(probe['format']['duration'])-60)>.1 or int(stream['nb_frames'])!=1500 or not any(s['codec_type']=='audio' for s in probe['streams']):
        raise RuntimeError('Demo must contain sixty seconds / 1500 frames and narration audio')
    save_json(root/'verification.json',dict(duration=probe['format']['duration'],frames=stream['nb_frames'],width=stream['width'],height=stream['height'],
        sha256=digest(root/'sample-video-60s.mp4'),workflow_run=os.getenv('GITHUB_RUN_ID'),voice=timing['profile'],
        native_speed=timing['speed'],narration_seconds=timing['duration'],outro_seconds=timing['outro_seconds'],image_count=6,
        renderer='AI background images with camera motion',speech_truncated=False,time_stretched=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['voice','image','render'],required=True)
    parser.add_argument('--part',type=int,default=0)
    args=parser.parse_args();ROOT.mkdir(parents=True,exist_ok=True)
    if args.stage=='voice':voice(ROOT)
    elif args.stage=='image':image(ROOT,args.part)
    else:render(ROOT)


if __name__=='__main__':main()
