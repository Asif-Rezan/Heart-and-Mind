import copy
import unittest
from unittest.mock import patch
from episode_packaging import VERSION,source_identity,validate_package,generate_package,public_metadata


def fixture_package(song,anchor=0):
    from hindi import require_hindi
    import hashlib
    try:
        title = require_hindi(song['title'])[:65] + ' | हिंदी बालगीत'
    except ValueError:
        title = 'प्यारे दोस्तों का बगीचे में नाच ' + str(int(hashlib.sha256(song['title'].encode()).hexdigest()[:6],16))
    return dict(version=VERSION,source_sha256=source_identity(song),
        title_candidates=[title,'प्यारे पशु मित्रों के साथ नाच | हिंदी बालगीत','सपनों के बगीचे में खेल | बच्चों का गीत'],
        video=dict(title=title,description='नन्हे बच्चे और प्यारे पशु मित्र बगीचे में साथ खेलते और नाचते हैं। यह मौलिक हिंदी बालगीत एआई संगीत और चित्रों से बनाया गया है।',
            tags=['हिंदी बालगीत','बच्चों के गीत','नन्हे पशु मित्र','बगीचे का गीत','Heart and Mind']),
        shorts=dict(title='प्यारे पशु मित्रों का बगीचे में नाच | हिंदी बालगीत #Shorts',
            description='प्यारे पशु मित्रों और नन्हे बच्चों के साथ बगीचे में नाचिए और गाइए। यह मौलिक हिंदी बालगीत एआई संगीत और चित्रों से बना है।',
            tags=['हिंदी बालगीत','बच्चों के गीत','पशु मित्र','बगीचे में नाच','Shorts']),
        thumbnail=dict(scene_index=anchor,focus='The same smiling toddlers and baby animals share the scene prop with joyful expressions.'))


class EpisodePackagingTests(unittest.TestCase):
    def song(self):
        from test_prepare_original_lyrics import fixture_song
        return fixture_song()

    def test_generated_packaging_is_based_on_episode_facts_and_reused(self):
        song=self.song()
        with patch('rhyme_writer.request_json',return_value=fixture_package(song)) as model:
            package=generate_package(song)
        prompt=model.call_args.args[1]
        self.assertIn(song['story_summary'],prompt)
        self.assertIn(song['scenes'][0]['lyric'],prompt)
        self.assertIn('first 40 seconds',prompt)
        self.assertIn('No invented animals',prompt)
        song['packaging']=package
        self.assertEqual(public_metadata(song),package['video'])
        self.assertEqual(public_metadata(song,'shorts'),package['shorts'])
        model.assert_called_once()

    def test_different_story_generates_different_public_metadata(self):
        first=self.song();second=copy.deepcopy(first);second['title']='Tiny Turtles Discover a Stream'
        first['packaging']=fixture_package(first);second['packaging']=fixture_package(second)
        self.assertNotEqual(public_metadata(first),public_metadata(second))

    def test_stale_or_invalid_packages_never_reach_upload(self):
        song=self.song();package=fixture_package(song)
        for mutate in (lambda p:p.update(source_sha256='stale'),
                       lambda p:p['thumbnail'].update(scene_index=999),
                       lambda p:p['video'].update(tags=['spam']*6),
                       lambda p:p['video'].update(title='Not a candidate')):
            bad=copy.deepcopy(package);mutate(bad)
            with self.assertRaises(Exception):validate_package(bad,song)

    def test_invalid_semantic_output_retries_then_reports_safe_failure(self):
        from lyrics_cpu import StoryGenerationError
        song=self.song();bad=fixture_package(song)
        bad['video']['tags']=['spam']*6
        with patch('rhyme_writer.request_json',side_effect=[bad]+[{'video.tags':['spam']*6} for _ in range(3)]) as model:
            with patch('builtins.print') as log:
                with self.assertRaises(StoryGenerationError):generate_package(song)
        self.assertEqual(model.call_count,4)
        retries=[c.args[0] for c in log.call_args_list if 'episode packaging field repair' in c.args[0]]
        self.assertEqual(len(retries),4)
        self.assertIn('minItems',retries[0])

    def test_fixable_slips_are_repaired_without_another_model_call(self):
        song=self.song();package=fixture_package(song)
        package['video']['title']='Not one of the candidates at all'
        package['video']['tags']=['Kids Song','kids song']+['x'*39+str(i) for i in range(13)]
        with patch('rhyme_writer.request_json',return_value=package) as model:
            result=generate_package(song)
        model.assert_called_once()
        self.assertIn(result['video']['title'],result['title_candidates'])
        tags=result['video']['tags']
        self.assertEqual(len({t.casefold() for t in tags}),len(tags))
        self.assertLessEqual(sum(len(t)+2 for t in tags),450)

    def test_title_used_before_switches_to_fresh_candidate(self):
        song=self.song();package=fixture_package(song)
        used=package['video']['title']
        with patch('rhyme_writer.request_json',return_value=package) as model:
            result=generate_package(song,[{'public_title':used}])
        model.assert_called_once()
        self.assertNotEqual(result['video']['title'],used)

    def test_stage_retry_uses_different_seeds(self):
        song=self.song()
        seeds=[]
        for offset in (0,1):
            with patch('rhyme_writer.request_json',return_value=fixture_package(song)) as model:
                generate_package(song,seed_offset=offset)
            seeds.append(model.call_args.args[2])
        self.assertNotEqual(seeds[0],seeds[1])


