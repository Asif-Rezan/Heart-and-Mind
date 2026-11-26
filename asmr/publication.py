"""Disabled-by-default publishing, isolated durable Drive state, verified media cleanup."""
import hashlib
import json
import os
from pathlib import Path
from storage import Store,required,drive_retry
from .plan import atomic,metadata,validate_plan
from .render import validate_products,file_hash,product_identity

class ASMRStore(Store):
 CHILD_MARKER='heart_and_mind_asmr_root'
 CHILD_LABEL='ASMR - Heart and Mind'

def enabled(name):return os.getenv(name,'false').lower()=='true'

def publish_enabled():return enabled('ASMR_PUBLISH_ENABLED')

def backup_enabled():return enabled('ASMR_DRIVE_BACKUP') or publish_enabled()

def preflight():
 if not publish_enabled():return {'publish':False,'facebook':False,'cleanup':False}
 for name in ('YOUTUBE_TOKEN_JSON','EXPECTED_CHANNEL_ID','DRIVE_TOKEN_JSON','DRIVE_FOLDER_ID'):required(name)
 if enabled('ASMR_FACEBOOK_ENABLED'):
  for name in ('FACEBOOK_PAGE_ACCESS_TOKEN','FACEBOOK_PAGE_ID'):required(name)
 return {'publish':True,'facebook':enabled('ASMR_FACEBOOK_ENABLED'),'cleanup':enabled('ASMR_CLEANUP_ENABLED')}

def load_history():
 if backup_enabled():return ASMRStore().load('history.json',[])
 path=Path('output/asmr-history.json')
 return json.loads(path.read_text()) if path.exists() else []

def reserve(plan):
 history=load_history()
 for item in history:
  if item.get('run_id')==plan['run_id']:
   if item['fingerprint']!=plan['fingerprint']:raise ValueError('ASMR run identity already reserved for different media')
   return
  if item.get('fingerprint')==plan['fingerprint'] or item.get('title','').casefold()==plan['video']['title'].casefold():raise ValueError('ASMR idea was already reserved')
 history.append(dict(run_id=plan['run_id'],title=plan['video']['title'],idea=plan['idea'],fingerprint=plan['fingerprint'],
  recipes=[{k:s[k] for k in ('material','shape','pattern','palette','cuts')} for s in plan['scenes']]))
 atomic('output/asmr-history.json',history[-100:])
 if backup_enabled():
  store=ASMRStore();store.save('history.json',history)
  store.save(f"episodes/{plan['run_id']}/plan.json",plan)

def save_state(root,store,key,state):
 atomic(Path(root)/'publication.json',state)
 store.save(key,state)

def backup(root,plan,store=None):
 if not backup_enabled():return {'disabled':True}
 root=Path(root);validate_products(root,plan)
 store=store or ASMRStore();prefix=f"episodes/{plan['run_id']}"
 key=prefix+'/publication.json'
 state=store.load(key,{})
 identity=product_identity(plan)
 if state and state.get('identity')!=identity:raise ValueError('ASMR publication source changed; reconcile existing checkpoint')
 if not state:state=dict(identity=identity,run_id=plan['run_id'],plan=plan,media=[],youtube={},facebook={},deleted=[],facebook_required=enabled('ASMR_FACEBOOK_ENABLED'))
 if state.get('facebook_required',False)!=enabled('ASMR_FACEBOOK_ENABLED'):raise ValueError('ASMR Facebook policy differs from its saved publication checkpoint')
 if state.get('backup_complete'):
  save_state(root,store,key,state);return state
 media=[root/'video.mp4',root/'thumbnail.jpg',root/'short'/'video.mp4',root/'short'/'thumbnail.jpg']
 media+=sorted((root/'scenes').glob('scene-*.mp4'))+sorted((root/'scenes').glob('scene-*.jpg'))
 for path in media:
  name=path.relative_to(root).as_posix();remote_key=prefix+'/'+name
  if any(entry['name']==name and entry['sha256']==file_hash(path) for entry in state['media']):continue
  result=store.upload(path,remote_key)
  with path.open('rb') as f:md5=hashlib.file_digest(f,'md5').hexdigest()
  state['media'].append(dict(id=result['id'],key=remote_key,name=name,sha256=file_hash(path),md5=md5,size=path.stat().st_size))
  save_state(root,store,key,state)
 state['backup_complete']=True
 save_state(root,store,key,state)
 store.save(prefix+'/plan.json',plan)
 store.save(prefix+'/media.json',json.loads((root/'media.json').read_text()))
 return state

