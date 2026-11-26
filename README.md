# Heart and Mind — original English emotional pop / soft-pop

The new song pipeline creates original **English sung songs**, their title,
description/tags, six lyric-related AI background images and a **MoviePy cinematic
1920×1080 landscape music video**. This implementation is on `codex/english-songs`;
main is unchanged until the reviewed migration is merged. The previous Hindi,
English family-cartoon and ASMR implementations remain archived/versioned.

## What changed

- Qwen writes structured verses, pre-chorus, chorus, bridge and outro. An
  independent AI editorial pass checks idiomatic English, emotional progression,
  hook, singability and concrete imagery. Rejected drafts are revised, not clipped
  into shape or replaced by a fixed nursery refrain. The accepted chorus is
  repeated exactly; verses must advance the story without duplicate filler.
- ACE-Step 1.5 turbo generates the actual singing and musical arrangement with
  `vocal_language=en`, adult vocals and an English soft-pop caption. This is not
  Kokoro narration, a synthetic oscillator tune or translated Hindi audio. Default
  target is 210 seconds; 180–300 seconds can be selected. The complete measured
  performance is retained, with stereo loudness mastering and dropout checks.
- Pinned SSD-1B generates six distinct 1024×576 cinematic background images, at 24
  steps. The old forced nursery/cartoon prompt and `photorealistic` negative prompt
  are removed for this mode. Artwork follows the lyric story, palette and light,
  favoring scenery/objects rather than difficult recurring faces. Existing legacy
  image modes keep their previous behavior and safety checks.
- MoviePy 2.2.1 grades the artwork gently, applies a soft vignette, restrained slow
  push/pull/pan and real overlapping dissolves. The canvas stays **16:9**, without
  stretching portrait pictures. Full singing/audio survives the composition.
  Description chapter times follow the actual visual timeline. The thumbnail is
  exported from this song's opening artwork, without AI-generated lettering.
- Isolated private Drive backup, resumable YouTube and optional Facebook feed-video
  publication, fresh public-HD checks and exact-file cleanup are included. English
  metadata/audio, Music category, not-made-for-kids and AI disclosure are explicit.

These are AI-generated still backgrounds with cinematic camera movement, not
actor animation or word-level lip sync. Written review scores do not prove the
unheard song has good pronunciation, melody or perfect lyric adherence. Each new
song still needs a finished listening/viewing review; original prompting and
history checks are not a global copyright/originality guarantee.

## Preview first: publishing is OFF

Change `.generation/english-song-request.json` on `codex/english-songs` to start an
artifact-only test. The request-file change triggers generation; ordinary code
pushes do not. The default test creates a new English song with a mature female
voice and a 210-second target. Six image jobs run alongside the music job.

YouTube/Facebook publication, Drive backup and Drive deletion are off for ordinary
branch tests. Old `PUBLISH_ENABLED` and `AUTOMATION_ENABLED` variables cannot enable
this pipeline. There are no hosted model API charges or newly provisioned GPUs;
CPU model inference can be slow. The first preview must complete before claiming
that a real new song has been generated successfully.

After the workflow is on the default branch, GitHub Actions → **Heart and Mind
original English songs** → **Run workflow** supports a topic, duration, adult
male/female voice, stable run ID and recovery inputs. The default `publish=false`
continues to produce review artifacts only.

Artifacts (fourteen days) include accepted/draft lyrics and critique, raw/mastered
song, six background sources and receipts, thumbnail, finished video, metadata,
media hashes and publication diagnostics. Do not confuse technical test fixtures
with generated songs; no fixture is a generation fallback.

## Publication and Drive cleanup

Publishing requires BOTH dispatch `publish=true` and repository variable
`ENGLISH_SONG_PUBLISH_ENABLED=true`. Optional Facebook also requires
`ENGLISH_SONG_FACEBOOK_ENABLED=true`, this project's `FACEBOOK_PAGE_ID` and
`FACEBOOK_PAGE_ACCESS_TOKEN`. Cleanup requires
`ENGLISH_SONG_CLEANUP_ENABLED` defaults to on for verified published songs; set it
to `false` to retain all media. Publishing remains disabled during previews, so
preview media is never automatically deleted.

