# Heart and Mind — Hindi music videos

The active pipeline creates original Hindi songs again: Qwen writes the lyrics,
ACE-Step 1.5 sings the full song, and the current realistic cinematic **3D storybook**
image system supplies the video scenes and thumbnail. New music videos change their
background image **every five seconds**, measured against the generated audio.

## Active version: music + current 3D visuals

Implementation checkpoint: [`checkpoint/music-return-3d-5s-2026-11-03`](https://github.com/Asif-Rezan/Heart-and-Mind/tree/checkpoint/music-return-3d-5s-2026-11-03).

- Music restoration source: [`0fca9240b5edf786f09a806401a62dcc386eb0f6`](https://github.com/Asif-Rezan/Heart-and-Mind/commit/0fca9240b5edf786f09a806401a62dcc386eb0f6), the saved Hindi music version.
- Original source archive: [`legacy/hindi-music/`](legacy/hindi-music/).
- Music synthesis remains the saved `music_cpu.py` implementation, pinned source,
  model revisions, CPU settings and vocal handling. No narration engine replaces singing.
- Daily direction alternates male/female vocals by Dhaka calendar date; manual
  `vocal_gender=male` or `female` applies only to a fresh song identity.
- New songs target the previous focused arrangement of about **195 seconds**.
  Actual audio is checked to remain within **180–360 seconds**.
- Graphics retain the current protected cinematic 3D/CGI style, attractive realistic
  adult faces, fair complexion, age-appropriate appearance and lyric-specific setting.
  Adult visual leads use stable ages/outfits within the song. Faces are generated,
  so exact identity across every image is not guaranteed.
- Background sources: **1024×576**, 20 CPU diffusion steps. Each five-second slot has
  its own image seed, with progression through the songwriter's visual scenes.
- Thumbnail: **1344×768** native generation, centered 16:9 crop, **1920×1080 JPEG**
  export. The scene is text-free and tied to the actual song's emotional promise.
- Video: **1920×1080, 25 fps**, slow alternating camera push/pull and pans,
  0.4-second dissolves beginning at five-second boundaries, subtle color/vignette
  treatment and rhythmic light variation, plus a genuinely audio-reactive waveform.
  Full audio duration is retained and encoded as AAC at 320 kb/s.
- Scene progression is editorial pacing through the song, **not word-level lyric
  transcription or lip synchronization**. Existing singing/lyrics are preserved.

## Lyrics and phrasing revision — 2026-11-03

Music automation is **manually disabled in GitHub Actions** at the user’s request.
Do not enable it or start a song until the lyrics changes have been reviewed. The
first return run failed before songwriting: regression tests needed `ffprobe`.
The lyrics job now installs FFmpeg before tests; no song was generated or published.

New lyrics focus on romance, longing, separation, reunion, tenderness and healing
after lost love, rather than motivational advice. The songwriter and revision pass
receive the same tempo, 4/4 meter and breathable two-bar phrasing brief. Verse lines
should share a melodic shape, with natural near-rhyme and an exact repeated chorus.

`lyric_quality.py` checks section/line counts, chorus identity, repeated verse filler,
word load and approximate written vowel lengths. A separate model critique also
checks relationship meaning, idiomatic Hindi, natural rhyme and singable phrasing.
It sends specific failures back for at most three revisions, saves
`lyrics-quality.json`, and blocks music creation
if these checks still fail. New song metadata carries the checked lyric hash and
report; resumed preparation rechecks the text. Historical unversioned songs are
not silently rewritten beneath existing audio.

This is a **written-phrasing heuristic**, not exact Hindi scansion, an acoustic beat
score or proof of good poetry. Schwa deletion, held notes, melody and emotional
delivery still need listening review. No new full song has been auditioned for this
revision. The previous music-return implementation remains saved at commit
[`77c2f23`](https://github.com/Asif-Rezan/Heart-and-Mind/commit/77c2f236157ccca2efcd50cc7d0a9ad0ef292e89)
and its existing checkpoint tag. The test lyric in `tests/fixtures/romantic_lyrics.txt` exercises the checks;
it is not hardcoded as the generator’s song.

## Daily automation and manual runs

Active workflow: [`.github/workflows/music-hindi-songs.yml`](.github/workflows/music-hindi-songs.yml),
**Hindi album music generation and public publishing**.

The existing daily schedule remains **03:00 Asia/Dhaka** (`0 21 * * *` UTC), gated by
`AUTOMATION_ENABLED=true`. The story workflow is now manual-only so it cannot compete
with the music schedule. Its full graph remains available for historical recovery.
Existing Google credentials, destination channel, private Drive backup, duplicate
checks, AI disclosure and verified-public cleanup are retained. `PUBLISH_ENABLED=false`
keeps the result as a generated artifact instead of uploading it.

For an immediate new song, run the music workflow on `main` with:

- `run_id`: a fresh identity such as `music-2026-11-03-return-01`. Empty uses the Dhaka date.
- `vocal_gender`: `auto`, `male`, or `female`.
- `prepared_run`: leave empty for a new song. To resume an unfinished song, provide
  its previous numeric music workflow run and reuse the **same** run ID/voice.

Generation order: lyrics/history/channel checks → ACE-Step full song → measured
visual timeline → **12 image workers** → Python/FFmpeg cinematic edit → checksum-
verified upload on Heart and Mind → fresh public-HD verification and Drive cleanup.
Publishing requires completed local assets and cannot silently start another music
synthesis job. A rerun never reuploads an already confirmed published identity.

Each worker packages only its own images/manifests; restored foreign worker files
cannot overwrite another owner's output. Image/model/review/scene hashes invalidate
stale caches. Rendering reuses only hash-matched clips and verifies final duration.
Failed image reviews retain explicit recovery status rather than stopping the whole
song. Such recovery is not proof of semantic quality or a measured CTR improvement.
More images require more CPU time than the historical two-picture visualizer;
completion also depends on shared runner availability.

For local/manual staging using existing dependencies and model setup:

```sh
python prepare_music.py --run-id MUSIC_ID --stage lyrics --check-history --motion-video
python prepare_music.py --run-id MUSIC_ID --stage music --motion-video
python prepare_music.py --run-id MUSIC_ID --stage images --motion-video
python prepare_music.py --run-id MUSIC_ID --stage render --motion-video
python pipeline.py --run-id MUSIC_ID --require-prepared --defer-drive-cleanup
```

Use the workflow for its pinned ACE-Step source checkout, CPU dependencies, memory
preparation and credentials. The old two-image renderer remains available for saved
legacy songs without the new `video_format` marker.

## Story version checkpoint and change log — 2026-11-03

Saved before returning to music:

- Previous deployed story version: `bfe45a4057a8b17ea4c6eb814a7cba085395b1ff`.
  Tag: [`checkpoint/story-production-before-music-2026-11-03`](https://github.com/Asif-Rezan/Heart-and-Mind/tree/checkpoint/story-production-before-music-2026-11-03).
- Story code including the current graphics recovery/style fixes: `2785ac49f57949c8485f079a409fc93af3d504a8`.
  Tag: [`checkpoint/story-graphics-before-music-2026-11-03`](https://github.com/Asif-Rezan/Heart-and-Mind/tree/checkpoint/story-graphics-before-music-2026-11-03).
  This graphics checkpoint was a review branch, distinct from the deployed story commit.
- [Verbatim pre-music README](docs/story-readme-before-music-2026-11-03.md) (historical
  relative paths refer to the repository root).
- [Saved full 40-commit story log](docs/story-commit-log-before-music-2026-11-03.txt).
- [Original Hindi music commit log](docs/hindi-music-commit-log.txt).

Changes in this music return:

1. Restore original Hindi songwriting/singing and daily music automation.
2. Keep the current production 3D image backend, safety/recovery, protected style
   prompts and full-HD thumbnail export instead of resetting the repository.
3. Generate a new background at each measured five-second slot and edit the images
   into a moving music-video sequence with pans, zooms, dissolves and waveform.
4. Keep story generation manual-only and preserve the exact story checkpoints.
5. Preserve duplicate-upload protection, destination validation and cleanup guards.

Inspect either story checkpoint in a separate checkout without rewriting shared history:

```sh
git fetch origin --tags
git worktree add ../heart-story-saved checkpoint/story-graphics-before-music-2026-11-03
```

Historical story recovery commands, earlier voice/puppet checkpoints and production
incident logs are retained in the saved README and the tagged repository versions.
Rollback restores tracked source; it does not roll back secrets, uploads or Drive data.

## Verification

The test suite covers the saved music engine, publication/channel safeguards,
current image style/recovery, five-second fractional-duration timelines, separate
full-HD thumbnails, worker-owned artifacts, and actual FFmpeg motion/dissolve/audio
rendering. Tests do not predict YouTube views, CTR, or audience retention.
