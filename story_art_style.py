"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-realistic-3d-v7'
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
    if kind == 'thumbnail':
        # The story object must reach CLIP before portrait/style embellishments.
        return ('Realistic cinematic 3D storybook render, attractive faces, fair skin. '+scene+
                ' Medium shot, object and face both prominent, natural proportions, soft dramatic lighting, no text.')
    framing = {
        'background': 'Medium wide shot. ',
        'reference': 'Character portrait, fixed clothes. ',
    }[kind]
    return STYLE + framing + scene + (
        ' Rich teal and gold colors, soft depth of field, no text.'
    )