class PackageFieldRepairTests(unittest.TestCase):
    def song(self):
        from test_hindi import HindiPipelineTests
        return HindiPipelineTests().song()

    def test_initial_and_repair_schemas_constrain_hindi_but_keep_visuals_english(self):
        from episode_packaging import initial_schema, field_specs
        from hindi import PUBLIC_PATTERN
        song=self.song()
        native=initial_schema(song)['properties']
        for kind in ('video','shorts'):
            for field in ('title','description'):
                self.assertEqual(native[kind]['properties'][field]['pattern'],PUBLIC_PATTERN)
                self.assertEqual(field_specs(song)[kind+'.'+field]['pattern'],PUBLIC_PATTERN)
        self.assertNotIn('pattern',native['thumbnail']['properties']['focus'])

    def test_overlong_thumbnail_repairs_only_focus_and_preserves_public_text(self):
        song=self.song();bad=fixture_package(song)
        original=copy.deepcopy(bad)
        bad['thumbnail']['focus']='Very long visual instruction ' * 12
        focus='Smiling toddlers and baby animals clap beside the same opening flower bed.'
        with patch('rhyme_writer.request_json',side_effect=[bad,{'thumbnail.focus':focus}]) as model:
            result=generate_package(song)
        self.assertEqual(model.call_count,2)
        repair=model.call_args
        self.assertEqual(repair.args[0]['required'],['thumbnail.focus'])
        self.assertNotIn('verse_lyrics',repair.args[1])
        self.assertEqual(repair.kwargs['budget'],800)
        self.assertEqual(result['video']['title'],original['video']['title'])
        self.assertTrue(result['video']['description'].startswith(original['video']['description']))
        self.assertEqual(result['shorts'],original['shorts'])
        self.assertEqual(result['thumbnail']['focus'],focus)
        validate_package(result,song)

    def test_english_description_repairs_only_that_field_without_relaxing_hindi(self):
        song=self.song();bad=fixture_package(song)
        correct=bad['shorts']['description'];bad['shorts']['description']='Happy animal friends dance in the magical garden. This music and its illustrations are AI generated.'
        with patch('rhyme_writer.request_json',side_effect=[bad,{'shorts.description':correct}]) as model:
            result=generate_package(song)
        self.assertEqual(model.call_args.args[0]['required'],['shorts.description'])
        self.assertNotIn('verse_lyrics',model.call_args.args[1])
        self.assertEqual(result['shorts']['description'],correct)
        validate_package(result,song)

    def test_interruption_resumes_saved_package_without_full_regeneration(self):
        import tempfile
        from pathlib import Path
        from lyrics_cpu import StoryGenerationError
        song=self.song();bad=fixture_package(song)
        original=bad['video']['title']
        bad['thumbnail']['focus']='too long ' * 30
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'package-draft.json'
            with patch('rhyme_writer.request_json',side_effect=[bad,StoryGenerationError('interrupted')]):
                with self.assertRaises(StoryGenerationError):generate_package(song,draft_path=path)
            self.assertTrue(path.exists())
            with patch('rhyme_writer.request_json',return_value={'thumbnail.focus':'Same smiling toddlers and baby animals share the opening scene flower.'}) as model:
                result=generate_package(song,draft_path=path)
            model.assert_called_once()
            self.assertEqual(model.call_args.args[0]['required'],['thumbnail.focus'])
            self.assertEqual(result['video']['title'],original)
            validate_package(result,song)

    def test_compact_facts_keep_full_verses_and_short_opening_without_repeated_scene_prose(self):
        from episode_packaging import package_facts, candidate_scenes
        import json
        song=self.song();facts=package_facts(song)
        self.assertEqual(len(facts['opening']),8)
        self.assertEqual(len(facts['verse_lyrics']),20)
        old=dict(facts,scenes=[dict(index=s['index'],lyric=s['lyric'],action=s['prompt'][:180]) for s in candidate_scenes(song)])
        self.assertLess(len(json.dumps(facts,ensure_ascii=False)),len(json.dumps(old,ensure_ascii=False))*.7)
