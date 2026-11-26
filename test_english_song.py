import copy
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
from asmr.plan import atomic,digest
from english_song import writer as w,publication as pub,media

def payload():
 sections={
  'verse1':['Your coffee cooled beside the window','The morning train had come and gone','I folded up the note you left me','And kept the hallway light switched on'],
  'prechorus':['I thought the quiet meant forgetting','But every room still knows your name'],
  'chorus':['You left a little light behind','A patient glow I could not see','I do not need to turn back time','To keep the good you gave to me'],
  'verse2':['I walked the long way past the station','The bakery was closing for the night','I bought two rolls from old affection','Then shared one underneath the streetlight'],
  'bridge':['Perhaps the door was never broken','Perhaps we asked too much of rain','I learned to leave a kindness open','Without inviting back the pain'],
  'outro':['The kettle hums into the morning','I let the daylight find its place']}
 return dict(title='The Light You Left Behind',description='An original English soft-pop song about noticing the small kindnesses that survive a farewell, moving from a quiet room toward a gentler way to begin again.',
  story='A person finds an old note in a quiet room, walks past a station, shares a spare roll and finally welcomes morning without denying the loss.',
  production='Intimate piano and acoustic guitar, warm bass, restrained brushed drums and a wider string-backed final chorus.',bpm=86,key='A minor',
  tags=['English song','emotional pop','soft pop','original music','heartbreak song'],sections=sections,
  visuals=[dict(label=f'A quiet light at moment {i+1}',prompt='Cinematic landscape: '+['a warm hallway lamp','an empty railway platform','a closed bakery doorway','a quiet rain-streaked window','a folded paper note on a table','sunrise across a small kitchen'][i]+', soft amber reflections, gentle dawn blue, emotionally restrained soft-pop artwork, realistic materials, no writing or people.') for i in range(6)])

def review():return dict(scores={k:4 for k in ('english','emotional_arc','hook','singability','imagery')},issues=[])

def song():
 p=payload();lyrics=w.render_lyrics(p['sections'])
 return dict(p,format=w.VERSION,run_id='english-song-test',request='Original emotional pop / soft-pop',language='en',duration=210,vocal_gender='female',lyrics=lyrics,lyrics_sha256=hashlib.sha256(lyrics.encode()).hexdigest(),review=review(),prompt='English emotional soft-pop, mature female vocals, 86 BPM, A minor, intimate piano and expressive guitar with a short natural ending.')

class EnglishWritingTests(unittest.TestCase):
 def test_active_workflow_is_singing_and_moviepy_with_preview_gates(self):
  import yaml
  workflow=yaml.safe_load(Path('.github/workflows/music.yml').read_text());jobs=workflow['jobs']
  self.assertEqual(jobs['images']['strategy']['matrix']['index'],list(range(6)))
  self.assertEqual(jobs['music']['env']['REFERENCE_AUDIO_PATH'],'')
  self.assertEqual(set(jobs['render']['needs']),{'lyrics','music','images'})
  self.assertIn('requirements-song-video.txt','\n'.join(s.get('run','') for s in jobs['render']['steps']))
  self.assertIn('vars.ENGLISH_SONG_PUBLISH_ENABLED',jobs['publication']['if'])
  self.assertNotIn('vars.PUBLISH_ENABLED',str(workflow));self.assertNotIn('Kokoro',str(workflow))
 def test_critic_grammar_has_valid_identifiers_and_optional_issue_array(self):
  import re
  grammar=w.grammar(w.review_schema())
  for line in grammar.splitlines():self.assertRegex(line,r'^[A-Za-z0-9-]+ ::=')
  self.assertIn('emotional_arc',grammar);self.assertNotIn('root-scores-emotional_arc ::=',grammar)
  self.assertIn('root-issues ::= "[" ws (string',grammar)
 def test_natural_sections_are_accepted_and_exact_chorus_is_repeated(self):
  p=w.validate_song(song());text=p['lyrics']
  self.assertEqual(text.count('\n'.join(p['sections']['chorus'])),3)
  self.assertNotIn('dudi',text.lower());self.assertEqual(p['language'],'en')
 def test_non_english_filler_unreviewed_and_changed_lyrics_fail(self):
  for edit in ('script','filler','review','changed'):
   p=song()
   if edit=='script':p['sections']['verse1'][0]='यह हिंदी गाना अच्छा है'
   if edit=='filler':p['sections']['verse2'][0]=p['sections']['verse1'][0]
   if edit=='review':p['review']['scores']['singability']=2
   if edit=='changed':p['lyrics']+='\nA different line was secretly inserted'
   with self.assertRaises(ValueError):w.validate_song(p)
 def test_model_critique_forces_revision_before_acceptance(self):
  bad=review();bad['issues']=['Verse two repeats the opening instead of advancing the story'];bad['scores']['emotional_arc']=2
  ask=Mock(side_effect=[payload(),bad,payload(),review()])
  with tempfile.TemporaryDirectory() as d:
   accepted=w.write(d,'english-song-new',model=ask)
   self.assertIn('advancing the story',ask.call_args_list[2].args[0])
   self.assertEqual(accepted['review'],review());self.assertEqual(ask.call_count,4)
   resumed=w.write(d,'english-song-new',model=Mock(side_effect=AssertionError('rewritten')))
   self.assertEqual(accepted,resumed)
 def test_duplicate_reserved_song_is_not_sent_to_music(self):
  p=song();history=[dict(run_id='older',title=p['title'],lyrics_sha256=p['lyrics_sha256'],chorus=p['sections']['chorus'])]
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'three attempts'):w.write(d,'english-song-second',history=history,model=Mock(return_value=payload()))