Use the existing Heart and Mind `YOUTUBE_TOKEN_JSON`, `EXPECTED_CHANNEL_ID`,
`DRIVE_TOKEN_JSON` and `DRIVE_FOLDER_ID`. No account credentials or destination IDs
are copied from another project. The original account, owner, private-folder and
quota guards remain. English songs use their own child marker
`heart_and_mind_english_songs_root=v1`, separate from Hindi/cartoon and ASMR media.

Backup verifies exact file identity/checksums and saves essential song, metadata,
audio and media receipts before marking completion. Upload uses the existing
ambiguous-insert and saved-video-ID guards; reruns do not blindly duplicate songs.
The Actions graph shows publication → **Verify published platforms and clean Drive media**
as separate jobs. The cleanup job restores only small receipts, writes an audit
artifact and reports reclaimed bytes in the run summary. It remains skipped in
preview mode or after publication failure.

Cleanup freshly verifies the correct YouTube video/channel, metadata, AI/audience
settings and public HD processing. If Facebook was required in the original
checkpoint, it must also be confirmed even if its enable flag changes later.
Only exact manifested disposable media IDs, private parents, names, workflow keys,
MD5 checksums and sizes qualify for deletion. The complete manifest is checked
before the first delete. History and essential JSON remain; failed, private,
scheduled, incomplete or ambiguous publications retain their media.

`operation=recover` restores verified Drive media and resumes the saved platform
IDs without new lyrics/music/images. `operation=cleanup` restores only essential
metadata and retries fresh publication checks. Use the original source revision.
For generation recovery, use the same run ID, topic, duration and voice plus the
original `prepared_run`; missing/expired artifacts fail clearly. Saved singing
cannot be reused under changed lyrics.

Daily generation runs at **03:00 Asia/Dhaka** from the default branch. Set
`ENGLISH_SONG_AUTOMATION_ENABLED=false` to pause it. Scheduled publishing additionally
requires `ENGLISH_SONG_PUBLISH_ENABLED=true`; testing keeps this off. The old cartoon workflow is replaced in this branch and
archived for rollback, rather than running a second format from the same trigger.

## Models and local checks

- Qwen3-4B-Instruct-2507: existing pinned Q4_K_M CPU runtime/revision/checksum.
- ACE-Step source `ca1e85fe9430179831e6bc6be790c332190a3866`, model revision
  `19671f406d603126926c1b7e2adc169acbcade22`, turbo eight-step CPU generation.
- SSD-1B revision `60987f37e94cd59c36b1cba832b9f97b57395a10`, cinematic mode.
- MoviePy 2.2.1; FFmpeg/ffprobe for mastering, encoding and complete decode checks.

Use Python 3.12, FFmpeg and `pip install -r requirements.txt` for component tests;
stage-specific music/image dependencies are installed by the workflow.
`python -m unittest -v` and `actionlint` check lyrics, language wiring, media,
MoviePy timing, checkpoint/backup recovery and disabled-publication behavior.
Model caches reuse pinned lyrics/image weights. The owner-approved cache quota
is unchanged; ACE-Step weights stay runner-local, and cache eviction can trigger
another download.

## History and rollback

- [README before this English-song migration](docs/archive/before-english-songs-2026-11-26-README.md)
- [Previous English family-cartoon workflow](docs/archive/before-english-songs-2026-11-26-music.yml.txt)
- [Original Hindi emotional-song README](docs/archive/before-hindi-kids-reference-2026-11-09-README.md)
- [Later Hindi nursery-rhyme README](docs/archive/before-english-family-cartoon-2026-11-10-README.md)
- [ASMR implementation and controls](docs/asmr-production.md)
- [Wan preview and its hardware limitations](docs/wan-short-preview.md)

Sources: [ACE-Step English vocal language and parameter documentation](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/API.md),
[SSD-1B model and limitations](https://huggingface.co/segmind/SSD-1B),
[MoviePy v2 composition and transitions](https://zulko.github.io/moviepy/user_guide/compositing.html).

Search packaging uses the actual song title with an English emotional-pop qualifier,
relevant deduplicated tags, story, complete lyrics, AI disclosure and measured visual
chapters. Thumbnails use the actual opening artwork with bright tonal separation,
strong warm/cool composition and a bold readable song title. No invented artist
credits, popularity claims or promised CTR gains are added.
