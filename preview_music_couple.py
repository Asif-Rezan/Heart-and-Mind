import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from music_video import scene_contract
from story_art_style import focused_prompt
from story_image_review import generate_reviewed
import hashlib
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
seed=int(hashlib.sha256(('couple-v3:'+kind).encode()).hexdigest()[:8],16)
report=generate_reviewed(prompt,out/(kind+'.png'),seed=seed,contract=contract,
                         kind=kind,width=1344,height=768,steps=20)
(out/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
(out/'used-prompt.txt').write_text(report['prompt']+'\n')
print('SAVED VERIFIED',out/(kind+'.png'),flush=True)
