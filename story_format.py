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
    return story.get('format') in (FORMAT,SAMPLE_FORMAT)


def duration_bounds(story):
    # Saved releases keep their original recovery contract.
    if is_sample(story):return (55,65)
    return (MIN_SECONDS, MAX_SECONDS) if is_short(story) else (480, 720)

# Preview profile uses the production pipeline, with smaller content budgets.
SAMPLE_FORMAT = 'pipeline-sample-60s-v1'


def is_sample(story):
    return story.get('format') == SAMPLE_FORMAT


def scene_count(story):
    return 12 if is_sample(story) else 48


def scenes_per_chapter(story):
    return scene_count(story)//6


def word_bounds(story):
    if is_sample(story):return (120,165)
    return (MIN_WORDS,MAX_WORDS) if is_short(story) else (1000,1600)


def score_part_seconds(story):
    return 30 if is_sample(story) else 120
