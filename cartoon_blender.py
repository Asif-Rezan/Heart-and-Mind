"""Render voice-timed Heart and Mind shots and covers using Blender."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

from cartoon_audio import digest
from cartoon_render import FPS, valid_clip
from cartoon_story import atomic

SCRIPT = Path(__file__).with_name('cartoon_blender_scene.py')
FONT = Path(__file__).parent/'assets/artwork/LilitaOne-Regular.ttf'
GRADE = 'eq=contrast=1.28:brightness=-0.009:saturation=1.35:gamma=1.04'
COVER_GRADE = 'eq=contrast=1.23:brightness=-0.018:saturation=1.42:gamma=1.01'
PLACES = {
    'kitchen': r'\b(kitchen|stove|cupboard|refrigerator|fridge|oven)\b',
    'bedroom': r'\b(bedroom|bedside|bunk|nightstand)\b',
    'entry': r'\b(hallway|entryway|doorstep|front door|porch)\b',
    'outdoors': r'\b(outdoors|garden|backyard|park|footpath|playground|street)\b',
}
PROPS = r'\b(socks?|ball|books?|notebook|phone|keys?|bag|backpack|box(?:es)?|basket|cups?|mugs?)\b'
ALIASES = {'notebook':'book','backpack':'bag','boxes':'box','basket':'box','mug':'cup'}
TRANSFER = r'\b(hand(?:s|ed)? over|pass(?:es|ed)?|swap(?:s|ped)?|trade(?:s|d)?)\b'
HANDLE = r'\b(pick(?:s|ed)? up|lift(?:s|ed)?|hold(?:s|ing)?|held|carry|carries|carried|reach(?:es|ed)?)\b'


def layout(scene):
    visual = scene['visual'].casefold()
    place = next((name for name, pattern in PLACES.items() if re.search(pattern,visual)), 'living-room')
    match = re.search(PROPS,visual)
    word = match.group(1) if match else ''
    prop = ALIASES.get(word.rstrip('s'), ALIASES.get(word,word.rstrip('s')))
    action = scene['action']
    if action == 'approach_ball':
        prop = 'ball'
    if prop and re.search(TRANSFER,visual):
        action = 'pass'
    elif prop and re.search(HANDLE,visual):
        action = 'handle'
    holder = scene['speaker'] if scene['speaker'] in ('mira','theo') else 'mira'
    named = re.search(r'\b(mira|theo)\b[^.!?]{0,55}'+r'(?:'+TRANSFER+'|'+HANDLE+')',visual)
    if named:
        holder = named.group(1)
    return dict(place=place,prop=prop,action=action,holder=holder,speaker=scene['speaker'],
                emotion=scene['emotion'],index=scene['index'])


def blender(shot, output, *, cover=False, frames=1):
    options = dict(shot,cover=cover,frames=frames,output=str(output.resolve())+('' if cover else '/'),
                   resolution=(1280,720) if cover else (768,432))
    env = dict(os.environ,HEART_STORYBOOK_SHOT=json.dumps(options))
    log = output.parent/'blender.log'
    with log.open('w') as stream:
        try:
            subprocess.run([os.environ['HEART_BLENDER'],'-b','-t','4','--python-exit-code','1',
                            '--python',str(SCRIPT)],env=env,stdout=stream,stderr=subprocess.STDOUT,
                           check=True,timeout=2400)
        except (subprocess.SubprocessError,OSError) as error:
            raise RuntimeError(f'Blender failed on the cartoon shot {shot["index"]+1}: '
                               + '\n'.join(log.read_text(errors='replace').splitlines()[-12:])) from error


def render_shot(root, scene):
    folder = root/'cartoon-motion'
    folder.mkdir(exist_ok=True)
    target = folder/f"clip-{scene['index']:03d}.mp4"
    record = target.with_suffix('.json')
    source = root/f"scene-{scene['index']:03d}-source.png"
    signature = dict(backend='blender-storybook-v1',engine=os.environ.get('HEART_BLENDER_ENGINE','CYCLES'),
                     renderer=digest(SCRIPT),adapter=digest(Path(__file__)),scene=scene)
    frames = round((scene['end']-scene['start'])*FPS)
    if target.exists() and record.exists() and source.exists():
        try:
            saved = json.loads(record.read_text())
            if (saved['identity']==signature and saved['sha256']==digest(target)
                    and saved.get('poster_sha256')==digest(source)):
                valid_clip(target,frames,1920,1080)
                return target
        except (OSError,ValueError,KeyError,subprocess.CalledProcessError):
            pass
    shot = layout(scene)
    with TemporaryDirectory(prefix='heart-storybook-',dir=folder) as directory:
        work = Path(directory)
        plates = work/'frames'
        plates.mkdir()
        blender(shot,plates,frames=math.ceil(frames/2))
        clip = work/'clip.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-framerate','25/2','-i',str(plates/'%04d.png'),
                        '-vf',f'fps={FPS},scale=1920:1080:flags=lanczos,{GRADE}','-frames:v',str(frames),
                        '-an','-c:v','libx264','-threads','3','-preset','fast','-crf','20',
                        '-pix_fmt','yuv420p',str(clip)],check=True,timeout=300)
        valid_clip(clip,frames,1920,1080)
        poster = work/'poster.png'
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(frames/FPS*.64),'-i',str(clip),
                        '-frames:v','1',str(poster)],check=True,timeout=60)
        with Image.open(poster) as image:
            image.verify()
        poster.replace(source)
        clip.replace(target)
        atomic(record,dict(identity=signature,sha256=digest(target),poster_sha256=digest(source)))
    return target


def hook(title):
    clean = re.sub(r'^(?:what if|the|a|an)\s+|\s*\|.*$', '',title,flags=re.I)
    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?",clean)
    if not words:
        return ['WHAT','IF?']
    return [word.upper() for word in words[:min(4,len(words))]]


def cover(root, song):
    # Use an early story action with a visible prop as the visual hook.
    shots = [layout(scene) for scene in song['scenes'][:5]]
    shot = next((s for s in shots if s['prop'] and s['action'] in ('pass','handle')),None)
    shot = shot or next((s for s in shots if s['prop']),shots[0])
    with TemporaryDirectory(prefix='heart-cover-',dir=root) as directory:
        work = Path(directory)
        source, graded = work/'cover.png',work/'graded.png'
        blender(shot,source,cover=True,frames=45)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-vf',
                        f'scale=1920:1080:flags=lanczos,{COVER_GRADE}','-frames:v','1',str(graded)],
                       check=True,timeout=60)
        with Image.open(graded) as photo:
            image = photo.convert('RGB')
        draw = ImageDraw.Draw(image)
        words = hook(song['title'])
        for size in range(250,65,-3):
            font = ImageFont.truetype(str(FONT),size)
            if draw.textlength(' '.join(words),font=font) <= 1735:
                break
        x = 77
        for i, word in enumerate(words):
            draw.text((x+3,69),word,font=font,anchor='lt',stroke_width=23,stroke_fill='#160915',fill='#160915')
            draw.text((x,49),word,font=font,anchor='lt',stroke_width=16,stroke_fill='#120c16',
                      fill='#ff202c' if i==len(words)-1 else '#fff9f1')
            x += round(draw.textlength(word+' ',font=font))
        target = work/'thumbnail-source.png'
        image.save(target)
        target.replace(root/'thumbnail-source.png')