class EnglishMusicTests(unittest.TestCase):
 def test_english_reaches_actual_ace_step_parameter_boundary(self):
  import music_cpu
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ):
   root=Path(d);raw=root/'native.wav';raw.write_bytes(b'native-audio-fixture')
   torch=Mock();torch.inference_mode.return_value=nullcontext()
   handler=Mock();handler.initialize_service.return_value=('ok',True);handler.device='cpu'
   params=Mock();config=Mock();infer=Mock(return_value=types.SimpleNamespace(success=True,audios=[dict(path=str(raw))]))
   with patch.object(music_cpu,'checkpoints'),patch.object(music_cpu,'runtime',return_value=(torch,Mock(return_value=handler),params,config,infer)),patch.object(music_cpu,'generation_progress',return_value=nullcontext()),patch('pipeline.duration',return_value=210):
    music_cpu.synthesize(dict(song(),_segment=True),root/'song.wav',root/'source',root/'weights')
   self.assertEqual(params.call_args.kwargs['vocal_language'],'en')
   self.assertEqual(params.call_args.kwargs['lyrics'],song()['lyrics']);self.assertFalse(params.call_args.kwargs['instrumental'])
 def test_cinematic_image_prompt_does_not_reintroduce_nursery_style(self):
  import image_cpu
  image=Image.new('RGB',(256,256),(80,90,100));pipeline=Mock(return_value=types.SimpleNamespace(images=[image],nsfw_content_detected=[False]))
  torch=Mock();torch.Generator.return_value.manual_seed.return_value=object()
  with tempfile.TemporaryDirectory() as d,patch.object(image_cpu,'_pipeline',pipeline),patch.dict('sys.modules',torch=torch,diffusers=Mock()):
   image_cpu.generate('A quiet adult music landscape',Path(d)/'image.png',seed=1,width=256,height=256,style='cinematic')
  call=pipeline.call_args.kwargs
  self.assertNotIn('child-friendly',call['prompt']);self.assertNotIn('photorealistic',call['negative_prompt'])
  self.assertIn('cartoon',call['negative_prompt'])

