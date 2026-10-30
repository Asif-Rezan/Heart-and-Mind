"""Explicit story metadata and verified publication for Heart and Mind."""
import datetime as dt
import json
import os
from pathlib import Path
import re

SETTINGS=Path(__file__).with_name('story_upload_settings.json')


def load_settings(now=None, *, profile='story'):
    if profile != 'story':
        raise ValueError('This publication profile is for Hindi stories only')
    settings=json.loads(SETTINGS.read_text())
    for env,field in [('UPLOAD_MODE','mode'),('PUBLISH_AT','publish_at'),('VIDEO_LANGUAGE','language'),
                      ('AUDIO_LANGUAGE','audio_language'),('VIDEO_CATEGORY_ID','category_id')]:
        if os.getenv(env):
            settings[field]=os.environ[env]
    if settings['mode'] not in ('public','scheduled'):
        raise ValueError('Unknown story upload mode')
    if settings['language'] != 'hi' or settings['audio_language'] != 'hi' or settings['category_id'] != '27':
        raise ValueError('Stories require Hindi metadata/audio and Education category')
    for field in ('made_for_kids','contains_synthetic_media','embeddable','public_stats_viewable',
                  'notify_subscribers','paid_product_placement'):
        if type(settings[field]) is not bool:
            raise ValueError('Expected boolean setting: '+field)
    if settings['made_for_kids'] or not settings['contains_synthetic_media']:
        raise ValueError('General audience and AI disclosure are required for stories')
    if settings['license'] not in ('youtube','creativeCommon'):
        raise ValueError('Unknown video license')
    if settings['mode']=='scheduled':
        when=dt.datetime.fromisoformat((settings.get('publish_at') or '').replace('Z','+00:00'))
        if when.tzinfo is None or when <= (now or dt.datetime.now(dt.timezone.utc)):
            raise ValueError('Scheduled publication requires a future timestamp with timezone')
        settings['publish_at']=when.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
    elif settings.get('publish_at'):
        raise ValueError('Public publication must not include a future schedule')
    return settings


def upload_body(song, description, tags, settings):
    status = dict(privacyStatus='private' if settings['mode']=='scheduled' else 'public',
        selfDeclaredMadeForKids=settings['made_for_kids'], containsSyntheticMedia=settings['contains_synthetic_media'],
        license=settings['license'], embeddable=settings['embeddable'], publicStatsViewable=settings['public_stats_viewable'])
    if settings['mode']=='scheduled' and settings.get('publish_at'):
        status['publishAt'] = settings['publish_at']
    return dict(snippet=dict(title=song['title'],description=description,tags=tags,
        categoryId=settings['category_id'],defaultLanguage=settings['language'],defaultAudioLanguage=settings['audio_language']),
        status=status, paidProductPlacementDetails=dict(hasPaidProductPlacement=settings['paid_product_placement']))



