"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-realistic-3d-v5'
STYLE = ('Realistic cinematic 3D storybook render, lifelike facial proportions, beautiful expressive face, '
         'natural skin, detailed fabrics, soft volumetric lighting. ')


def art_prompt(scene, kind='background'):
    framing = {
        'background': 'Medium wide shot. ',
        'reference': 'Character portrait, fixed clothes. ',
        'thumbnail': 'Chest-up portrait, large face, intriguing object. ',
    }[kind]
    return STYLE + framing + scene + (
        ' Rich teal and gold colors, soft depth of field, no text.'
    )