class EnglishMoviePyTests(unittest.TestCase):
 def test_dissolves_move_without_black_edges_and_preserve_timeline(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for i,color in enumerate([(220,30,20),(20,220,30),(25,30,220)]):
    p=Path(d)/f'{i}.png';Image.new('RGB',(320,180),color).save(p);paths.append(p)
   clip,starts,parts=media.cinematic_timeline(paths,9,size=(320,180))
   try:
    self.assertEqual(clip.duration,9);self.assertEqual(clip.get_frame(8.98).shape,(180,320,3))
    blend=clip.get_frame(starts[1]+.3)
    self.assertGreater(blend[90,160,0],30);self.assertGreater(blend[90,160,1],30)
    self.assertGreater(clip.get_frame(.1)[0,0].max(),20)
   finally:
    clip.close()
    for p in parts:p.close()

class EnglishPublicationTests(unittest.TestCase):
 def test_successful_cleanup_checks_exact_id_size_hash_and_is_idempotent(self):
  p=song();store=Mock();store.folder='owned-english';key=pub.prefix(p)+'/song.wav'
  item=dict(name='song.wav',key=key,id='owned-audio',size=100,md5='checked')
  state=dict(identity=media.identity(p),backup_complete=True,youtube=dict(phase='published',video_id='published-id',thumbnail_uploaded=True,upload_body={}),facebook_required=False,media=[item],deleted=[])
  store.load.return_value=state
  store.client.files().get().execute.return_value=dict(id='owned-audio',name=key.replace('/','__'),parents=['owned-english'],mimeType='audio/wav',appProperties={'workflow_key':hashlib.sha256(key.encode()).hexdigest()},size='100',md5Checksum='checked')
  client=Mock();client.videos().list().execute.return_value={'items':[{'id':'published-id'}]}
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ENGLISH_SONG_PUBLISH_ENABLED':'true','ENGLISH_SONG_CLEANUP_ENABLED':'true','EXPECTED_CHANNEL_ID':'channel'}),patch.object(pub,'preflight'),patch.object(pub,'SongStore',return_value=store),patch('pipeline.youtube_client',return_value=client),patch('upload_settings.verified_phase',return_value='published'):
   pub.cleanup(d,p);pub.cleanup(d,p)
  store.client.files().delete.assert_called_once_with(fileId='owned-audio');store.check_private.assert_called_once_with('owned-audio')
  self.assertTrue(state['cleanup_complete']);self.assertEqual(state['deleted'],['owned-audio'])
 def test_saved_facebook_requirement_cannot_be_disabled_to_bypass_cleanup(self):
  p=song();store=Mock();store.load.return_value=dict(identity=media.identity(p),backup_complete=True,youtube=dict(phase='published',video_id='id',thumbnail_uploaded=True,upload_body={}),facebook_required=True,facebook={'video_id':'fb-id'},media=[],deleted=[])
  client=Mock();client.videos().list().execute.return_value={'items':[{'id':'id'}]}
  with patch.dict(os.environ,{'ENGLISH_SONG_PUBLISH_ENABLED':'true','ENGLISH_SONG_CLEANUP_ENABLED':'true','ENGLISH_SONG_FACEBOOK_ENABLED':'false'}),patch.object(pub,'preflight'),patch.object(pub,'required',return_value='configured'),patch.object(pub,'SongStore',return_value=store),patch('pipeline.youtube_client',return_value=client),patch('upload_settings.verified_phase',return_value='published'),patch('facebook_publish.PAGE_ID','placeholder'),patch('facebook_publish.Facebook'),patch('facebook_publish.verify_remote',return_value=False):
   with self.assertRaisesRegex(ValueError,'Facebook'):pub.cleanup('/unused',p)
  store.client.files().delete.assert_not_called()
 @patch.dict(os.environ,{'ENGLISH_SONG_PUBLISH_ENABLED':'false','ENGLISH_SONG_DRIVE_BACKUP':'false','ENGLISH_SONG_CLEANUP_ENABLED':'true','PUBLISH_ENABLED':'true'})
 def test_preview_cannot_publish_or_delete_even_if_legacy_flag_is_on(self):
  with patch.object(pub,'SongStore',side_effect=AssertionError('cloud client')):
   for fn in (pub.backup,pub.publish,pub.cleanup):self.assertEqual(fn('/unused',song()),{'disabled':True})
 def test_cleanup_checks_publication_and_validates_whole_manifest_before_delete(self):
  p=song();store=Mock();store.load.return_value=dict(identity=media.identity(p),backup_complete=True,youtube=dict(phase='published',video_id='id',thumbnail_uploaded=True,upload_body={}),facebook_required=False,
   media=[dict(name='song.wav',key=pub.prefix(p)+'/song.wav',id='safe'),dict(name='history.json',key=pub.prefix(p)+'/history.json',id='unsafe')],deleted=[])
  client=Mock();client.videos().list().execute.return_value={'items':[{'id':'id'}]}
  with patch.dict(os.environ,{'ENGLISH_SONG_PUBLISH_ENABLED':'true','ENGLISH_SONG_CLEANUP_ENABLED':'true','EXPECTED_CHANNEL_ID':'channel'}),patch.object(pub,'preflight'),patch.object(pub,'SongStore',return_value=store),patch('pipeline.youtube_client',return_value=client),patch('upload_settings.verified_phase',return_value='published'):
   with self.assertRaisesRegex(ValueError,'Unsafe'):pub.cleanup('/unused',p)
  store.client.files().delete.assert_not_called()
 def test_essential_backup_failure_never_marks_media_complete(self):
  p=song();store=Mock();state=dict(identity=media.identity(p),facebook_required=False,media=[]);store.load.return_value=state;store.upload.return_value={'id':'temporary'}
  def save(key,value):
   if key.endswith('/media.json'):raise RuntimeError('essential failure')
  store.save.side_effect=save
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for name in pub.files():
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'media')
   for name in pub.essentials():atomic(root/name,{})
   with patch.dict(os.environ,{'ENGLISH_SONG_DRIVE_BACKUP':'true','ENGLISH_SONG_PUBLISH_ENABLED':'false','ENGLISH_SONG_FACEBOOK_ENABLED':'false'}),patch.object(pub,'verify_products'):
    with self.assertRaisesRegex(RuntimeError,'essential'):pub.backup(root,p,store)
   self.assertFalse(state.get('backup_complete'))
