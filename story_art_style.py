"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-3d-v3'
STYLE = ('3D storybook illustration, polished animated film render, appealing expressive face, '
         'balanced facial features, clear eyes, soft sculpted shapes, warm soft key light. ')


def art_prompt(scene, kind='background'):
    framing = {
        'background': 'Medium wide composition, readable character and setting. ',
        'reference': 'Single character portrait, fixed clothing, uncluttered backdrop. ',
        'thumbnail': 'Chest-up hero portrait, face large and well lit, one intriguing story object. ',
    }[kind]
    return STYLE + framing + scene + (
        ' Rich teal and gold colors, soft depth of field, no text.'
    )
