"""Isolated English-song publication and exact-media cleanup, disabled in previews."""
import hashlib
import json
import os
from pathlib import Path
from storage import Store,required,drive_retry
from asmr.plan import atomic,digest
from asmr.render import file_hash
from .writer import validate_song
from .media import verify_products,identity

class SongStore(Store):
 CHILD_MARKER='heart_and_mind_english_songs_root'
 CHILD_LABEL='English Songs - Heart and Mind'

def enabled(name):return os.getenv('ENGLISH_SONG_'+name,'false').lower()=='true'
def backup_enabled():return enabled('PUBLISH_ENABLED') or enabled('DRIVE_BACKUP')
def prefix(song):return 'songs/'+song['run_id']
def metadata(root):return json.loads((Path(root)/'metadata.json').read_text())
def files():return ['song.wav','raw-song.wav','video.mp4','thumbnail.jpg']+[f'images/background-{i}.png' for i in range(6)]
def essentials():return ['song.json','metadata.json','media.json','music.json']

def preflight():
 if not enabled('PUBLISH_ENABLED'):return
 for name in ('DRIVE_TOKEN_JSON','DRIVE_FOLDER_ID','YOUTUBE_TOKEN_JSON','EXPECTED_CHANNEL_ID'):required(name)
 if enabled('FACEBOOK_ENABLED'):
  for name in ('FACEBOOK_PAGE_ACCESS_TOKEN','FACEBOOK_PAGE_ID'):required(name)

def history():
 if backup_enabled():return SongStore().load('history.json',[])
 p=Path('output/english-song-history.json');return json.loads(p.read_text()) if p.exists() else []

def reserve(song):
 validate_song(song);entries=history()
 for item in entries:
  if item['run_id']==song['run_id']:
   if item['identity']!=digest(song):raise ValueError('Reserved English song identity differs')
   return
  if item['lyrics_sha256']==song['lyrics_sha256'] or item['title'].casefold()==song['title'].casefold():raise ValueError('English song already reserved')
 entries.append(dict(run_id=song['run_id'],identity=digest(song),title=song['title'],lyrics_sha256=song['lyrics_sha256'],chorus=song['sections']['chorus']))
 atomic('output/english-song-history.json',entries)
 if backup_enabled():
  store=SongStore();store.save('history.json',entries);store.save(prefix(song)+'/song.json',song)

def save(root,store,song,state):
 atomic(Path(root)/'publication.json',state);store.save(prefix(song)+'/publication.json',state)

def backup(root,song,store=None):
 if not backup_enabled():return {'disabled':True}
 root=Path(root);verify_products(root,song);store=store or SongStore();state=store.load(prefix(song)+'/publication.json',{})
 if state and state.get('identity')!=identity(song):raise ValueError('English publication source changed')
 if not state:state=dict(identity=identity(song),run_id=song['run_id'],media=[],deleted=[],youtube={},facebook={},facebook_required=enabled('FACEBOOK_ENABLED'))
 if state['facebook_required']!=enabled('FACEBOOK_ENABLED'):raise ValueError('Saved English Facebook policy differs')
 if state.get('backup_complete'):
  for item in state['media']:
   if not store.verified(item['id'],item['key'],item['size'],item['md5']):raise ValueError('English backup changed or missing')
  return state
 for name in files():
  path=root/name;key=prefix(song)+'/'+name;checksum=file_hash(path)
  old=next((m for m in state['media'] if m['name']==name),None)
  if old and old['sha256']==checksum and store.verified(old['id'],key,old['size'],old['md5']):continue
  remote=store.upload(path,key)
  with path.open('rb') as f:md5=hashlib.file_digest(f,'md5').hexdigest()
  state['media']=[m for m in state['media'] if m['name']!=name]
  state['media'].append(dict(name=name,key=key,id=remote['id'],sha256=checksum,md5=md5,size=path.stat().st_size))
  save(root,store,song,state)
 for name in essentials():store.save(prefix(song)+'/'+name,json.loads((root/name).read_text()))
 state['backup_complete']=True;save(root,store,song,state);return state

def settings():
 from upload_settings import load_settings
 result=load_settings();result.update(mode='public',publish_at=None,language='en',audio_language='en',category_id='10',made_for_kids=False,contains_synthetic_media=True)
 return result

def publish(root,song):
 if not enabled('PUBLISH_ENABLED'):return {'disabled':True}
 preflight();root=Path(root);verify_products(root,song);store=SongStore();state=backup(root,song,store)
 from pipeline import youtube_client,publish as upload
 upload(youtube_client(),root,song,state['youtube'],lambda:save(root,store,song,state),settings=settings(),metadata=metadata(root))
 if enabled('FACEBOOK_ENABLED'):
  if state['youtube'].get('phase')!='published':raise ValueError('English YouTube publication not yet public')
  import facebook_publish as fb
  fb.PAGE_ID=required('FACEBOOK_PAGE_ID')
  fb.publish(fb.Facebook(required('FACEBOOK_PAGE_ACCESS_TOKEN')),root/'video.mp4','video',metadata(root),None,state['facebook'],lambda:save(root,store,song,state))
 save(root,store,song,state);return state

