"""Generate comparable Hindi voice samples without music or publishing."""
import argparse
import hashlib
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from story_voice import SAMPLE_RATE,synthesize_chunks,prepare_speech
from story_voice_model import voice_profile,load_pipeline
from story_writer import save_json
from story_media import run_ffmpeg,digest

LINES=[
 'शाम को दुकान बंद करते हुए राम को दरवाज़े पर एक चिट्ठी मिली। वह कुछ देर उसे देखता रहा।',
 'उसे डर था कि इसमें कोई बुरी खबर होगी। तभी सीता ने कहा, पहले पढ़ तो लो।',
 'चिट्ठी उसके पुराने शिक्षक की थी। उन्होंने लिखा था, तुम्हारी ईमानदारी ने पूरे गाँव का भरोसा जीत लिया है।',
 'राम मुस्कुराया। उस दिन उसे समझ आया कि छोटी सी मदद भी किसी की ज़िंदगी में बड़ा बदलाव ला सकती है।']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='output/hindi-voice-preview')
    args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    text='\n'.join(LINES);(root/'script.txt').write_text(text)
    records=[]
    import torch
    torch.set_num_threads(4)
    for engine,voice,label in [('kokoro','hm_omega','01-current-kokoro'),('goonj','hi_ravi','02-hindi-ravi'),('goonj','hi_atul','03-hindi-atul')]:
        profile=voice_profile(engine,voice);started=time.monotonic()
        print(f'Generating {label}',flush=True)
        pipeline,speaker=load_pipeline(profile)
        pieces=[]
        for i,line in enumerate(LINES):
            chunks=synthesize_chunks(pipeline,line,speaker,1.0)
            if not chunks:raise RuntimeError('Missing Hindi speech')
            samples=prepare_speech(np.concatenate(chunks))
            pieces.append(samples)
            if i<len(LINES)-1:pieces.append(np.zeros(round(.15*SAMPLE_RATE),dtype=np.float32))
        source=root/f'{label}-source.wav';target=root/f'{label}.wav'
        sf.write(source,np.concatenate(pieces),SAMPLE_RATE,subtype='PCM_16')
        run_ffmpeg(['-i',str(source),'-af','loudnorm=I=-16:TP=-1.5:LRA=9','-ar',str(SAMPLE_RATE),'-ac','1','-c:a','pcm_s16le',str(target)])
        info=sf.info(target)
        records.append(dict(file=target.name,profile=profile,duration=info.duration,
            generation_seconds=round(time.monotonic()-started,1),sha256=digest(target)))
        save_json(root/'comparison.json',dict(script_sha256=hashlib.sha256(text.encode()).hexdigest(),
            sample_rate=SAMPLE_RATE,speed=1.0,music=False,voices=records))
        source.unlink()
        print(records[-1],flush=True)
    print('All comparison samples generated',flush=True)


if __name__=='__main__':main()