def production_settings():
 from upload_settings import load_settings
 result=load_settings()
 result.update(mode='public',publish_at=None,made_for_kids=False,contains_synthetic_media=True,category_id='24',language='en',audio_language='en')
 return result

def publish_youtube(root,plan):
 if not publish_enabled():return {'disabled':True}
 preflight();root=Path(root);validate_products(root,plan)
 store=ASMRStore();state=backup(root,plan,store)
 if not state.get('backup_complete'):raise ValueError('Complete verified ASMR backup required')
 key=f"episodes/{plan['run_id']}/publication.json"
 from pipeline import youtube_client,publish
 client=youtube_client()
 for kind,folder in [('video',root),('shorts',root/'short')]:
  part=state['youtube'].setdefault(kind,{})
  meta=metadata(plan,kind)
  if part.get('upload_body') and part['upload_body']['snippet']['title']!=meta['title']:raise ValueError('Saved ASMR upload metadata changed')
  publish(client,folder,meta,part,lambda:save_state(root,store,key,state),upload_thumbnail=(kind=='video'),settings=production_settings(),metadata=meta)
 save_state(root,store,key,state)
 return state

def publish_facebook(root,plan):
 if not publish_enabled() or not enabled('ASMR_FACEBOOK_ENABLED'):return {'disabled':True}
 preflight();root=Path(root);store=ASMRStore();key=f"episodes/{plan['run_id']}/publication.json"
 state=store.load(key,{})
 if state.get('identity')!=product_identity(plan):raise ValueError('ASMR Facebook source identity mismatch')
 import facebook_publish as fb
 fb.PAGE_ID=required('FACEBOOK_PAGE_ID')
 for kind,remote_kind,folder in [('video','video',root),('shorts','short',root/'short')]:
  if state.get('youtube',{}).get(kind,{}).get('phase')!='published':raise ValueError('Verified YouTube publication required before ASMR Facebook upload')
  part=state['facebook'].setdefault(kind,{})
  fb.publish(fb.Facebook(required('FACEBOOK_PAGE_ACCESS_TOKEN')),folder/'video.mp4',remote_kind,metadata(plan,kind),None,part,lambda:save_state(root,store,key,state))
 return state

