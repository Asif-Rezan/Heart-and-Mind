"""SEO stays story-specific, bounded, separate from speech, and uses Entertainment."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from story_packaging import prepare_packaging,clean_tags
from story_upload_settings import load_settings,upload_body
from test_short_story import short_story


class StoryPackagingTests(unittest.TestCase):
    def test_packaging_reads_final_script_once_without_rewriting_speech(self):
        story=short_story();original=copy.deepcopy(story['scenes']);script=story['lyrics']
        package=dict(title='एक चिट्ठी ने बदला फैसला | Emotional Hindi Story',
            description='यह कहानी एक दुकानदार की मुश्किल और उसके परिवार के भरोसे की है। '*6,
            tags=['चिट्ठी की कहानी','Chitthi ki kahani','Hindi Story','Emotional Hindi Story','Motivational Kahani',
                  'परिवार की कहानी','Family story','Heart and Mind'])
        with tempfile.TemporaryDirectory() as folder,patch('story_packaging.ask',return_value=package) as model:
            prepare_packaging(Path(folder),story)
            self.assertIn(script,model.call_args.args[1])
            self.assertEqual(story['scenes'],original)
            self.assertEqual(story['lyrics'],script)
            self.assertEqual(story['title'],package['title'])
            self.assertIn('काल्पनिक',story['description'])
            prepare_packaging(Path(folder),story)
            model.assert_called_once()

    def test_tags_deduplicate_and_respect_upload_budget(self):
        tags=clean_tags([' Hindi Story ','hindi story','#HindiStory']+[f'specific family conflict phrase {i}' for i in range(50)])
        self.assertEqual(tags[:2],['Hindi Story','HindiStory'])
        self.assertLessEqual(sum(len(t)+(2 if ' ' in t else 0)+1 for t in tags),480)
        with patch.dict('os.environ',{'VIDEO_CATEGORY_ID':'24'}):
            body=upload_body(short_story(),'description',tags,load_settings())
        self.assertEqual(body['snippet']['categoryId'],'24')
        self.assertNotIn('education',str(body).lower())
        self.assertNotIn('academic',str(body).lower())
        self.assertNotIn('bangladesh',str(body).lower())
        with patch.dict('os.environ',{'VIDEO_CATEGORY_ID':'27'}),self.assertRaisesRegex(ValueError,'Entertainment'):
            load_settings()