def ensure_synthetic_disclosure(client, video, state, save):
    """Submit the required disclosure on the existing upload, preserving visibility.

    Some API responses omit this writeable field. Record a successful explicit
    write for that video; never treat an explicit false value as verified.
    """
    if state['upload_body']['status'].get('containsSyntheticMedia') is not True:
        raise ValueError('AI disclosure is required')
    status=video.get('status',{})
    if status.get('containsSyntheticMedia') is True:
        return
    receipt=state.get('synthetic_disclosure_receipt',{})
    if ('containsSyntheticMedia' not in status and receipt.get('video_id')==state['video_id']
            and receipt.get('accepted') is True):
        return
    if video.get('id')!=state['video_id']:
        raise RuntimeError('Uploaded video unavailable')
    # Status updates replace mutable properties: preserve the live visibility,
    # schedule and other settings instead of restoring an old private status.
    fields=('privacyStatus','publishAt','license','embeddable','publicStatsViewable','selfDeclaredMadeForKids')
    update={field:status[field] for field in fields if field in status}
    update['containsSyntheticMedia']=True
    response=client.videos().update(part='status',body={'id':state['video_id'],'status':update}).execute()
    returned=response.get('status',{})
    print(json.dumps({'check':'AI disclosure update','readback_present':'containsSyntheticMedia' in returned,
                      'readback_value':returned.get('containsSyntheticMedia')}),flush=True)
    if response.get('id')!=state['video_id'] or returned.get('containsSyntheticMedia') is False:
        raise RuntimeError('Uploaded setting mismatch: containsSyntheticMedia')
    state['synthetic_disclosure_receipt']={'video_id':state['video_id'],'accepted':True,
        'accepted_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    save()


def normalized_tags(tags):
    # YouTube may normalize casing/spacing while processing a Short.
    return {' '.join(tag.split()).casefold() for tag in tags}


def ensure_uploaded_tags(client, video, state, save):
    """Repair metadata on the existing ID, never upload a second video."""
    wanted = state['upload_body']['snippet']
    actual = video.get('snippet', {}).get('tags', [])
    if normalized_tags(actual) == normalized_tags(wanted['tags']):
        return False
    if video.get('id') != state['video_id']:
        raise RuntimeError('Uploaded video unavailable')
    # Tags are public metadata; log these alone, never API bodies or credentials.
    print(json.dumps({'check':'reconcile uploaded tags',
        'expected_tags':wanted['tags'], 'actual_tags':actual}), flush=True)
    attempts = state.get('tag_repair_attempts', 0)
    if attempts >= 2:
        raise RuntimeError('Uploaded tags mismatch')
    state['tag_repair_attempts'] = attempts + 1
    save()
    client.videos().update(part='snippet',body={'id':state['video_id'],
        'snippet':wanted}).execute(num_retries=5)
    return True


def verified_phase(video, body, channel_id, disclosure_receipt=None):
    """Return a terminal phase only for matching remote metadata and processed HD."""
    snippet, status = video.get('snippet',{}), video.get('status',{})
    if snippet.get('channelId') != channel_id:
        raise RuntimeError('Uploaded channel mismatch')
    if status.get('uploadStatus') in ('failed','rejected','deleted'):
        raise RuntimeError('YouTube rejected upload')
    for field in ('title','description','categoryId','defaultLanguage','defaultAudioLanguage'):
        if snippet.get(field) != body['snippet'][field]:
            raise RuntimeError('Uploaded metadata mismatch: ' + field)
    if normalized_tags(snippet.get('tags',[])) != normalized_tags(body['snippet']['tags']):
        raise RuntimeError('Uploaded tags mismatch')
    for field in ('selfDeclaredMadeForKids','containsSyntheticMedia','license','embeddable','publicStatsViewable'):
        if (field=='containsSyntheticMedia' and field not in status
                and body['status'][field] is True and disclosure_receipt
                and disclosure_receipt.get('accepted') is True
                and disclosure_receipt.get('video_id')==video.get('id')):
            continue
        if status.get(field) != body['status'][field]:
            raise RuntimeError('Uploaded setting mismatch: ' + field)
    if video.get('paidProductPlacementDetails',{}).get('hasPaidProductPlacement',False) != body['paidProductPlacementDetails']['hasPaidProductPlacement']:
        raise RuntimeError('Paid placement disclosure mismatch')
    if 'publishAt' in body['status'] and status.get('privacyStatus') == 'private':
        wanted=dt.datetime.fromisoformat(body['status']['publishAt'].replace('Z','+00:00'))
        got=dt.datetime.fromisoformat(status.get('publishAt','').replace('Z','+00:00'))
        if got!=wanted:
            raise RuntimeError('Scheduled time mismatch')
        phase='scheduled'
    elif status.get('privacyStatus')=='public':
        phase='published'
    else:
        raise RuntimeError('YouTube did not retain requested visibility')
    if status.get('uploadStatus')=='processed' and video.get('contentDetails',{}).get('definition')=='hd' and video.get('processingDetails',{}).get('processingStatus')=='succeeded':
        return phase
    return None
