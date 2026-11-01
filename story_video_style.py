"""Standard-library-only daily visual rotation and persisted resume selection."""
import json
import os
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path


def video_style(root):
    requested=os.getenv('STORY_VIDEO_STYLE','').strip()
    path=Path(root)/'video-style.json'
    saved=json.loads(path.read_text())['style'] if path.exists() else None
    if requested in ('','auto'):
        if saved:
            style=saved
        elif (Path(root)/'render-state.json').exists() and json.loads((Path(root)/'render-state.json').read_text()).get('version','').startswith('hindi-story-motion-'):
            # Old prepared runs predate the style marker and used backgrounds.
            style='background'
        elif any(Path(root).glob('image-manifest-*.json')) and any(
                isinstance(plan,dict) and 'model' in plan
                for manifest in Path(root).glob('image-manifest-*.json')
                for plan in json.loads(manifest.read_text()).values()):
            style='background'
        else:
            match=re.fullmatch(r'story-(\d{4}-\d{2}-\d{2})',Path(root).name)
            day=date.fromisoformat(match[1]) if match else datetime.now(ZoneInfo('Asia/Dhaka')).date()
            # 2026-11-01 puppet, 2026-11-02 background; no mutable counter.
            style='puppet' if (day-date(2026,11,1)).days%2==0 else 'background'
    else:
        style=requested
    if style not in ('puppet','background'):
        raise ValueError('STORY_VIDEO_STYLE must be auto, puppet or background')
    if saved and style!=saved:
        raise ValueError('Video style differs from saved run; use a new run ID for the other renderer')
    return style

