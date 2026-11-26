"""Wan preview input/provenance guards and real post-processing; no fake inference claims."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
import wan_preview as wan

def plan():
 return dict(idea='A calm macro study of amber glass beads flowing across a dark ceramic surface.',
  title='Amber Glass Bead Flow ASMR | Gentle Cascades',
  description='A calm AI-generated macro study of amber glass beads flowing across a dark ceramic surface, with six quiet compositions and separate synthesized granular sound design.',
  tags=['asmr','glass beads','satisfying video','macro video','relaxing flow'],
  shots=[dict(label=f'Amber bead flow view {i+1}',sound='granules',prompt=f'Photorealistic macro cinematography, amber glass beads flowing slowly over a dark ceramic surface, soft warm light and shallow depth of field. Camera composition variation {i+1}, no hands or text.') for i in range(6)])

class WanPreviewTests(unittest.TestCase):
 def test_incomplete_and_duplicate_shot_plans_are_rejected(self):
  wan.validate_plan(plan())
  p=plan();p['shots'].pop()
  with self.assertRaises(Exception):wan.validate_plan(p)
  p=plan();p['shots'][1]=copy.deepcopy(p['shots'][0])
  with self.assertRaisesRegex(ValueError,'distinct'):wan.validate_plan(p)
 def test_frozen_frames_do_not_become_a_looped_thirty_second_video(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);frames=root/'frames';frames.mkdir()
   for i in range(41):Image.new('RGB',(288,512),(30,40,50)).save(frames/f'{i:03}.png')
   with self.assertRaisesRegex(ValueError,'frozen'):wan.export_frames(root)
   self.assertFalse((root/'video.mp4').exists())
 def test_real_frame_interpolation_exports_five_seconds_in_portrait(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);frames=root/'frames';frames.mkdir()
   for i in range(41):
    image=Image.new('RGB',(288,512),(25,35,45));draw=ImageDraw.Draw(image)
    draw.ellipse((10+i*4,180,70+i*4,240),fill=(230,160,60));image.save(frames/f'{i:03}.png')
   wan.export_frames(root)
   report=wan.probe(root/'video.mp4',5)
   self.assertEqual((report['width'],report['height'],report['fps']),(720,1280,24))
 def test_assembly_refuses_mismatched_model_clip_before_any_export(self):
  with tempfile.TemporaryDirectory() as d,patch.object(wan,'ROOT',Path(d)):
   wan.atomic(Path(d)/'plan.json',plan());folder=Path(d)/'shot-0';folder.mkdir()
   wan.atomic(folder/'receipt.json',dict(identity='different model or prompt',sha256='x',actual_generated_frames=41))
   with self.assertRaisesRegex(ValueError,'provenance'):wan.assemble()
   self.assertFalse((Path(d)/'video.mp4').exists())
