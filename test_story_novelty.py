import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from story_plan import prepare_outline, StoryValidationError
from test_story_parallel import outline_fixture


class OutlineNoveltyTests(unittest.TestCase):
    def test_duplicate_plot_retries_with_distinct_checkpoint_and_feedback(self):
        old=outline_fixture()
        fresh=copy.deepcopy(old)
        fresh.update(title='अलग कहानी',summary='A nurse repairs a broken clinic schedule during a storm and chooses to stay with an elderly patient.')
        history=[dict(run='old',title='पुरानी कहानी',summary=old['summary'])]
        with tempfile.TemporaryDirectory() as tmp,patch('story_plan.ask',side_effect=[old,fresh]) as ask:
            root=Path(tmp)
            prepare_outline(root,'new',history)
            self.assertEqual(json.loads((root/'story-draft.json').read_text())['outline'],fresh)
            self.assertEqual(ask.call_count,2)
            self.assertNotEqual(ask.call_args_list[0].kwargs['checkpoint'],ask.call_args_list[1].kwargs['checkpoint'])
            self.assertIn(old['summary'],ask.call_args.args[1])

    def test_duplicates_exhaust_before_chapters_or_draft_are_saved(self):
        old=outline_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch('story_plan.ask',return_value=old) as ask:
            root=Path(tmp)
            with self.assertRaises(StoryValidationError) as error:
                prepare_outline(root,'new',[dict(run='old',**old)])
            self.assertEqual(error.exception.code,'outline_novelty_exhausted')
            self.assertEqual(ask.call_count,3)
            self.assertFalse((root/'story-draft.json').exists())
            self.assertEqual(json.loads((root/'outline-novelty.json').read_text())['attempts'],3)

    def test_cached_duplicate_is_refused_without_rewriting_chapters(self):
        from story_writer import save_json
        old=outline_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch('story_plan.ask') as ask:
            root=Path(tmp)
            save_json(root/'story-draft.json',dict(run_id='new',outline=old))
            with self.assertRaises(StoryValidationError) as error:
                prepare_outline(root,'new',[dict(run='old',**old)])
            self.assertEqual(error.exception.code,'duplicate_outline_checkpoint')
            ask.assert_not_called()

    def test_current_run_reservation_is_not_treated_as_a_duplicate(self):
        old=outline_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch('story_plan.ask',return_value=old) as ask:
            prepare_outline(Path(tmp),'same',[dict(run='same',**old)])
            self.assertEqual(ask.call_count,1)
