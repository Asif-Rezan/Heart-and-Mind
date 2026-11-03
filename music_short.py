"""One independently synthesized portrait companion per long song."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from music_cpu import generate, validate_audio_duration
from pipeline import validate_song, duration, publish, youtube_client
from music_video import generate_images, prepare_timeline, song_identity
from short_edit import render
from story_media import digest
from story_writer import save_json
from storage import Store

FORMAT = 'hindi-music-portrait-short-v1'


def short_id(parent):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', parent):
        raise ValueError('Invalid parent run ID')
    base = parent if len(parent)<=74 else parent[:61]+'-'+hashlib.sha256(parent.encode()).hexdigest()[:12]
    return base+'-short'


def companion(parent, parent_run):
    validate_song(parent)
    from lyric_quality import parse_sections
    sections = parse_sections(parent['lyrics'])
    chorus = sections.get('chorus', [])
    bridge = sections.get('bridge', [])
    if len(chorus)!=4 or len(bridge)!=2:
        raise ValueError('Companion requires the reviewed four-line chorus and two-line bridge')
    song = copy.deepcopy(parent)
    for field in ('lyric_quality','lyric_quality_version','authored_source'):
        song.pop(field,None)
    song.update(media_kind='shorts',video_format=FORMAT,duration=45,
        title=parent['title'][:91].rstrip()+' #Shorts',
        lyrics='[Chorus]\n'+'\n'.join(chorus)+'\n[Bridge]\n'+'\n'.join(bridge)+'\n[Outro]\n'+'\n'.join(chorus[-2:]),
        prompt=parent['prompt'][:350]+'. Separate 45-second hook-first arrangement: immediate solo singing, bright plucked guitar and intimate piano, crisp light percussion, short resolved ending, no long intro or instrumental breaks.',
        parent_run=parent_run,parent_song_identity=song_identity(parent))
    validate_song(song,allow_short=True)
    return song


def prepare(parent_run):
    parent_root=Path('output')/parent_run
    song=companion(json.loads((parent_root/'song.json').read_text()),parent_run)
    root=Path('output')/short_id(parent_run);root.mkdir(parents=True,exist_ok=True)
    target=root/'song.json'
    if target.exists() and json.loads(target.read_text())!=song:
        raise ValueError('Saved companion differs; use the original source checkpoint')
    save_json(target,song)
    return root


def validate_media(root,song):
    validate_song(song,allow_short=True)
    validate_audio_duration(song,duration(root/'song.wav'))
    validate_audio_duration(song,duration(root/'video.mp4'))
    state=json.loads((root/'music-render-state.json').read_text())
    identity=state['identity']
    from short_edit import VERSION as EDIT_VERSION
    if identity.get('version')!=EDIT_VERSION:
        raise ValueError('Companion needs the dedicated Shorts edit')
    if (identity['width'],identity['height'])!=(1080,1920):
        raise ValueError('Shorts render must be 1080x1920')
    if (identity['timing']['song_identity']!=song_identity(song) or
        identity['timing']['audio_sha256']!=digest(root/'song.wav') or
        state['video_sha256']!=digest(root/'video.mp4') or
        state['thumbnail_sha256']!=digest(root/'thumbnail.jpg')):
        raise ValueError('Shorts media was modified or belongs to another song')
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height','-of','json',str(root/'video.mp4')],text=True))
    if [(x['width'],x['height']) for x in info['streams']] != [(1080,1920)]:
        raise ValueError('Measured Shorts dimensions must be 1080x1920')
    if abs(duration(root/'song.wav')-duration(root/'video.mp4'))>.15:
        raise ValueError('Shorts video/audio duration mismatch')


def publish_short(parent_run):
    from cleanup_drive import cleanup
    identity=short_id(parent_run);root=Path('output')/identity
    song=json.loads((root/'song.json').read_text())
    if song.get('parent_run')!=parent_run or song.get('media_kind')!='shorts':
        raise ValueError('Companion parent mismatch')
    validate_media(root,song)
    store=Store();client=youtube_client();key=f'runs/{identity}/state.json'
    state=store.load(key,{})
    if state.get('song') and state['song']!=song:
        raise ValueError('Published companion identity differs from prepared media')
    state.update(song=song,hash=hashlib.sha256(song['lyrics'].encode()).hexdigest())
    save=lambda:store.save(key,state)
    save()
    if not state.get('video_id') and not state.get('upload_started'):
        for name in ('song.json','song.wav','video.mp4','thumbnail.jpg','music-render-state.json'):
            store.upload(root/name,f'runs/{identity}/{name}')
    publish(client,root,song,state,save)
    # No shared long-song history write: parallel publishing cannot lose its entries.
    save_json(root/'publication.json',dict(video_id=state['video_id'],parent_run=parent_run,phase=state['phase']))
    cleanup(store,client,identity,state)
    print(json.dumps(dict(phase=state['phase'],video_id=state['video_id'],media_kind='shorts')),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--parent-run',required=True)
    parser.add_argument('--stage',required=True,choices=['plan','music','images','package','render','publish'])
    args=parser.parse_args();identity=short_id(args.parent_run)
    if args.stage=='plan':prepare(args.parent_run);return
    root=Path('output')/identity;song=json.loads((root/'song.json').read_text())
    validate_song(song,allow_short=True)
    if args.stage=='music':
        path=root/'generation-state.json';state=json.loads(path.read_text()) if path.exists() else {}
        generate(song,root/'song.wav',state,lambda:save_json(path,state))
        prepare_timeline(root,song,allow_short=True)
    elif args.stage=='images':generate_images(root,song)
    elif args.stage=='package':
        import os
        from music_video import package_images
        package_images(root,Path('artifacts/music-images'),int(os.getenv('IMAGE_SHARD','0')),int(os.getenv('IMAGE_SHARDS','1')))
    elif args.stage=='render':
        render(root,song,width=1080,height=1920);validate_media(root,song)
    else:publish_short(args.parent_run)


if __name__=='__main__':main()
