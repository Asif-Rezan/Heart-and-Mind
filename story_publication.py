"""Verified Hindi story uploads to the existing Heart and Mind channel."""
import datetime as dt
import time
from storage import required
from pipeline import youtube_client as original_youtube_client

HEART_CHANNEL_ID = "UCDTjTh7ORO2J_5OrR0dESTQ"

def youtube_client():
    if required("EXPECTED_CHANNEL_ID") != HEART_CHANNEL_ID:
        raise RuntimeError("Story publishing is restricted to Heart and Mind")
    return original_youtube_client()


def publish(client, root, song, state, save, upload_thumbnail=True, metadata_kind="video"):
    from googleapiclient.http import MediaFileUpload
    if not state.get('video_id'):
        if state.get('upload_started'):
            raise RuntimeError('Ambiguous upload; reconcile YouTube before retry to avoid duplicates')
        from story_upload_settings import load_settings, upload_body
        settings = load_settings(profile="story")
        metadata = song
        state['upload_description'] = metadata['description']
        state['upload_settings'] = settings
        state['upload_body'] = upload_body(metadata, metadata['description'], metadata['tags'], settings)
        state['upload_started'] = True
        save()
        request = client.videos().insert(part='snippet,status,paidProductPlacementDetails',
            body=state['upload_body'], notifySubscribers=state['upload_settings']['notify_subscribers'],
            media_body=MediaFileUpload(str(root/'video.mp4'), resumable=True, chunksize=8*1024*1024))
        result = None
        while result is None:
            _, result = request.next_chunk(num_retries=5)
        state['video_id'] = result['id']
        state['upload_completed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save()
    # One shared forty-minute processing budget leaves time for checkpoint
    # artifacts within the 45-minute recovery job, including slow scheduling.
    deadline = time.monotonic() + 2400
    if upload_thumbnail and not state.get('thumbnail_uploaded'):
        client.thumbnails().set(videoId=state['video_id'],
            media_body=MediaFileUpload(str(root/'thumbnail.jpg'))).execute()
        state['thumbnail_uploaded'] = True
        save()
    while time.monotonic() < deadline:
        items = client.videos().list(part='snippet,status,processingDetails,contentDetails,paidProductPlacementDetails',
                                    id=state['video_id']).execute().get('items', [])
        if not items:
            raise RuntimeError('Uploaded video unavailable')
        video = items[0]
        from story_upload_settings import verified_phase, ensure_synthetic_disclosure
        if video.get('snippet',{}).get('channelId') != required('EXPECTED_CHANNEL_ID'):
            raise RuntimeError('Uploaded channel mismatch')
        if video.get('status',{}).get('containsSyntheticMedia') is not True:
            ensure_synthetic_disclosure(client, video, state, save)
            video = client.videos().list(part='snippet,status,processingDetails,contentDetails,paidProductPlacementDetails',
                id=state['video_id']).execute()['items'][0]
        from story_upload_settings import ensure_uploaded_tags
        if ensure_uploaded_tags(client, video, state, save):
            continue  # Read back the repaired metadata on the same upload.
        phase = verified_phase(video, state['upload_body'], required('EXPECTED_CHANNEL_ID'),
                               state.get('synthetic_disclosure_receipt'))
        if phase:
            state['phase'] = phase
            save()
            return
        time.sleep(20)
    raise TimeoutError('HD processing pending; rerun same run ID')
