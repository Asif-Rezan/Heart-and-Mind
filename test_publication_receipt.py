import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from publication_receipt import report


class ReceiptTests(unittest.TestCase):
    def test_render_success_cannot_be_reported_as_uploaded(self):
        for state in ({},{'phase':'rendered','video_id':'abc'},{'phase':'published'}):
            with self.assertRaises(ValueError): report(state)

    def test_scheduled_receipt_shows_dhaka_time_and_not_public_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary=Path(tmp)/'summary.md'
            with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':str(summary)}),redirect_stdout(io.StringIO()):
                result=report({'phase':'scheduled','video_id':'abc123', 'schedule_target':'2026-11-14T11:00:00Z'})
            self.assertEqual(result['publish_at_dhaka'],'2026-11-14T17:00:00+06:00')
            self.assertIn('not public yet',summary.read_text())
            self.assertIn('https://www.youtube.com/watch?v=abc123',summary.read_text())

    def test_scheduled_upload_requires_confirmed_time(self):
        with self.assertRaises(ValueError): report({'phase':'scheduled','video_id':'abc'})

    def test_public_receipt_reports_verified_public_phase(self):
        with patch.dict(os.environ,{},clear=True),redirect_stdout(io.StringIO()):
            value=report({'phase':'published','video_id':'abc'})
        self.assertEqual(value['status'],'published')