def cleanup(root,plan):
 if not publish_enabled() or not enabled('ASMR_CLEANUP_ENABLED'):return {'disabled':True}
 preflight();root=Path(root);store=ASMRStore();key=f"episodes/{plan['run_id']}/publication.json"
 state=store.load(key,{})
 if state.get('identity')!=product_identity(plan) or not state.get('backup_complete'):raise ValueError('ASMR cleanup checkpoint identity mismatch')
 from pipeline import youtube_client
 from upload_settings import verified_phase
 client=youtube_client()
 # Fresh publication proof for BOTH products, not merely a saved success boolean.
 for kind in ('video','shorts'):
  part=state.get('youtube',{}).get(kind,{})
  if part.get('phase')!='published' or not part.get('video_id'):raise ValueError('Both ASMR uploads must be public before media cleanup')
  result=client.videos().list(part='snippet,status,processingDetails,contentDetails,paidProductPlacementDetails',id=part['video_id']).execute().get('items',[])
  if len(result)!=1 or result[0].get('id')!=part['video_id']:raise ValueError('ASMR cleanup remote video identity mismatch')
  if verified_phase(result[0],part['upload_body'],required('EXPECTED_CHANNEL_ID'),part.get('synthetic_disclosure_receipt'),tag_receipt=part.get('tag_verification_receipt'))!='published':raise ValueError('Public HD ASMR publication is not confirmed')
 if state.get('facebook_required'):
  import facebook_publish as fb
  fb.PAGE_ID=required('FACEBOOK_PAGE_ID');api=fb.Facebook(required('FACEBOOK_PAGE_ACCESS_TOKEN'));api.verify_page()
  for kind in ('video','shorts'):
   part=state.get('facebook',{}).get(kind,{})
   if not part.get('video_id') or not fb.verify_remote(api.status(part['video_id']),part):raise ValueError('Both ASMR Facebook uploads must be confirmed before cleanup')
 allowed={'video.mp4','thumbnail.jpg','short/video.mp4','short/thumbnail.jpg'}
 allowed|={f'scenes/scene-{i:02}.{ext}' for i in range(12) for ext in ('mp4','jpg')}
 prefix=f"episodes/{plan['run_id']}/"
 seen=set()
 # Validate the WHOLE deletion manifest before deleting the first file.
 for entry in state['media']:
  if entry['name'] not in allowed or entry['key']!=prefix+entry['name'] or entry['id'] in seen:raise ValueError('Unsafe ASMR cleanup manifest')
  seen.add(entry['id'])
 for entry in state['media']:
  if entry['id'] in state['deleted']:continue
  try:
   remote=drive_retry(lambda:store.client.files().get(fileId=entry['id'],fields='id,name,parents,appProperties,mimeType,size,md5Checksum').execute())
   if (remote.get('id')!=entry['id'] or remote.get('name')!=entry['key'].replace('/','__') or store.folder not in remote.get('parents',[])
    or remote.get('mimeType')=='application/vnd.google-apps.folder' or remote.get('appProperties',{}).get('workflow_key')!=hashlib.sha256(entry['key'].encode()).hexdigest()
    or remote.get('md5Checksum')!=entry['md5'] or str(remote.get('size'))!=str(entry['size'])):raise ValueError('Unsafe or changed ASMR cleanup target')
   store.check_private(entry['id']);drive_retry(lambda:store.client.files().delete(fileId=entry['id']).execute())
  except Exception as error:
   if getattr(getattr(error,'resp',None),'status',None)!=404:raise
  state['deleted'].append(entry['id']);save_state(root,store,key,state)
 state['cleanup_complete']=True;save_state(root,store,key,state)
 return state


def restore(root,run_id,media=True):
 if not backup_enabled():raise ValueError('Drive restore requires explicitly enabled backup or publication')
 root=Path(root);store=ASMRStore();prefix=f'episodes/{run_id}'
 plan=validate_plan(store.load(prefix+'/plan.json',{}))
 if plan['run_id']!=run_id:raise ValueError('Drive ASMR episode identity mismatch')
 state=store.load(prefix+'/publication.json',{})
 if state.get('identity')!=product_identity(plan):raise ValueError('Restore must use the original ASMR renderer revision')
 atomic(root/'plan.json',plan)
 for entry in state.get('media',[]):
  name=entry['name']
  allowed={'video.mp4','thumbnail.jpg','short/video.mp4','short/thumbnail.jpg'}
  allowed|={f'scenes/scene-{i:02}.{ext}' for i in range(12) for ext in ('mp4','jpg')}
  if name not in allowed or entry['key']!=prefix+'/'+name:raise ValueError('Unsafe ASMR restore path')
  if not media:continue
  target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
  store.download(entry['id'],target)
  if file_hash(target)!=entry['sha256']:raise ValueError('Restored ASMR media checksum mismatch')
 atomic(root/'publication.json',state)
 atomic(root/'media.json',store.load(prefix+'/media.json',{}))
 if media:validate_products(root,plan)
 return plan
