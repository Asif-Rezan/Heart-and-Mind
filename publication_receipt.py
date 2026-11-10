"""Report verified visibility separately from successful rendering."""
import datetime as dt
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo


def report(state):
    phase=state.get('phase')
    video_id=state.get('video_id','')
    if phase not in ('published','scheduled') or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',video_id):
        raise ValueError('A verified upload and video ID are required for a publication receipt')
    when=state.get('schedule_target') or state.get('upload_body',{}).get('status',{}).get('publishAt')
    receipt=dict(platform='YouTube',status=phase,video_url='https://www.youtube.com/watch?v='+video_id)
    if phase=='scheduled':
        if not when:
            raise ValueError('Scheduled upload receipt requires its publication time')
        target=dt.datetime.fromisoformat(when.replace('Z','+00:00'))
        if target.tzinfo is None:
            raise ValueError('Scheduled upload receipt requires a timezone')
        receipt.update(publish_at=when,publish_at_dhaka=target.astimezone(ZoneInfo('Asia/Dhaka')).isoformat())
    print(json.dumps(receipt),flush=True)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
            stream.write('### Verified YouTube upload\n\n['+video_id+']('+receipt['video_url']+')\n\n')
            if phase=='scheduled':
                stream.write('**Scheduled, not public yet.** Release (Asia/Dhaka): '+receipt['publish_at_dhaka']+'.\n')
            else:
                stream.write('**Public:** YouTube visibility and processing verified.\n')
    return receipt
