"""Truthful searchable music metadata and a bright, mobile-readable cover."""
import re
from pathlib import Path
from PIL import Image,ImageOps,ImageEnhance,ImageDraw,ImageFont


def metadata(song,chapters):
 title=song['title'].strip()
 suffix=' | Emotional English Pop Song'
 if len(title)+len(suffix)>100:suffix=' | English Pop'
 tags=list(dict.fromkeys(song['tags']))
 for tag in ['English song','emotional pop','soft pop','original AI music']:
  if tag.casefold() not in {t.casefold() for t in tags} and sum(len(t)+2 for t in tags)+len(tag)+2<=500:tags.append(tag)
 if sum(len(t)+2 for t in tags)>500:raise ValueError('Upload tag budget exceeded')
 details=song['description'].strip()+'\n\nStory\n'+song['story'].strip()
 tail=(
  '\n\nOriginal English song created with AI-generated lyrics, singing/music and artwork. '
  'Cinematic visual scenes accompany the complete vocal performance.\n\nVisual chapters\n'+'\n'.join(chapters)+
  '\n\nLyrics\n'+song['lyrics']+'\n\n#EnglishSong #EmotionalPop #SoftPop')
 opening=f'{title} — an original emotional English soft-pop song.\n\n'
 budget=5000-len(opening)-len(tail)
 if budget<100:raise ValueError('Complete lyrics and chapters exceed description budget')
 description=opening+details[:budget].rstrip()+tail
 return dict(title=title+suffix,description=description,tags=tags)


def thumbnail(source,target,title):
 with Image.open(source) as raw:
  image=ImageOps.fit(raw.convert('RGB'),(1920,1080),method=Image.Resampling.LANCZOS)
 image=ImageOps.autocontrast(image,cutoff=.5,preserve_tone=True)
 image=ImageEnhance.Brightness(image).enhance(1.35)
 image=ImageEnhance.Contrast(image).enhance(1.12)
 image=ImageEnhance.Color(image).enhance(1.18)
 # Keep the scene bright; darken only the top strip behind the real song title.
 shade=Image.new('RGBA',image.size,(0,0,0,0));draw=ImageDraw.Draw(shade)
 for y in range(430):draw.line((0,y,1919,y),fill=(5,10,24,int(210*max(0,1-y/430))))
 image=Image.alpha_composite(image.convert('RGBA'),shade)
 font_path=next((p for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/System/Library/Fonts/Supplemental/Arial Bold.ttf') if Path(p).exists()),None)
 if not font_path:raise ValueError('Install a bold TrueType font for readable thumbnails')
 title=re.sub(r'\s+',' ',title).strip().upper();words=title.split()
 draw=ImageDraw.Draw(image)
 for size in range(150,49,-2):
  font=ImageFont.truetype(font_path,size);lines=['']
  for word in words:
   trial=(lines[-1]+' '+word).strip()
   if draw.textlength(trial,font=font)>1720 and lines[-1]:lines.append(word)
   else:lines[-1]=trial
  if len(lines)<=2 and max(draw.textlength(line,font=font) for line in lines)<=1720:break
 else:raise ValueError('Thumbnail title cannot fit readable cover layout')
 for i,line in enumerate(lines):
  draw.text((100,60+i*(size+22)),line,font=font,fill='#FFF06A' if i==0 else 'white',stroke_width=6,stroke_fill='#081020')
 image.convert('RGB').save(target,quality=94,optimize=True)
 if Path(target).stat().st_size>=2*1024*1024:raise ValueError('YouTube thumbnail exceeds 2MB')
