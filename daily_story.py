"""Daily original Hindi story -> Kokoro speech -> ACE-Step score -> YouTube."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
from story_writer import save_json, validate_story, write_story, novelty_reason, text_hash


def root_for(run_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
        raise ValueError('Invalid story run ID')
    root = Path('output')/run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def load_story(root):
    return validate_story(json.loads((root/'story.json').read_text()))


def plan(root, run_id, check_history, mode="plan"):
    from storage import Store
    store = Store() if check_history else None
    history = store.load('stories/history.json', []) if store else []
    if store:
        cleanup_previous(store, history)
    saved = store.load(f'stories/runs/{run_id}/story.json', None) if store else None
    if saved:
        validate_story(saved)
        if (root/'story.json').exists() and json.loads((root/'story.json').read_text()) != saved:
            raise ValueError('Local story differs from the reserved daily identity')
        save_json(root/'story.json', saved)
    if mode == 'outline':
        from story_plan import prepare_outline
        prepare_outline(root,run_id,history)
        return
    if mode == 'assemble':
        from story_plan import assemble_story
        story=assemble_story(root,run_id,history)
    else:
        story = write_story(root, run_id, history)
    if story['run_id'] != run_id:
        raise ValueError('Recovered manifest belongs to a different story run')
    others = [h for h in history if h.get('run') != run_id]
    if novelty_reason(story, others):
        raise ValueError('Duplicate story refused before synthesis')
    if store:
        # Reserve unfinished/scheduled stories as well as publicly released ones.
        store.save(f'stories/runs/{run_id}/story.json', story)
        entry = dict(run=run_id,title=story['title'],summary=story['summary'],
            hash=text_hash(story['lyrics']),lines=[s['text'] for s in story['scenes']])
        store.save('stories/history.json', others+[entry])
    return story


def music_parts(seconds):
    if not 480 <= seconds <= 720:
        raise ValueError('Story duration must be 8-12 minutes')
    # Equal parts bounded to 120 seconds; no tiny final music request.
    count = math.ceil(seconds/120)
    return [math.ceil(seconds/count)]*count


def score_request(story, index):
    if type(index) is not int or not 0<=index<6:
        raise ValueError('Invalid background music part')
    mood=('gentle reflective piano, soft strings' if index==0 else
          'warm hopeful piano, rising strings' if index==5 else
          'restrained emotional piano, subtle ambient strings')
    return dict(_segment=True,instrumental=True,duration=120,lyrics='[Instrumental]',
        prompt='Instrumental cinematic background score for an Indian emotional motivational story, '+mood+
        ', no vocals, no singing, no speech, sparse arrangement, quiet accompaniment under dialogue.')


def generate_score_part(root,story,index):
    from story_music_cpu import generate_segment
    from pipeline import duration
    work=Path(root)/'score'/f'part-{index}'
    request=score_request(story,index)
    work.mkdir(parents=True,exist_ok=True)
    manifest=dict(story_hash=text_hash(story['lyrics']),run_id=story['run_id'],request=request,index=index)
    manifest_path=work/'request.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text())!=manifest:
        raise ValueError('Saved music part belongs to different story inputs')
    save_json(manifest_path,manifest)
    state_path=work/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {}
    save=lambda:save_json(state_path,state)
    target=work/'bgm.wav'
    generate_segment(request,target,state,save)
    if duration(target)<119.95:
        raise RuntimeError('Background score too short; never pad or loop music')


def mix_score(root,story,timing):
    from story_media import run_ffmpeg,digest
    from pipeline import duration
    from story_video import validate_timing
    validate_timing(story,timing)
    root=Path(root)
    if abs(duration(root/'narration.wav')-timing['duration'])>.05:
        raise ValueError('Narration audio differs from its measured timeline')
    work=root/'score'
    work.mkdir(exist_ok=True)
    paths=[]
    for i in range(6):
        part=work/f'part-{i}'
        path=part/'bgm.wav'
        expected=dict(story_hash=text_hash(story['lyrics']),run_id=story['run_id'],request=score_request(story,i),index=i)
        if not (part/'request.json').is_file() or json.loads((part/'request.json').read_text())!=expected:
            raise ValueError('Missing or mismatched background music checkpoint')
        if duration(path)<119.95:
            raise RuntimeError('Background score too short; never pad or loop music')
        normalized=work/f'normalized-{i}.wav'
        run_ffmpeg(['-i',str(path),'-t','120','-ar','24000','-ac','1',str(normalized)])
        paths.append(normalized)
    listing=work/'parts.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in paths))
    run_ffmpeg(['-f','concat','-safe','1','-i',str(listing),'-c','copy',str(root/'background.wav')])
    if duration(root/'background.wav')<timing['duration']-.05:
        raise RuntimeError('Complete background score is shorter than speech')
    seconds=timing['duration']
    # All six parts may be generated before speech. Only excess instrumental
    # accompaniment is trimmed; the complete measured narration is preserved.
    graph=(f'[0:a]asplit=2[voice][control];[1:a]volume=0.10,afade=t=in:d=1,'
        f'afade=t=out:st={max(0,seconds-2)}:d=2[bed];'
        '[bed][control]sidechaincompress=threshold=0.025:ratio=6:attack=20:release=300[ducked];'
        '[voice][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[out]')
    temp=root/'song.tmp.wav'
    run_ffmpeg(['-i',str(root/'narration.wav'),'-i',str(root/'background.wav'),
        '-filter_complex',graph,'-map','[out]','-ar','24000','-t',str(seconds),str(temp)])
    if abs(duration(temp)-seconds)>.05:
        raise ValueError('Mixed story duration differs from speech')
    temp.replace(root/'song.wav')
    save_json(root/'mix.json',dict(narration=digest(root/'narration.wav'),
        background=digest(root/'background.wav'),duration=seconds,instrumental=True))


def score(root,story,timing):
    # Local compatibility command. Production runs the six parts in separate jobs.
    for i in range(6):
        generate_score_part(root,story,i)
    mix_score(root,story,timing)


def publish_story(root, story, run_id, defer_drive_cleanup=False):
    from story_publication import publish, youtube_client
    from pipeline import duration
    from storage import Store
    from story_video import render_identity
    from story_media import digest
    from story_upload_settings import load_settings
    load_settings(profile='story')
    store = Store()
    client = youtube_client()
    key = f'stories/runs/{run_id}/publication.json'
    state = store.load(key, {})
    save = lambda: store.save(key, state)
    if state.get('story_hash') and state['story_hash'] != text_hash(story['lyrics']):
        raise ValueError('Publication identity differs from the reserved story')
    state['story_hash'] = text_hash(story['lyrics'])
    state['song'] = story
    save()
    if not state.get('video_id'):
        history = store.load('stories/history.json', [])
        if novelty_reason(story, [h for h in history if h.get('run') != run_id]):
            raise ValueError('Duplicate story refused before publication')
        if not 480 <= duration(root/'video.mp4') <= 720:
            raise ValueError('Only 8-12 minute story videos may be published')
        if json.loads((root/'render-state.json').read_text()) != render_identity(root, story):
            raise ValueError('Video render is stale; render current story assets first')
        fingerprint = digest(root/'video.mp4')
        if state.get('video_hash') and state['video_hash'] != fingerprint:
            raise ValueError('Video bytes changed during publication recovery')
        state['video_hash'] = fingerprint
        save()
        for name in ('story.json','timing.json','narration.wav','background.wav','song.wav',
                     'mix.json','video.mp4','thumbnail.jpg','render-state.json'):
            store.upload(root/name, f'stories/runs/{run_id}/{name}')
    publish(client, root, story, state, save)
    history = store.load('stories/history.json', [])
    for entry in history:
        if entry.get('run') == run_id:
            entry['video_id'] = state['video_id']
    store.save('stories/history.json', history)
    if state['phase'] == 'published' and not defer_drive_cleanup:
        from story_cleanup import cleanup
        cleanup(store,client,run_id,state)
        state['backup_cleanup_complete'] = True
        save()
    save_json(root/'publication.json',dict(video_id=state['video_id'],phase=state['phase'],
        publish_at=state.get('schedule_target') or state['upload_settings'].get('publish_at')))
    print(json.dumps({'phase':state['phase'],'video_id':state['video_id']}), flush=True)


def cleanup_previous(store, history):
    """Release verified public media quota; preserve scheduled/unverified stories."""
    from story_publication import youtube_client, publish
    from story_cleanup import cleanup
    client = None
    for entry in history:
        if not entry.get('video_id'):
            continue
        run_id = entry['run']
        root = root_for(run_id)
        key = f'stories/runs/{run_id}/publication.json'
        state = store.load(key, {})
        if state.get('backup_cleanup_complete') or not state.get('video_id'):
            continue
        target = state.get('schedule_target') or state.get('upload_settings',{}).get('publish_at')
        if target and dt.datetime.fromisoformat(target.replace('Z','+00:00')) > dt.datetime.now(dt.timezone.utc):
            continue
        try:
            client = client or youtube_client()
            save = lambda: store.save(key, state)
            publish(client,root,state['song'],state,save,upload_thumbnail=False)
            if state.get('phase') == 'published':
                cleanup(store,client,run_id,state)
                state['backup_cleanup_complete'] = True
                save()
        except Exception:
            # One stale/unavailable upload must not block today's fresh story.
            # Exact guards retain its media; the next daily run retries cleanup.
            print(json.dumps({'phase':'story media cleanup deferred','run_id':run_id}),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--stage',choices=['plan','outline','chapter','assemble','voice','music','music-part','mix','images','render-clips','render','publish','recover'],required=True)
    parser.add_argument('--check-history',action='store_true')
    parser.add_argument('--part',type=int)
    parser.add_argument('--prepared-clips',action='store_true')
    parser.add_argument('--defer-drive-cleanup',action='store_true',
        help='Let the separate verified Drive cleanup job remove temporary media')
    args = parser.parse_args()
    root = root_for(args.run_id)
    try:
        if args.stage in ('plan','outline','assemble'):
            plan(root,args.run_id,args.check_history,mode=args.stage)
            (root/'failure.json').unlink(missing_ok=True)
            return
        if args.stage == 'recover':
            recover(root, args.run_id)
            return
        if args.stage == 'chapter':
            from story_plan import write_chapter
            write_chapter(root,args.run_id,args.part)
            (root/'failure.json').unlink(missing_ok=True)
            return
        story = load_story(root)
        if story['run_id'] != args.run_id:
            raise ValueError('Manifest belongs to a different story run')
        if args.stage == 'voice':
            from story_voice import generate_voice
            generate_voice(root,story)
        elif args.stage == 'images':
            from story_video import generate_images
            generate_images(root,story)
        elif args.stage == 'music-part':
            generate_score_part(root,story,args.part)
        elif args.stage == 'mix':
            mix_score(root,story,json.loads((root/'timing.json').read_text()))
        elif args.stage == 'render-clips':
            from story_video import render_clips
            render_clips(root,story,json.loads((root/'timing.json').read_text()),
                shard=int(os.getenv('IMAGE_SHARD','0')),shards=int(os.getenv('IMAGE_SHARDS','1')))
        elif args.stage == 'music':
            score(root,story,json.loads((root/'timing.json').read_text()))
        elif args.stage == 'render':
            from story_video import render
            render(root,story,json.loads((root/'timing.json').read_text()),prepared_clips=args.prepared_clips)
        elif args.stage == 'publish':
            publish_story(root,story,args.run_id,defer_drive_cleanup=args.defer_drive_cleanup)
    except Exception as error:
        # Do not print API response bodies or credentials into public Actions logs.
        from pipeline import pipeline_failure_message
        from story_writer import StoryValidationError
        details=getattr(error,'details',{}) if isinstance(error,StoryValidationError) else {}
        code=getattr(error,'code','pipeline_error') if isinstance(error,StoryValidationError) else 'pipeline_error'
        diagnostic=dict(stage=args.stage,error_type=type(error).__name__,code=code,details=details,
            message=pipeline_failure_message(error))
        save_json(root/'failure.json',diagnostic)
        print(json.dumps(diagnostic),flush=True)
        raise SystemExit(1)


def recover(root, run_id):
    """Reconcile an existing upload; never generate or insert another video."""
    from storage import Store
    from story_publication import publish, youtube_client
    store = Store()
    key = f'stories/runs/{run_id}/publication.json'
    state = store.load(key, {})
    if not state.get('video_id'):
        raise ValueError('No existing uploaded story to recover')
    story = validate_story(state['song'])
    if not state.get('thumbnail_uploaded'):
        fid = store.find(f'stories/runs/{run_id}/thumbnail.jpg')
        if not fid:
            raise ValueError('Saved story thumbnail is missing')
        store.download(fid, root/'thumbnail.jpg')
    publish(youtube_client(),root,story,state,lambda:store.save(key,state))
    save_json(root/'publication.json',dict(video_id=state['video_id'],phase=state['phase']))
    print(json.dumps({'phase':state['phase'],'video_id':state['video_id']}),flush=True)


if __name__ == '__main__':
    main()
