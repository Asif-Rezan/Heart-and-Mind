"""Regression: resumed workers must not overwrite another shard's new media."""
import json
from pathlib import Path
import tempfile
import unittest
import yaml
from story_image_artifacts import copy_owned,restore_images
from story_writer import save_json
from story_restore import restore_artifacts


class OwnedImageArtifacts(unittest.TestCase):
    def make_legacy(self,base,shard):
        root=base/f'story-images-123-{shard}'/'story-test'
        root.mkdir(parents=True)
        # Legacy archives contain a full snapshot, including another worker's files.
        for i in (0,1):
            save_json(root/f'image-manifest-{i:02d}.json',{str(i):dict(seed=shard)})
            (root/f'scene-{i:03d}-source.png').write_bytes(f'image-{shard}-{i}'.encode())
            path=root/'story-motion';path.mkdir(exist_ok=True)
            (path/f'clip-{i:03d}.mp4').write_bytes(f'clip-{shard}-{i}'.encode())
            save_json(path/f'clip-{i:03d}.json',dict(owner=shard))
        (root/'thumbnail-source.png').write_bytes(f'thumb-{shard}'.encode())
        return root

    def test_pack_excludes_restored_files_owned_by_another_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.make_legacy(root,1);target=root/'packed'
            copy_owned(source,target,1,2)
            self.assertTrue((target/'scene-001-source.png').exists())
            self.assertFalse((target/'scene-000-source.png').exists())
            self.assertFalse((target/'story-motion/clip-000.mp4').exists())
            self.assertFalse((target/'image-manifest-00.json').exists())
            self.assertFalse((target/'thumbnail-source.png').exists())

    def test_restore_legacy_overlapping_snapshots_chooses_owner_for_every_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source'
            for shard in (1,0):self.make_legacy(source,shard)
            # Also repair broad upstream snapshots, which contain stale media.
            old=source/'story-input-123'/'story-test';old.mkdir(parents=True)
            (old/'scene-000-source.png').write_bytes(b'old')
            restore_artifacts(source,root/'output','story-test')
            result=root/'output/story-test'
            for i in (0,1):
                self.assertEqual((result/f'scene-{i:03d}-source.png').read_bytes(),f'image-{i}-{i}'.encode())
                self.assertEqual((result/f'story-motion/clip-{i:03d}.mp4').read_bytes(),f'clip-{i}-{i}'.encode())
                self.assertEqual(json.loads((result/f'story-motion/clip-{i:03d}.json').read_text())['owner'],i)
            self.assertEqual((result/'thumbnail-source.png').read_bytes(),b'thumb-0')

    def test_workflow_isolates_downloads_and_packages_owned_results(self):
        jobs=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())['jobs']
        images=jobs['images']['steps']
        self.assertTrue(any('story_image_artifacts.py pack' in s.get('run','') for s in images))
        upload=next(s for s in images if s.get('uses')=='actions/upload-artifact@v4')
        self.assertEqual(upload['with']['path'],'image-artifact/')
        publish=jobs['publish']['steps']
        download=next(s for s in publish if 'story-images-' in s.get('with',{}).get('pattern',''))
        self.assertIs(download['with']['merge-multiple'],False)
        self.assertTrue(any('story_image_artifacts.py restore' in s.get('run','') for s in publish))

    def test_publication_recovery_can_assemble_without_a_preexisting_video(self):
        data=yaml.safe_load(Path('.github/workflows/publish-saved-story.yml').read_text())
        steps=data['jobs']['publish']['steps']
        video_download=next(s for s in steps if s.get('with',{}).get('name','').startswith('story-video-'))
        self.assertEqual(video_download['if'],'${{ !inputs.assemble }}')
        assemble=next(s for s in steps if '--stage render --prepared-clips' in s.get('run',''))
        self.assertEqual(assemble['if'],'inputs.assemble')
        self.assertFalse(any('--stage images' in s.get('run','') or '--stage voice' in s.get('run','') for s in steps))