def cleanup(root,song):
 if not enabled('PUBLISH_ENABLED') or not enabled('CLEANUP_ENABLED'):return {'disabled':True}
 preflight();validate_song(song);root=Path(root);store=SongStore();state=store.load(prefix(song)+'/publication.json',{})
 if state.get('identity')!=identity(song) or not state.get('backup_complete'):raise ValueError('English cleanup source/backup mismatch')
 from pipeline import youtube_client
 from upload_settings import verified_phase
 part=state.get('youtube',{});client=youtube_client()
 if part.get('phase')!='published' or not part.get('video_id') or not part.get('thumbnail_uploaded'):raise ValueError('Verified public song and thumbnail required')
 remote=client.videos().list(part='snippet,status,processingDetails,contentDetails,paidProductPlacementDetails',id=part['video_id']).execute().get('items',[])
 if len(remote)!=1 or remote[0].get('id')!=part['video_id'] or verified_phase(remote[0],part['upload_body'],required('EXPECTED_CHANNEL_ID'),part.get('synthetic_disclosure_receipt'),tag_receipt=part.get('tag_verification_receipt'))!='published':raise ValueError('Fresh public-HD English song proof required')
 if state['facebook_required']:
  import facebook_publish as fb
  fb.PAGE_ID=required('FACEBOOK_PAGE_ID');api=fb.Facebook(required('FACEBOOK_PAGE_ACCESS_TOKEN'));api.verify_page()
  if not state.get('facebook',{}).get('video_id') or not fb.verify_remote(api.status(state['facebook']['video_id']),state['facebook']):raise ValueError('English Facebook publication unconfirmed; retain media')
 seen=set()
 for item in state['media']:
  if item['name'] not in files() or item['key']!=prefix(song)+'/'+item['name'] or item['id'] in seen:raise ValueError('Unsafe English cleanup manifest')
  seen.add(item['id'])
 for item in state['media']:
  if item['id'] in state['deleted']:continue
  try:
   r=drive_retry(lambda:store.client.files().get(fileId=item['id'],fields='id,name,parents,mimeType,appProperties,size,md5Checksum').execute())
   if (r.get('id')!=item['id'] or r.get('name')!=item['key'].replace('/','__') or store.folder not in r.get('parents',[])
    or r.get('appProperties',{}).get('workflow_key')!=hashlib.sha256(item['key'].encode()).hexdigest()
    or r.get('mimeType')=='application/vnd.google-apps.folder' or str(r.get('size'))!=str(item['size']) or r.get('md5Checksum')!=item['md5']):raise ValueError('Changed or unsafe English cleanup target')
   store.check_private(item['id']);drive_retry(lambda:store.client.files().delete(fileId=item['id']).execute())
  except Exception as error:
   if getattr(getattr(error,'resp',None),'status',None)!=404:raise
  state['deleted'].append(item['id']);save(root,store,song,state)
 state['cleanup_complete']=True;save(root,store,song,state)
 report=dict(run_id=song['run_id'],cleanup_complete=True,deleted_files=len(state['deleted']),reclaimed_bytes=sum(int(m['size']) for m in state['media'] if m['id'] in state['deleted']),retained=essentials()+['history.json','publication.json'],platforms_verified=True)
 atomic(root/'cleanup-report.json',report)
 summary=os.getenv('GITHUB_STEP_SUMMARY')
 if summary:
  with open(summary,'a') as f:f.write('## Verified Drive cleanup\nDeleted '+str(report['deleted_files'])+' generated media files ('+str(report['reclaimed_bytes'])+' bytes). Essential metadata and history retained.\n')
 return state

def restore(root,run_id,media=True):
 if not backup_enabled():raise ValueError('Explicit English backup/publication required for Drive restore')
 root=Path(root);store=SongStore();base='songs/'+run_id
 song=validate_song(store.load(base+'/song.json',{}));state=store.load(base+'/publication.json',{})
 if song['run_id']!=run_id or state.get('identity')!=identity(song):raise ValueError('English recovery requires original song and renderer revision')
 for name in essentials():atomic(root/name,store.load(base+'/'+name,{}))
 if media:
  for item in state['media']:
   if item['name'] not in files() or item['key']!=base+'/'+item['name']:raise ValueError('Unsafe English restore path')
   target=root/item['name'];target.parent.mkdir(parents=True,exist_ok=True);store.download(item['id'],target)
   if file_hash(target)!=item['sha256']:raise ValueError('Restored English media checksum mismatch')
  verify_products(root,song)
 atomic(root/'publication.json',state);return song
