"""ASMR content fidelity, repeat protection, real geometry, publishing and cleanup guards."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import types
from unittest.mock import Mock,patch
import numpy as np
from asmr.plan import finish,validate_plan,generate,metadata,fingerprint,atomic
from asmr import publication as pub


def payload():
 scenes=[]
 for i in range(12):
  scenes.append(dict(label=f'Satisfying cutting variation {i+1}',material=['soap','sand','clay','slime'][i%4],
   palette=['candy','ocean','sunset','jewel'][i%4],shape=['bar','tapered','stepped'][i%3],
   pattern=['rainbow','solid','layered','striped'][i%4],cuts=8+i%3))
 meta=dict(title='Colorful Material Cutting ASMR for Quiet Moments',
  description='Watch colorful animated materials sliced into neat pieces, with crisp cuts and soft squishes across a changing palette.',
  tags=['cutting asmr','soap cutting','sand cutting','satisfying animation','no talking'])
 short=copy.deepcopy(meta);short['title']='Quick Colorful Cutting ASMR in Three Calm Scenes'
 return dict(idea='A coherent journey from bright crisp rainbow bars to soft ocean and jewel slices.',video=copy.deepcopy(meta),shorts=short,scenes=scenes,short_scenes=[0,1,3])

def plan():return finish(payload(),'asmr-unit',270,42)


class PlanningTests(unittest.TestCase):
 def test_model_uses_explicit_grammar_and_rejects_incomplete_output(self):
  from asmr.model import ask
  backend=Mock();backend.tokenize.return_value=[1]
  backend.create_chat_completion.return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload())}}]}
  grammar=Mock();module=types.SimpleNamespace(LlamaGrammar=grammar)
  with patch.dict('sys.modules',{'llama_cpp':module}),patch('lyrics_cpu.load_model',return_value=backend):
   self.assertEqual(ask('Make an episode',{},42),payload())
   call=backend.create_chat_completion.call_args.kwargs
   self.assertIs(call['grammar'],grammar.from_string.return_value)
   self.assertNotIn('response_format',call)
   backend.create_chat_completion.return_value['choices'][0]['finish_reason']='length'
   with self.assertRaisesRegex(ValueError,'incomplete'):ask('Make an episode',{},42)
 def test_invalid_model_candidate_is_saved_and_retried_with_specific_field(self):
  bad=payload();bad['scenes'][0].pop('cuts')
  with tempfile.TemporaryDirectory() as d:
   ask=Mock(side_effect=[bad,payload()])
   p=generate(d,'asmr-retry',270,[],ask)
   self.assertEqual(p['run_id'],'asmr-retry')
   self.assertIn('cuts',ask.call_args.args[0])
   self.assertEqual(ask.call_count,2)
 def test_full_and_short_have_accurate_separate_chapters(self):
  p=plan()
  self.assertEqual(p['seconds'],270)
  self.assertEqual(p['scenes'][-1]['start']+p['scenes'][-1]['seconds'],270)
  long=metadata(p,'video')['description'];short=metadata(p,'shorts')['description']
  self.assertIn('00:00',long);self.assertIn('04:07',long)
  self.assertIn('00:10',short);self.assertIn('00:20',short);self.assertNotIn('04:07',short)
  self.assertIn('synthesized',long)
 def test_render_controls_and_metadata_fidelity_are_validated(self):
  p=plan();p['video']['title']='Impossible Soap Cure ASMR for Everyone'
  with self.assertRaises(ValueError):validate_plan(p)
  p=plan();p['short_scenes']=[1,1,2]
  with self.assertRaises(Exception):validate_plan(p)
  p=plan();p['scenes'][1]=dict(p['scenes'][0],index=1,start=22.5)
  p['fingerprint']=fingerprint(p)
  with self.assertRaisesRegex(ValueError,'distinct'):validate_plan(p)
 def test_short_cannot_promise_a_material_outside_its_selected_scenes(self):
  p=plan();p['short_scenes']=[0,4,8];p['shorts']['title']='Soft Slime Cutting ASMR in Pastel Colors'
  with self.assertRaisesRegex(ValueError,'absent'):validate_plan(p)
 def test_new_generation_rejects_duplicate_even_with_a_new_seed(self):
  first=plan();history=[dict(title=first['video']['title'],fingerprint=first['fingerprint'])]
  with tempfile.TemporaryDirectory() as d:
   ask=Mock(return_value=payload())
   with self.assertRaisesRegex(ValueError,'Duplicate'):generate(d,'asmr-second',270,history,ask)
   self.assertEqual(ask.call_count,3)
 def test_resume_does_not_call_model_and_changed_request_stops(self):
  with tempfile.TemporaryDirectory() as d:
   atomic(Path(d)/'plan.json',plan());ask=Mock(side_effect=AssertionError('model called'))
   self.assertEqual(generate(d,'asmr-unit',270,[],ask),plan())
   with self.assertRaisesRegex(ValueError,'differs'):generate(d,'asmr-unit',240,[],ask)
   ask.assert_not_called()

class GeometryTests(unittest.TestCase):
 def test_all_materials_render_distinct_pixels_and_valid_cut_clock(self):
  from asmr import geometry as g
  images=[]
  for i,scene in enumerate(plan()['scenes'][:4]):
   g.configure(scene,supersample=1)
   for k in range(g.CUTS):
    self.assertAlmostEqual(g.knife_state(g.t_bottom(k))[1],g.YBOT)
    self.assertIsNone(g.slice_state(k,g.t_detach(k)-.001))
    self.assertLess(g.t_land(k),g.TOTAL)
   images.append(np.array(g.render(4)))
  self.assertTrue(all(not np.array_equal(images[0],x) for x in images[1:]))
 def test_material_sounds_are_stereo_bounded_and_not_identical(self):
  from asmr import geometry as g
  from scipy.io import wavfile
  with tempfile.TemporaryDirectory() as d:
   sounds=[]
   for i,s in enumerate(plan()['scenes'][:4]):
    g.configure(s,supersample=1);p=Path(d)/f'{i}.wav';g.build_audio(p)
    rate,pcm=wavfile.read(p)
    self.assertEqual((rate,pcm.shape[1]),(44100,2))
    self.assertLessEqual(np.max(np.abs(pcm.astype(float))),32767)
    self.assertGreater(np.sqrt(np.mean(pcm.astype(float)**2)),20)
    sounds.append(pcm)
   self.assertTrue(all(not np.array_equal(sounds[0],x) for x in sounds[1:]))

@patch.dict(os.environ,{'ASMR_PUBLISH_ENABLED':'false','ASMR_FACEBOOK_ENABLED':'true','ASMR_CLEANUP_ENABLED':'true','ASMR_DRIVE_BACKUP':'false'})
class DisabledPublicationTests(unittest.TestCase):
 def test_testing_never_instantiates_cloud_clients_or_deletes_media(self):
  with patch.object(pub,'ASMRStore',side_effect=AssertionError('cloud access')):
   for function in (pub.backup,pub.publish_youtube,pub.publish_facebook,pub.cleanup):
    self.assertEqual(function(Path('/unused'),plan()),{'disabled':True})
   self.assertFalse(pub.preflight()['publish'])
 def test_global_legacy_flags_cannot_enable_asmr_publication(self):
  with patch.dict(os.environ,{'PUBLISH_ENABLED':'true','FACEBOOK_PUBLISH_ENABLED':'true'}):
   self.assertFalse(pub.publish_enabled())

class DurablePublicationTests(unittest.TestCase):
 def test_missing_remote_completed_backup_stops_reuse(self):
  from asmr.render import product_identity
  p=plan();store=Mock();store.verified.return_value=False
  store.load.return_value=dict(identity=product_identity(p),facebook_required=False,backup_complete=True,
   media=[dict(id='missing',key='episode/video',size=4,md5='checksum')])
  with patch.dict(os.environ,{'ASMR_DRIVE_BACKUP':'true','ASMR_FACEBOOK_ENABLED':'false'}),patch.object(pub,'validate_products'):
   with self.assertRaisesRegex(ValueError,'changed or disappeared'):pub.backup('/unused',p,store)
  store.upload.assert_not_called()
 def test_backup_not_complete_until_recovery_metadata_is_saved(self):
  from asmr.render import product_identity
  p=plan();store=Mock();state=dict(identity=product_identity(p),facebook_required=False,media=[])
  store.load.return_value=state;store.upload.return_value={'id':'media'}
  def save(key,value):
   if key.endswith('/media.json'):raise RuntimeError('Simulated essential metadata failure')
  store.save.side_effect=save
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'short').mkdir()
   for name in ('video.mp4','thumbnail.jpg','short/video.mp4','short/thumbnail.jpg'):(root/name).write_bytes(b'fake')
   atomic(root/'media.json',{})
   with patch.dict(os.environ,{'ASMR_DRIVE_BACKUP':'true','ASMR_FACEBOOK_ENABLED':'false'}),patch.object(pub,'validate_products'):
    with self.assertRaisesRegex(RuntimeError,'essential'):pub.backup(root,p,store)
   self.assertFalse(state.get('backup_complete'))
 def test_partial_backup_resumes_remaining_files(self):
  p=plan();store=Mock()
  from asmr.render import product_identity,file_hash
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'short').mkdir();(root/'scenes').mkdir()
   for name in ('video.mp4','thumbnail.jpg','short/video.mp4','short/thumbnail.jpg'):(root/name).write_bytes(name.encode())
   atomic(root/'media.json',{})
   state=dict(identity=product_identity(p),run_id=p['run_id'],plan=p,youtube={},facebook={},deleted=[],facebook_required=False,
    media=[dict(name='video.mp4',sha256=file_hash(root/'video.mp4'),id='already',key='old',size=9,md5='existing')])
   store.load.return_value=state;store.upload.return_value={'id':'next'}
   with patch.dict(os.environ,{'ASMR_DRIVE_BACKUP':'true','ASMR_PUBLISH_ENABLED':'false','ASMR_FACEBOOK_ENABLED':'false'}),patch.object(pub,'validate_products'):
    result=pub.backup(root,p,store)
   self.assertEqual(store.upload.call_count,3)
   self.assertTrue(result['backup_complete'])
 def test_cleanup_requires_both_public_uploads(self):
  p=plan();store=Mock()
  from asmr.render import product_identity
  store.load.return_value=dict(identity=product_identity(p),backup_complete=True,youtube={'video':{'phase':'published','video_id':'long'}})
  client=Mock();client.videos().list().execute.return_value={'items':[{'id':'long'}]}
  with patch.dict(os.environ,{'ASMR_PUBLISH_ENABLED':'true','ASMR_CLEANUP_ENABLED':'true','ASMR_FACEBOOK_ENABLED':'false','EXPECTED_CHANNEL_ID':'channel'}),\
   patch.object(pub,'preflight'),patch.object(pub,'ASMRStore',return_value=store),patch('pipeline.youtube_client',return_value=client),\
   patch('upload_settings.verified_phase',return_value='published'):
   store.load.return_value['youtube']['video']['upload_body']={}
   with self.assertRaisesRegex(ValueError,'Both'):pub.cleanup('/unused',p)
  store.client.files().delete.assert_not_called()
 def test_corrupt_or_outside_manifest_is_rejected_before_any_deletion(self):
  p=plan();store=Mock()
  from asmr.render import product_identity
  yt={k:dict(phase='published',video_id=k,upload_body={}) for k in ('video','shorts')}
  state=dict(identity=product_identity(p),backup_complete=True,youtube=yt,facebook_required=False,deleted=[],
   media=[dict(id='one',name='video.mp4',key=f"episodes/{p['run_id']}/video.mp4"),dict(id='two',name='../../personal.mp4',key='outside')])
  store.load.return_value=state;client=Mock()
  client.videos().list().execute.side_effect=[{'items':[{'id':k}]} for k in ('video','shorts')]
  with patch.dict(os.environ,{'ASMR_PUBLISH_ENABLED':'true','ASMR_CLEANUP_ENABLED':'true','ASMR_FACEBOOK_ENABLED':'false','EXPECTED_CHANNEL_ID':'channel'}),\
   patch.object(pub,'preflight'),patch.object(pub,'ASMRStore',return_value=store),patch('pipeline.youtube_client',return_value=client),\
   patch('upload_settings.verified_phase',return_value='published'):
   with self.assertRaisesRegex(ValueError,'Unsafe'):pub.cleanup('/unused',p)
  store.client.files().delete.assert_not_called()
 def test_successful_cleanup_checks_exact_file_then_checkpoints_idempotently(self):
  from asmr.render import product_identity
  import hashlib
  p=plan();store=Mock();store.folder='asmr-owned'
  yt={k:dict(phase='published',video_id=k,upload_body={}) for k in ('video','shorts')}
  key=f"episodes/{p['run_id']}/video.mp4"
  entry=dict(id='media-id',name='video.mp4',key=key,size=42,md5='expected')
  state=dict(identity=product_identity(p),backup_complete=True,youtube=yt,facebook_required=False,deleted=[],media=[entry])
  store.load.return_value=state
  store.client.files().get().execute.return_value=dict(id='media-id',name=key.replace('/','__'),parents=['asmr-owned'],
   appProperties={'workflow_key':hashlib.sha256(key.encode()).hexdigest()},size='42',md5Checksum='expected',mimeType='video/mp4')
  client=Mock();client.videos().list().execute.side_effect=[{'items':[{'id':k}]} for k in ('video','shorts','video','shorts')]
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ASMR_PUBLISH_ENABLED':'true','ASMR_CLEANUP_ENABLED':'true','ASMR_FACEBOOK_ENABLED':'false','EXPECTED_CHANNEL_ID':'channel'}),\
   patch.object(pub,'preflight'),patch.object(pub,'ASMRStore',return_value=store),patch('pipeline.youtube_client',return_value=client),\
   patch('upload_settings.verified_phase',return_value='published'):
   pub.cleanup(d,p);pub.cleanup(d,p)
  store.client.files().delete.assert_called_once_with(fileId='media-id')
  self.assertEqual(state['deleted'],['media-id']);self.assertTrue(state['cleanup_complete'])

 def test_preview_history_reserves_identity_without_drive(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ASMR_PUBLISH_ENABLED':'false','ASMR_DRIVE_BACKUP':'false'}):
   previous=os.getcwd();os.chdir(d)
   try:
    pub.reserve(plan());pub.reserve(plan())
    self.assertEqual(len(pub.load_history()),1)
    changed=plan();changed['fingerprint']='changed'
    with self.assertRaisesRegex(ValueError,'reserved'):pub.reserve(changed)
   finally:os.chdir(previous)

if __name__=='__main__':unittest.main()
