"""Fail early for enabled publication without printing secret values."""
import argparse
import os
from pathlib import Path

REQUIRED = ('YOUTUBE_TOKEN_JSON', 'EXPECTED_CHANNEL_ID', 'DRIVE_TOKEN_JSON', 'DRIVE_FOLDER_ID')


def validate(environment=None, *, require_enabled=False):
    environment = os.environ if environment is None else environment
    if environment.get('FACEBOOK_PUBLISH_ENABLED') == 'true' and not environment.get('FACEBOOK_PAGE_ACCESS_TOKEN', '').strip():
        print('::warning::Facebook token is missing; optional Facebook publication may fail. YouTube generation and publication will continue.')
    if environment.get('PUBLISH_ENABLED') != 'true':
        if require_enabled:
            raise ValueError('YouTube publication is disabled: set repository variable PUBLISH_ENABLED=true. Use the no-publishing preview workflow for render-only runs.')
        return
    missing = [name for name in REQUIRED if not environment.get(name, '').strip()]
    if missing:
        raise ValueError('Publishing is enabled but required repository secrets are missing: ' + ', '.join(missing))


if __name__ == '__main__':
    try:
        parser=argparse.ArgumentParser()
        parser.add_argument('--require-enabled', action='store_true')
        args=parser.parse_args()
        validate(require_enabled=args.require_enabled)
        summary=os.getenv('GITHUB_STEP_SUMMARY')
        if summary:
            youtube='enabled' if os.getenv('PUBLISH_ENABLED')=='true' else 'DISABLED — no YouTube upload'
            facebook='enabled' if os.getenv('FACEBOOK_PUBLISH_ENABLED')=='true' else 'DISABLED — no Facebook upload'
            with Path(summary).open('a') as stream:
                stream.write('### Publication configuration\n\nYouTube: '+youtube+'.\n\nFacebook: '+facebook+'.\n\nA successful render alone does not mean a video was uploaded.\n')
    except ValueError as error:
        raise SystemExit(str(error)) from None
