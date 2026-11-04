"""Prevent optional cache saving from failing successful CPU generation jobs."""
from pathlib import Path
import re
import unittest

import yaml


class WorkflowPipCacheTests(unittest.TestCase):
    def test_uncached_install_jobs_do_not_register_a_pip_cache_save(self):
        checked = 0
        workflows = Path(__file__).parent / '.github' / 'workflows'
        for path in sorted(workflows.glob('*.yml')):
            jobs = yaml.safe_load(path.read_text()).get('jobs', {})
            for name, job in jobs.items():
                steps = job.get('steps', [])
                installs = [step.get('run', '') for step in steps]
                if not any(re.search(r'\bpip\b[^\n]*--no-cache-dir\b', command)
                           for command in installs):
                    continue
                checked += 1
                with self.subTest(workflow=path.name, job=name):
                    for step in steps:
                        if step.get('uses', '').startswith('actions/setup-python@'):
                            self.assertNotEqual(
                                step.get('with', {}).get('cache'), 'pip',
                                'Uncached installs may never create the pip cache directory; '
                                'setup-python then fails in its post-job save step.',
                            )
                    # Keep genuine generation/setup failures visible to downstream jobs.
                    self.assertFalse(job.get('continue-on-error', False))
        self.assertGreater(checked, 0, 'No uncached install jobs were checked')


if __name__ == '__main__':
    unittest.main()
