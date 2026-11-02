"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-events-3d-v8'
CAST_DIRECTION = (
    'Give every character a fair complexion, attractive harmonious facial features and clear face lighting, '
    'while preserving their exact age, identity and distinct appearance. '
    'Adult women have strikingly beautiful refined features, expressive eyes, elegant hair, '
    'subtle makeup and tasteful flattering clothes consistent with their established outfit. '
    'Keep children age-appropriate and preserve elderly characters as elderly. '
)
STYLE = ('Realistic cinematic 3D storybook render, attractive characters, fair skin, lifelike facial proportions, '
         'natural skin texture, soft volumetric lighting. ')


def art_prompt(scene, kind='background'):
    if kind == 'reference':
        return 'Realistic cinematic 3D character reference. '+scene+' Natural proportions, fair skin, no text.'
    # Action/object must lead both CLIP encoders. Appearance cannot displace the story.
    return ('Narrative scene, medium wide shot. '+scene+
            ' Realistic cinematic 3D storybook, expressive attractive characters, fair skin, soft light, no text.')
