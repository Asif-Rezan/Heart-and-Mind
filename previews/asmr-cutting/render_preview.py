"""Standalone ASMR preview: consistent keyframes, flow/masking/deformation, granular sound."""
from pathlib import Path
import json, math, subprocess, wave
import cv2
import numpy as np
from scipy import signal

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
W,H,FPS,SECONDS,SR=1280,720,24,60,48000
PASS_SECONDS,CUT_SECONDS=20,4.5
cv2.setNumThreads(2)
RNG=np.random.default_rng(20261125)

def ease(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)

def sound_design():
    count=SR*SECONDS
    mix=np.zeros((count,2),np.float64)
    def add(samples,start,pan=0):
        first=round(start*SR); n=min(len(samples),count-first)
        gains=np.array([math.sqrt((1-pan)/2), math.sqrt((1+pan)/2)])
        mix[first:first+n]+=samples[:n,None]*gains
    for event in range(12):
        cut=event%4
        start=(event//4)*PASS_SECONDS+1+cut*CUT_SECONDS
        n=round(3.5*SR); t=np.arange(n)/SR
        raw=RNG.standard_normal(n)
        scrape=signal.sosfilt(signal.butter(3,[850,7800],btype='bandpass',fs=SR,output='sos'),raw)
        body=signal.sosfilt(signal.butter(3,[100,1600],btype='bandpass',fs=SR,output='sos'),raw)
        env=ease(t/.35)*(1-ease((t-2.65)/.85))
        flutter=.65+.22*np.sin(2*np.pi*(11+cut)*t)+.13*np.sin(2*np.pi*47*t)
        sound=(.11*scrape+.08*body)*env*flutter
        # Sparse tiny fractures: granular crunch with no harsh repeated digital clicks.
        for _ in range(190):
            pos=int(RNG.uniform(.12,2.9)*SR)
            k=np.arange(700)/SR
            grain=RNG.standard_normal(len(k))*np.exp(-k*RNG.uniform(320,650))
            grain=signal.sosfilt(signal.butter(2,[500,9500],btype='bandpass',fs=SR,output='sos'),grain)
            sound[pos:pos+len(k)]+=.035*RNG.uniform(.3,1)*grain[:len(sound)-pos]
        add(sound,start+.8,pan=-.35+cut*.17)
        # Soft final tray contact and a short dust/sand settling tail.
        k=np.arange(int(.16*SR))/SR
        tap=(np.sin(2*np.pi*185*k)+.35*np.sin(2*np.pi*720*k))*np.exp(-k*65)
        add(.035*tap,start+3.35,pan=-.3+cut*.15)
        n=int(.8*SR); k=np.arange(n)/SR
        tail=signal.sosfilt(signal.butter(2,[1100,6800],btype='bandpass',fs=SR,output='sos'),RNG.standard_normal(n))
        add(.021*tail*np.exp(-k*5),start+3.5,pan=-.2+cut*.1)
    mix=np.tanh(mix*1.8)*.8
    peak=np.max(np.abs(mix)); mix*=min(1,.80/max(peak,1e-9))
    target=OUT/'cutting-sound-design.wav'
    with wave.open(str(target),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR)
        f.writeframes((mix*32767).astype('<i2').tobytes())
    return target

def prepare_flow(images):
    flows=[]
    for a,b in zip(images,images[1:]):
        ga=cv2.cvtColor(cv2.resize(a,(640,360)),cv2.COLOR_RGB2GRAY)
        gb=cv2.cvtColor(cv2.resize(b,(640,360)),cv2.COLOR_RGB2GRAY)
        forward=cv2.calcOpticalFlowFarneback(ga,gb,None,.5,5,31,5,7,1.5,0)
        backward=cv2.calcOpticalFlowFarneback(gb,ga,None,.5,5,31,5,7,1.5,0)
        flows.append((cv2.resize(forward,(W,H))*2,cv2.resize(backward,(W,H))*2))
    return flows

def render():
    paths=[ROOT/'images'/f'keyframe-{i:02}.png' for i in range(5)]
    images=[cv2.cvtColor(cv2.resize(cv2.imread(str(p)),(W,H)),cv2.COLOR_BGR2RGB) for p in paths]
    flows=prepare_flow(images)
    audio=sound_design()
    target=OUT/'kinetic-sand-cutting-asmr-preview.mp4'
    command=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
             '-r',str(FPS),'-i','pipe:0','-i',str(audio),'-map','0:v','-map','1:a',
             '-c:v','libx264','-threads','2','-preset','fast','-crf','19','-pix_fmt','yuv420p',
             '-af','loudnorm=I=-19:TP=-2:LRA=6,afade=t=in:d=0.25,afade=t=out:st=59.5:d=0.5',
             '-c:a','aac','-b:a','192k','-ar',str(SR),'-t',str(SECONDS),'-movflags','+faststart',str(target)]
    encoder=subprocess.Popen(command,stdin=subprocess.PIPE)
    yy,xx=np.mgrid[:H,:W].astype(np.float32)
    particles=[RNG.random((65,5)) for _ in range(4)]
    try:
        for frame_index in range(SECONDS*FPS):
            t=frame_index/FPS
            scene_time=t%PASS_SECONDS
            if scene_time<1:
                image=images[0].copy()
            elif scene_time>=19:
                image=images[-1].copy()
            else:
                cut=min(3,int((scene_time-1)//CUT_SECONDS)); local=(scene_time-1)-cut*CUT_SECONDS
                phase=float(ease((local-.8)/2.75))
                a,b=images[cut],images[cut+1]
                flow,back=flows[cut]
                # Dense optical-flow morphing avoids a simple crossfade between stills.
                wa=cv2.remap(a,xx-phase*flow[:,:,0],yy-phase*flow[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
                wb=cv2.remap(b,xx-(1-phase)*back[:,:,0],yy-(1-phase)*back[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
                seam=(.17+cut*.07)*W
                # Feathered cutting reveal, concentrated near the evolving slice region.
                mask=np.clip(phase+(seam-xx)/W*.18*np.sin(np.pi*phase),0,1)[...,None]
                image=(wa*(1-mask)+wb*mask).astype(np.uint8)
                activity=np.sin(np.pi*phase)
                local_mask=np.exp(-((xx-seam)/(W*.10))**2)*np.clip((yy-H*.15)/(H*.6),0,1)
                displacement=activity*local_mask*H*.009
                image=cv2.remap(image,xx,yy-displacement.astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
                # Small falling grains at the seam: no simulated fountains or large debris.
                if 1.1<local<4.3:
                    for j,p in enumerate(particles[cut]):
                        age=(local-1.1-p[0]*1.8)
                        if 0<age<.7:
                            x=int(seam+(p[1]-.5)*25+(p[2]-.5)*age*42)
                            y=int(H*.78+age*age*H*.12)
                            if y<H*.91:
                                color=[(188,136,222),(62,177,169),(226,159,121)][j%3]
                                cv2.circle(image,(x,y),1+int(p[3]*1.7),color,-1,cv2.LINE_AA)
            # Restrained camera push/pan keeps the material readable without a bouncing frame.
            zoom=1.015+.022*(.5-.5*np.cos(2*np.pi*t/SECONDS))
            shift=3*np.sin(2*np.pi*t/SECONDS)
            matrix=np.array([[zoom,0,(1-zoom)*W/2+shift],[0,zoom,(1-zoom)*H/2]],np.float32)
            image=cv2.warpAffine(image,matrix,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            fade=float(ease(scene_time/.25)*ease((PASS_SECONDS-scene_time)/.25))
            image=(image*fade).astype(np.uint8)
            encoder.stdin.write(image.tobytes())
            if frame_index%(FPS*5)==0: print(f'Rendered {frame_index/FPS:.0f}/{SECONDS}s',flush=True)
    finally:
        encoder.stdin.close()
    if encoder.wait()!=0: raise RuntimeError('FFmpeg encode failed')
    report=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(target)]))
    (OUT/'media-probe.json').write_text(json.dumps(report,indent=2))
    video=next(s for s in report['streams'] if s['codec_type']=='video')
    assert video['width']==W and video['height']==H and abs(float(report['format']['duration'])-SECONDS)<.1
    assert any(s['codec_type']=='audio' and s['channels']==2 for s in report['streams'])
    subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],check=True)
    print(str(target),flush=True)

if __name__=='__main__': render()
