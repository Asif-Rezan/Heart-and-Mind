import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from cartoon_seo import optimize,capitalize_title,select_package,add_chapters,VERSION
from test_cartoon import fixture


def story():
    song=fixture();song['story_summary']=song['description'];return song


def keywords():
    return dict(primary='teamwork cartoon',supporting=['animated adventure','working together','family story'],
        queries=['teamwork cartoon story','animated teamwork adventure'])


def package():
    evidence=story()['scenes'][0]['text']
    return dict(candidates=[dict(title=t,power_words=[p],story_evidence=evidence) for t,p in [
        ('The unexpected Map Mistake | A Teamwork Cartoon Adventure','UNEXPECTED'),
        ('A surprising Woodland Detour | Teamwork Cartoon','SURPRISING'),
        ('Their clever Plan for Getting Home | A Teamwork Cartoon','CLEVER')]],
        description='This teamwork cartoon follows Mira and Theo on a woodland adventure. A confusing sign makes them pause, '
            'listen to each other and decide how to find their way home together. Enjoy an animated family story about cooperation.',
        hashtags=['#FamilyCartoon','#Teamwork','#AnimatedStory'],chapters=[dict(scene_index=i,title=t) for i,t in [(0,'A confusing sign'),(4,'Checking the map'),(8,'Working together'),(12,'Finding the way home')]])


class CartoonSEOTests(unittest.TestCase):
    def test_live_research_is_bounded_and_metadata_resume_reuses_checkpoint(self):
        song=story();client=Mock()
        client.search.return_value.list.return_value.execute.return_value={'items':[{'id':{'videoId':'sample'},'snippet':{
            'title':'A teamwork adventure','description':'A story about cooperation'}}]}
        writer=Mock(side_effect=[keywords(),package()])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=optimize(root,song,client=client,writer=writer)
            self.assertEqual(client.search.return_value.list.call_count,2)
            self.assertEqual(writer.call_count,2)
            self.assertRegex(result['title'],r'UNEXPECTED|SURPRISING|CLEVER')
            self.assertIn('teamwork cartoon',result['title'].casefold())
            record=json.loads((root/'seo-draft.json').read_text())
            self.assertEqual(record['research'][0]['source'],'YouTube Data API search.list')
            self.assertIn('retrieved_at',record['research'][0])
            writer.reset_mock();client.reset_mock()
            optimize(root,result,client=client,writer=writer)
            writer.assert_not_called();client.search.assert_not_called()

    def test_api_failure_has_safe_story_fallback_without_invented_metrics(self):
        client=Mock();client.search.return_value.list.return_value.execute.side_effect=RuntimeError('secret token=never-log')
        with tempfile.TemporaryDirectory() as tmp:
            result=optimize(Path(tmp),story(),client=client,writer=Mock(side_effect=[keywords(),package()]))
            saved=(Path(tmp)/'seo-draft.json').read_text()
            self.assertNotIn('never-log',saved)
            self.assertIn('story-derived fallback',saved)
            self.assertNotIn('search_volume',saved)
            self.assertEqual(result['seo']['version'],VERSION)

    def test_power_word_is_capitalized_and_fabricated_evidence_is_rejected(self):
        p=package();s=story();primary=keywords()['primary']
        title=capitalize_title(p['candidates'][0],primary,s['scenes'][0]['text'])
        self.assertIn('UNEXPECTED',title);self.assertNotEqual(title,title.upper())
        bad=copy.deepcopy(p['candidates'][0]);bad['story_evidence']='A dragon appeared and destroyed the castle.'
        with self.assertRaises(ValueError):capitalize_title(bad,primary,s['scenes'][0]['text'])
        bad=copy.deepcopy(p['candidates'][0]);bad['title']='An unrelated viral mystery'
        with self.assertRaises(ValueError):capitalize_title(bad,primary,s['scenes'][0]['text'])

    def test_description_keywords_and_chapters_are_validated(self):
        s=story();p=package()
        for change in ('description','hashtags','chapters'):
            bad=copy.deepcopy(p)
            if change=='description':bad[change]='An unrelated video opening without its primary search phrase. '*5
            elif change=='hashtags':bad[change]=['#bad hashtag','#Teamwork']
            else:bad[change][1]['scene_index']=0
            with self.assertRaises(ValueError):select_package(bad,keywords(),s,[])

    def test_timed_chapters_are_idempotent_and_use_actual_scene_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            song=optimize(Path(tmp),story(),writer=Mock(side_effect=[keywords(),package()]))
            for i,scene in enumerate(song['scenes']):scene['start']=i*8.8
            add_chapters(song);first=song['description'];add_chapters(song)
            self.assertEqual(first,song['description'])
            self.assertIn('00:00 A confusing sign',first)
            self.assertIn('00:35 Checking the map',first)
            self.assertNotIn('00:20 Checking the map',first)

    def test_valid_candidates_are_usable_when_another_title_is_rejected(self):
        bad=package();bad['candidates'][0]['story_evidence']='Completely invented scene and dialogue.'
        writer=Mock(side_effect=[keywords(),bad])
        with tempfile.TemporaryDirectory() as tmp:
            result=optimize(Path(tmp),story(),writer=writer)
            self.assertEqual(writer.call_count,2)
            self.assertRegex(result['title'], r'SURPRISING|CLEVER')

    def test_exhausted_seo_attempts_resume_with_saved_story_metadata(self):
        bad = package()
        bad['description'] = 'An opening that misses the target keyword. ' * 5
        writer = Mock(side_effect=[keywords(), bad, {}, bad])
        song = story()
        song['seo_pending'] = True
        original = copy.deepcopy(song)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = optimize(root, song, writer=writer)
            self.assertEqual(writer.call_count, 4)
            self.assertEqual(result['title'], original['title'])
            self.assertTrue(result['description'].startswith(original['story_summary']))
            self.assertEqual(result['scenes'], original['scenes'])
            self.assertNotIn('seo_pending', result)
            description = result['description']
            add_chapters(result)
            self.assertEqual(result['description'], description)
            writer.reset_mock()
            self.assertEqual(optimize(root, result, writer=writer)['description'], description)
            writer.assert_not_called()
