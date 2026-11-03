import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from music_video import scene_contract
from story_art_style import focused_prompt
from story_image_cpu import generate
song=json.loads(Path('lyrics/tum-laut-aao-2026-11-03.json').read_text())
print(song.keys(),flush=True)
if 'song' in song:song=song['song']
import os
kind=os.environ.get('IMAGE_KIND','thumbnail')
contract=scene_contract(song,0,1,kind)
prompt=focused_prompt(contract,kind)
out=Path('output/romantic-couple-test')/kind;out.mkdir(parents=True,exist_ok=True)
(out/'plan.json').write_text(json.dumps(dict(contract=contract,prompt=prompt),ensure_ascii=False,indent=2))
print(prompt,flush=True)
used_prompt=generate(prompt,out/(kind+'.png'),seed=32791,width=1344,height=768,steps=20,negative_extra='third person, extra people, duplicate man, group photo, wedding, gold, amber, yellow tint, orange light, sepia, distant people, hidden face, overlapping faces',story_contract=contract,kind=kind)
print('SAVED',out/(kind+'.png'),flush=True)
(out/'used-prompt.txt').write_text(used_prompt+'\n')
