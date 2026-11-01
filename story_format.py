"""Release format shared by writing, narration, imagery and publishing."""
FORMAT = 'short-story-v2'
MIN_SECONDS = 240
MAX_SECONDS = 360
TARGET_SECONDS = 300
MIN_WORDS = 520
MAX_WORDS = 720
IMAGE_SECONDS = 4
NARRATOR = 'hm_omega'


def is_short(story):
    return story.get('format') == FORMAT


def duration_bounds(story):
    # Saved releases keep their original recovery contract.
    return (MIN_SECONDS, MAX_SECONDS) if is_short(story) else (480, 720)
