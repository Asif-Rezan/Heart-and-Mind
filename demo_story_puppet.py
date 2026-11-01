"""Render a 60-second Hindi story demo on CPU, without publishing anything."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from story_puppet import Stage, scene_plan, encode
from story_media import run_ffmpeg, digest
from story_writer import save_json

BEATS=[
('सुबह राम अपनी छोटी दुकान खोल रहा था। तभी उसे रास्ते में एक बंद चिट्ठी मिली। उस पर पड़ोस की शिक्षिका सीता का नाम लिखा था।',
 'Ram walks in the village street carrying a letter, curious and worried.'),
('राम ने सोचा, दुकान देर से खुली तो कमाई घटेगी। लेकिन चिट्ठी में किसी की जरूरी खबर भी हो सकती थी। उसने सही रास्ता चुना।',
 'Ram stands worried at his village shop holding the letter.'),
('वह चिट्ठी लेकर सीता के स्कूल पहुँचा। सीता कई दिनों से अपने छात्र की छात्रवृत्ति के जवाब का इंतजार कर रही थी। उसकी आँखें चमक उठीं।',
 'Ram offers a letter to Sita together inside the school classroom, happy smiles.'),
('चिट्ठी में खुशखबरी थी। छात्र की पढ़ाई अब रुकने वाली नहीं थी। सीता ने कहा, तुम्हारे छोटे से कदम ने एक बड़ा सपना बचा लिया।',
 'Sita holds a letter in the school classroom, happy smile.'),
('शाम को राम लौटा तो सीता दुकान पर आई। वह अपने साथ पड़ोसियों को भी लाई थी। सबने राम की ईमानदारी की सराहना की।',
 'Ram offers a book to Sita together inside the village shop, happy smiles.'),
('उस दिन राम समझ गया, हर मदद का हिसाब पैसों में नहीं होता। कभी किसी का भरोसा जीतना ही सबसे बड़ी कमाई होती है।',
 'Ram and Sita walk together in a sunny garden, happy smiles, hopeful ending.')]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='output/puppet-demo-60s')
    parser.add_argument('--silent',action='store_true',help='Local graphics smoke check; production demo includes narration')
    args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    story=dict(title='एक छोटी मदद',characters='Ram, young Indian man, short black hair, blue kurta. Sita, Indian woman, green sari, long black hair.',
        world='A warm Indian village',scenes=[dict(index=i,text=text,visual=visual) for i,(text,visual) in enumerate(BEATS)])
    save_json(root/'story.json',story)
    if args.silent:
        lengths=[10.]*6
    else:
        import soundfile as sf
        import torch
        from kokoro import KPipeline
        from story_voice import synthesize_chunks,SAMPLE_RATE
        torch.set_num_threads(4)
        pipeline=KPipeline(lang_code='h',device='cpu',repo_id='hexgrad/Kokoro-82M')
        parts=[];lengths=[]
        for scene in story['scenes']:
            print(json.dumps(dict(phase='demo narration',scene=scene['index']+1)),flush=True)
            chunks=synthesize_chunks(pipeline,scene['text'],'hm_omega',1.0)
            if not chunks or not all(len(c) and np.isfinite(c).all() for c in chunks):
                raise RuntimeError('Empty or invalid demo speech')
            samples=np.concatenate(chunks+[np.zeros(round(.25*SAMPLE_RATE),dtype=np.float32)])
            lengths.append(len(samples)/SAMPLE_RATE);parts.append(samples)
        sf.write(root/'narration-source.wav',np.concatenate(parts),SAMPLE_RATE)
        speed=sum(lengths)/60
        # Fixed-length preview only: preserve the entire script with modest tempo fitting.
        if not .7<=speed<=1.4:raise RuntimeError(f'Demo narration would need excessive tempo adjustment: {speed}')
        run_ffmpeg(['-i',str(root/'narration-source.wav'),'-af',f'atempo={speed},loudnorm=I=-16:TP=-1.5:LRA=9',str(root/'narration.wav')])
        # Original, quiet synthesized pad; no music service or third-party recording.
        rate=24000;t=np.arange(60*rate)/rate;music=np.zeros_like(t)
        for start,notes in [(0,(146.83,185.,220.)),(15,(196.,246.94,293.66)),(30,(164.81,220.,261.63)),(45,(146.83,185.,220.))]:
            active=(t>=start)&(t<start+15);local=t[active]-start
            envelope=np.minimum(local/1.5,1)*np.minimum((15-local)/1.5,1)
            for note in notes:music[active]+=.018*np.sin(2*np.pi*note*local)*envelope
        sf.write(root/'music.wav',music,rate)
    total=sum(lengths);offset=0;clips=[];plans=[];posters=[]
    for i,seconds in enumerate(lengths):
        start=round(offset/total*1500);offset+=seconds;end=round(offset/total*1500)
        plan=scene_plan(story,dict(index=i))
        plans.append(dict(plan,start=start/25,end=end/25))
        Stage(plan).frame(.7,False).save(root/f'scene-{i:02d}.png')
        posters.append(Stage(plan,640,360).frame(.7,False))
        target=root/f'clip-{i:02d}.mp4';clips.append(target)
        print(json.dumps(dict(phase='demo puppet animation',scene=i+1,frames=end-start)),flush=True)
        encode(plan,target,end-start,25,1280,720)
    sheet=Image.new('RGB',(1920,720),'white')
    for i,poster in enumerate(posters):sheet.paste(poster,((i%3)*640,(i//3)*360))
    sheet.save(root/'storyboard.jpg',quality=92)
    save_json(root/'scene-plans.json',plans)
    (root/'clips.txt').write_text(''.join(f"file '{p.name}'\n" for p in clips))
    command=['-f','concat','-safe','1','-i',str(root/'clips.txt')]
    if not args.silent:
        command+=['-i',str(root/'narration.wav'),'-i',str(root/'music.wav'),'-filter_complex',
            '[1:a][2:a]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]',
            '-map','0:v:0','-map','[a]','-c:a','aac','-b:a','192k']
    command+=['-c:v','copy','-t','60','-movflags','+faststart',str(root/'puppet-story-60s.mp4')]
    run_ffmpeg(command)
    import subprocess
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(root/'puppet-story-60s.mp4')]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    if abs(float(probe['format']['duration'])-60)>.1 or int(video['nb_frames'])!=1500:
        raise RuntimeError('Demo must contain exactly 1500 frames / 60 seconds')
    if not args.silent and not any(s['codec_type']=='audio' for s in probe['streams']):
        raise RuntimeError('Demo narration is missing')
    save_json(root/'verification.json',dict(duration=probe['format']['duration'],frames=video['nb_frames'],
        width=video['width'],height=video['height'],sha256=digest(root/'puppet-story-60s.mp4'),
        narration=not args.silent,renderer='Python Pillow 2D puppet animation',workflow_run=__import__('os').getenv('GITHUB_RUN_ID')))
    print(root/'puppet-story-60s.mp4',flush=True)


if __name__=='__main__':main()
