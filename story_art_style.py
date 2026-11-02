"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-3d-v4'
STYLE = ('3D cartoon storybook illustration, stylized animated character, rounded sculpted face, '
         'large expressive eyes, soft clay materials, cinematic lighting. ')


def art_prompt(scene, kind='background'):
    framing = {
        'background': 'Medium wide shot. ',
        'reference': 'Character portrait, fixed clothes. ',
        'thumbnail': 'Chest-up portrait, large face, intriguing object. ',
    }[kind]
    return STYLE + framing + scene + (
        ' Rich teal and gold colors, soft depth of field, no text.'
    )
