"""Audit dedicated storage and reuse verified publication cleanup routines."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import Store, drive_retry


def main(apply=False):
    store = Store()
    def quota():
        return drive_retry(lambda: store.client.about().get(fields='storageQuota').execute())['storageQuota']
    before = quota()
    files, page = [], None
    while True:
        result = drive_retry(lambda: store.client.files().list(
            q=f"'{store.folder}' in parents and trashed = false", pageSize=1000,
            pageToken=page, fields='nextPageToken,files(id,name,size)').execute())
        files.extend(result.get('files', []))
        page = result.get('nextPageToken')
        if not page:
            break
    print(json.dumps({'phase':'storage audit','quota':before,'folder_files':len(files),
                      'folder_bytes':sum(int(f.get('size',0)) for f in files)}),flush=True)
    from pipeline import youtube_client
    client = youtube_client()
    for f in files:
        match = re.fullmatch(r'(runs|stories__runs)__([A-Za-z0-9_-]{1,80})__(state|publication)\.json', f['name'])
        if not match:
            continue
        prefix, run, kind = match.groups()
        if (prefix,kind) not in [('runs','state'),('stories__runs','publication')]:
            continue
        key=f"{prefix.replace('__','/')}/{run}/{kind}.json"
        state=store.load(key,{})
        if state.get('phase')!='published':
            continue
        from cleanup_drive import cleanup as song_cleanup, verify_public as song_verify
        from story_cleanup import cleanup as story_cleanup, verify_public as story_verify
        cleanup, verify = (story_cleanup,story_verify) if prefix=='stories__runs' else (song_cleanup,song_verify)
        try:
            verify(client,state)
            media_prefix=f'{prefix}__{run}__'
            media=[x for x in files if x['name'].startswith(media_prefix) and not x['name'].endswith(('.json','.srt'))]
            print(json.dumps({'run':run,'phase':'verified public HD','media_bytes':sum(int(x.get('size',0)) for x in media),'apply':apply}),flush=True)
            if apply:
                cleanup(store,client,run,state)
        except Exception as error:
            print(json.dumps({'run':run,'phase':'preserved','error_type':type(error).__name__}),flush=True)
    after=quota()
    print(json.dumps({'phase':'storage result','quota':after,
                      'freed_bytes':int(before.get('usageInDrive',0))-int(after.get('usageInDrive',0))}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    main(parser.parse_args().apply)
