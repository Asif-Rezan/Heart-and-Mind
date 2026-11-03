import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lyric_quality import assess, vowel_weight, render_sections, SECTION_KEYS, section_schema, parse_sections
from test_song_generation import CORE, PACKAGE, response
from pipeline import make_song

GOOD = CORE['lyrics']
BAD = render_sections({key:['नई सुबह में फिर से जीना है']*count for key,count in SECTION_KEYS})


class LyricQualityTests(unittest.TestCase):
    def setUp(self):
        import lyric_quality
        self.real_review = lyric_quality.review
        self.reviewer = patch('lyric_quality.review', return_value={'passed':True, 'issues':[]})
        self.reviewer.start()
        self.addCleanup(self.reviewer.stop)

    def test_complete_romantic_song_has_balanced_written_phrases(self):
        report = assess(GOOD)
        self.assertTrue(report['passed'], report['issues'])
        self.assertEqual(report['word_count'], 189)
        self.assertEqual(len(report['sections']), 8)
        self.assertIn('require listening review', report['limitation'])

    def test_repeated_prose_and_changed_chorus_are_rejected(self):
        self.assertFalse(assess(BAD)['passed'])
        changed = GOOD.replace('तुम पास रहो तो शाम ठहर जाए', 'तुम साथ रहो तो रात सँवर जाए', 1)
        self.assertIn('All three chorus performances must use identical words', assess(changed)['issues'])

    def test_equal_word_counts_can_hide_overloaded_vowels(self):
        short = 'तुम अब इस घर चल कर रह लो'
        long = 'तुम्हारी कहानियों तुम्हारी कहानियों तुम्हारी कहानियों तुम्हारी कहानियों'
        self.assertEqual(len(short.split()), len(long.split()))
        self.assertGreater(vowel_weight(long)-vowel_weight(short), 20)
        altered = GOOD.replace(GOOD.splitlines()[1], long)
        self.assertTrue(any('vowel lengths' in issue for issue in assess(altered)['issues']))

    def test_bounded_revision_stops_before_packaging_or_synthesis(self):
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory)/'song-draft.json'
            with patch('lyrics_cpu.request_story', side_effect=[response(dict(CORE, lyrics=BAD))]+[response({'lyrics': BAD})]*3) as model:
                with self.assertRaisesRegex(ValueError, 'Lyrics need revision'):
                    make_song('2026-11-03', [], draft)
            self.assertEqual(model.call_count, 4)
            report = json.loads(draft.with_name('lyrics-quality.json').read_text())
            self.assertFalse(report['passed'])
            self.assertEqual(json.loads(draft.read_text())['lyrics'], BAD)
            # Resume the rejected draft: repair lyrics first, then create packaging.
            with patch('lyrics_cpu.request_story', side_effect=[response({'lyrics':GOOD}), response(PACKAGE)]) as model:
                song = make_song('2026-11-03', [], draft)
            self.assertEqual(model.call_count, 2)
            self.assertTrue(song['lyric_quality']['passed'])

    def test_semantic_failure_cannot_pass_on_balanced_counts_alone(self):
        critique = {'passed':False, 'issues':['Verse 2: imagery has no relationship meaning']}
        with patch('lyric_quality.review', side_effect=[critique, {'passed':True,'issues':[]}]) as reviewer:
            with patch('lyrics_cpu.request_story', side_effect=[response(CORE),response({'lyrics':GOOD}),response({'lyrics':GOOD}),response(PACKAGE)]) as model:
                song = make_song('2026-11-03', [])
        self.assertEqual(reviewer.call_count, 2)
        self.assertIn('imagery has no relationship meaning', model.call_args_list[2].args[1]['messages'][-1]['content'])
        self.assertTrue(song['lyric_quality']['semantic_review']['passed'])

    def test_critique_requires_all_criteria_and_no_reported_issues(self):
        # Exercise the real critic rather than the isolated integration mock.
        real_review = self.real_review
        from unittest.mock import Mock
        request = Mock(return_value=dict(coherent_relationship=True,natural_hindi=True,
            natural_rhyme=False,singable_phrasing=True,issues=['Chorus: rhyme is forced']))
        result = real_review(request, GOOD, 'romantic ballad', 86, 'female')
        self.assertFalse(result['passed'])
        self.assertIn('not-human', result['reviewer'])
        self.assertIn('do not rewrite', request.call_args.args[0])

    def test_tampered_saved_lyrics_stop_before_audio_inference(self):
        import prepare_music
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'output'/'saved'
            root.mkdir(parents=True)
            (root/'song.json').write_text(json.dumps(dict(CORE, **PACKAGE, lyrics=BAD, lyric_quality_version=2)))
            with patch('prepare_music.Path',side_effect=lambda value:Path(directory)/value), patch('prepare_music.generate') as synth:
                with self.assertRaisesRegex(ValueError, 'Saved lyrics failed'):
                    prepare_music.prepare('saved','music')
            synth.assert_not_called()

    def test_inline_historical_headings_keep_the_first_sung_line(self):
        inline = GOOD.replace(']\n', '] ')
        self.assertEqual(assess(inline)['word_count'], 189)
        self.assertTrue(assess(inline)['passed'])
        self.assertEqual(render_sections(parse_sections(inline)), GOOD)

    def test_schema_requires_four_chorus_lines_before_accepting_output(self):
        from jsonschema import Draft202012Validator, ValidationError
        sections = parse_sections(GOOD)
        Draft202012Validator(section_schema()).validate(sections)
        sections['chorus'] = sections['chorus'][:2]
        with self.assertRaises(ValidationError):
            Draft202012Validator(section_schema()).validate(sections)

    def test_failed_production_draft_recovers_with_structured_editor_output(self):
        broken = GOOD.replace(']\n', '] ')
        # Reproduce the real production two-line chorus (not an accepted song).
        lines = parse_sections(broken)
        lines['chorus'] = lines['chorus'][:2]
        broken = render_sections(lines).replace(']\n', '] ')
        self.assertFalse(assess(broken)['passed'])
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory)/'song-draft.json'
            draft.write_text(json.dumps(dict(CORE,lyrics=broken)))
            draft.with_name('lyrics-quality.json').write_text(json.dumps(dict(version=2,passed=False)))
            with patch('lyrics_cpu.request_story',side_effect=[response({'lyrics':GOOD}),response(PACKAGE)]) as model:
                song = make_song('2026-11-03',[],draft)
            self.assertEqual(model.call_count,2)
            self.assertEqual(song['lyrics'],GOOD)
            self.assertTrue(song['lyric_quality']['passed'])
            schema=model.call_args_list[0].args[1]['response_format']['json_schema']['schema']
            self.assertEqual(schema['properties']['lyrics']['type'],'object')

    def test_exact_bar_tempo_brief_and_repair_feedback_reach_editor(self):
        with patch('lyrics_cpu.request_story', side_effect=[response(dict(CORE, lyrics=BAD)),response({'lyrics':BAD}),response({'lyrics':GOOD}),response(PACKAGE)]) as model:
            song = make_song('2026-11-03', [])
        prompts = [call.args[1]['messages'][-1]['content'] for call in model.call_args_list]
        self.assertIn('BPM in 4/4', prompts[0])
        self.assertIn('Verses repeat filler', prompts[2])
        self.assertIn('match melody to Hindi word stress', song['prompt'])
        self.assertTrue(song['lyric_quality']['passed'])


if __name__ == '__main__':
    unittest.main()
