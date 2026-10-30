"""Require the existing Heart and Mind destination before any generation."""
import os
from story_publication import HEART_CHANNEL_ID


def validate(environment=None):
    environment=os.environ if environment is None else environment
    required=('DRIVE_TOKEN_JSON','DRIVE_FOLDER_ID')
    if environment.get('PUBLISH_ENABLED','true') != 'false':
        required+=('YOUTUBE_TOKEN_JSON','EXPECTED_CHANNEL_ID')
    missing=[name for name in required if not environment.get(name,'').strip()]
    if missing:
        raise ValueError('Missing story configuration: '+', '.join(missing))
    if environment.get('EXPECTED_CHANNEL_ID') and environment['EXPECTED_CHANNEL_ID'] != HEART_CHANNEL_ID:
        raise ValueError('Story destination must be Heart and Mind')

if __name__=='__main__':
    validate()
