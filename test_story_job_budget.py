"""Prove the workflow's critical path overlaps independent work within 20 jobs."""
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
from PIL import Image
from story_video import generate_images
from story_writer import save_json
from test_short_story import short_story,timeline


class ParallelBudgetTests(unittest.TestCase):
    def test_every_possible_concurrent_generation_phase_fits_twenty_jobs(self):
        jobs=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())['jobs']
        def ancestors(name):
            needs=jobs[name].get('needs',[])
            if isinstance(needs,str):needs=[needs]
            return set(needs).union(*(ancestors(n) for n in needs))
        lineage={name:ancestors(name) for name in jobs}
        weights={name:min(job.get('strategy',{}).get('max-parallel',1),
            len(next(iter(job.get('strategy',{}).get('matrix',{'single':[0]}).values())))) for name,job in jobs.items()}
        maximum=0
        for n in range(1,len(jobs)+1):
            for subset in itertools.combinations(jobs,n):
                if any(a in lineage[b] or b in lineage[a] for a,b in itertools.combinations(subset,2)):
                    continue
                maximum=max(maximum,sum(weights[name] for name in subset))
        self.assertEqual(maximum,20)
        self.assertEqual(weights['images']+weights['music'],20)
        self.assertNotIn('music',lineage['images'])
        self.assertNotIn('images',lineage['mix'])

    def test_all_seventy_five_frames_render_once_as_their_images_become_ready(self):
        story=short_story()
        owners=[]
        def draw(prompt,path,**kwargs):
            Image.new('RGB',(64,36),'gold').save(path)
        def render(root,story,timing,**kwargs):
            self.assertEqual(kwargs['shards'],17)
            indices=kwargs['only_indices']
            self.assertEqual(len(indices),1)
            for index in indices:
                self.assertTrue((root/f'scene-{index:03d}-source.png').exists())
                self.assertEqual(index%17,kwargs['shard'])
                owners.append(index)
        with tempfile.TemporaryDirectory() as folder,patch('story_image_cpu.generate',side_effect=draw) as generator,patch('story_video.render_clips',side_effect=render):
            root=Path(folder);save_json(root/'timing.json',timeline(300))
            for shard in range(17):
                with patch.dict(os.environ,{'IMAGE_SHARD':str(shard),'IMAGE_SHARDS':'17'}):
                    generate_images(root,story,render_ready=True)
            self.assertEqual(sorted(owners),list(range(75)))
            self.assertEqual(len(set(owners)),75)
            self.assertEqual(generator.call_count,75+17+1)  # Frames, references, dedicated thumbnail.
            self.assertTrue((root/'thumbnail-source.png').exists())
