import unittest
import io
from contextlib import redirect_stdout
from validate_publication_config import REQUIRED, validate


class PublicationConfigTests(unittest.TestCase):
    def test_preview_needs_no_publication_credentials(self):
        validate({})
        validate({'PUBLISH_ENABLED': 'false'})

    def test_each_missing_secret_fails_before_expensive_generation(self):
        ready = dict.fromkeys(REQUIRED, 'present-secret-value')
        ready['PUBLISH_ENABLED'] = 'true'
        validate(ready)
        for name in REQUIRED:
            for absent in ('', '   '):
                with self.subTest(name=name, absent=absent):
                    with self.assertRaisesRegex(ValueError, name) as raised:
                        validate(dict(ready, **{name: absent}))
                    self.assertNotIn('present-secret-value', str(raised.exception))

    def test_missing_facebook_token_warns_without_blocking_youtube(self):
        ready = dict.fromkeys(REQUIRED, 'present-secret-value')
        ready.update(PUBLISH_ENABLED='true', FACEBOOK_PUBLISH_ENABLED='true')
        for absent in ('', '   '):
            with self.subTest(absent=absent), redirect_stdout(io.StringIO()) as output:
                validate(dict(ready, FACEBOOK_PAGE_ACCESS_TOKEN=absent))
                self.assertIn('::warning::', output.getvalue())
                self.assertNotIn('present-secret-value', output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            validate(dict(ready, FACEBOOK_PAGE_ACCESS_TOKEN='present-secret-value'))
            self.assertEqual('', output.getvalue())
        del ready['YOUTUBE_TOKEN_JSON']
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'YOUTUBE_TOKEN_JSON'):
            validate(ready)

    def test_production_rejects_disabled_switch_instead_of_silently_rendering(self):
        for value in ('','false','TRUE'):
            with self.assertRaisesRegex(ValueError,'PUBLISH_ENABLED=true'):
                validate({'PUBLISH_ENABLED':value},require_enabled=True)
        ready=dict.fromkeys(REQUIRED,'configured');ready['PUBLISH_ENABLED']='true'
        validate(ready,require_enabled=True)
