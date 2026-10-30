"""Publishing and cleanup must have separate visible success/failure states."""
import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import yaml

from daily_story import publish_story
from story_cleanup import cleanup_published_story
from test_daily_story import example_story


class VisibleCleanupTests(unittest.TestCase):
    def test_publish_defers_media_deletion_to_job_but_local_default_still_cleans(self):
        for deferred in (True,False):
            with self.subTest(deferred=deferred),tempfile.TemporaryDirectory() as temporary:
                state=dict(song=example_story(),video_id='existing-video',phase='published',
                           upload_settings={'publish_at':None})
                store=Mock();store.load.side_effect=[state,[]]
                with patch('storage.Store',return_value=store),patch('story_publication.youtube_client'),patch('story_publication.publish'),patch('story_cleanup.cleanup') as clean:
                    publish_story(Path(temporary),example_story(),'story-test',defer_drive_cleanup=deferred)
                self.assertEqual(clean.call_count,0 if deferred else 1)
                self.assertEqual(bool(state.get('backup_cleanup_complete')),not deferred)
                self.assertEqual(json.loads((Path(temporary)/'publication.json').read_text())['phase'],'published')

    def test_standalone_success_marks_saved_publication_and_writes_small_report(self):
        state=dict(song=example_story(),video_id='existing-video',phase='published')
        store=Mock();store.load.return_value=state
        journal=dict(deleted=['temporary-media'],complete=True)
        with tempfile.TemporaryDirectory() as temporary,contextlib.chdir(temporary),patch('story_cleanup.cleanup',return_value=journal) as clean:
            result=cleanup_published_story(store,Mock(),'story-test')
            self.assertTrue(state['backup_cleanup_complete'])
            self.assertTrue(result['cleanup_complete'])
            self.assertEqual(result['deleted_media'],1)
            self.assertNotIn('temporary-media',Path('output/story-test/cleanup.json').read_text())
            store.save.assert_called_with('stories/runs/story-test/publication.json',state)
            # Even a completed cleanup is freshly verified by the underlying
            # idempotent cleanup helper when the job is retried.
            cleanup_published_story(store,Mock(),'story-test')
            self.assertEqual(clean.call_count,2)

    def test_wrong_identity_or_failed_cleanup_cannot_mark_success(self):
        store=Mock()
        state=dict(song=example_story(),video_id='video',phase='published')
        store.load.return_value=state
        with tempfile.TemporaryDirectory() as temporary,contextlib.chdir(temporary),patch('story_cleanup.cleanup',side_effect=RuntimeError('public HD check failed')):
            with self.assertRaises(RuntimeError):
                cleanup_published_story(store,Mock(),'story-test')
            self.assertNotIn('backup_cleanup_complete',state)
            store.save.assert_not_called()
            self.assertFalse(Path('output/story-test/cleanup.json').exists())
        state['song']['run_id']='another-story'
        with patch('story_cleanup.cleanup') as clean,self.assertRaisesRegex(RuntimeError,'exact published story'):
            cleanup_published_story(store,Mock(),'story-test')
        clean.assert_not_called()

    def test_main_and_recovery_graphs_have_a_dedicated_cleanup_after_publication(self):
        jobs=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())['jobs']
        self.assertEqual(jobs['cleanup']['name'],'Drive cleanup')
        self.assertIn('publish',jobs['cleanup']['needs'])
        self.assertIn('plan',jobs['cleanup']['needs'])
        self.assertEqual(jobs['cleanup']['if'],"vars.PUBLISH_ENABLED != 'false'")
        publish=[s['run'] for s in jobs['publish']['steps'] if s.get('name')=='Back up and publish on the existing Heart and Mind channel'][0]
        self.assertIn('--defer-drive-cleanup',publish)
        self.assertTrue(any('python -u story_cleanup.py' in s.get('run','') for s in jobs['cleanup']['steps']))
        recovery=yaml.safe_load(Path('.github/workflows/recover-story.yml').read_text())['jobs']
        self.assertEqual(recovery['cleanup']['needs'],'recover')
        self.assertEqual(recovery['cleanup']['name'],'Drive cleanup')


if __name__=='__main__':
    unittest.main()
