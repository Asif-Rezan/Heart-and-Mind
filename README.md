# Heart and Mind — Hindi music videos

The active pipeline creates original Hindi songs again: Qwen drafts lyrics or an
explicitly selected, repository-reviewed original song supplies them,
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

The user paused music automation for lyrics work, then authorized a new generation.
The first revised run (`41592294627`) stopped at lyric quality review before music. The
earlier return run failed before songwriting: regression tests needed `ffprobe`.
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


### Production lyric recovery — 2026-11-03

Run `41592294627` produced inline section headings and only two chorus lines, plus
awkward Hindi, so review rejected it. The old parser incorrectly reported zero
words for inline headings. It now reads that layout without losing the first line,
but missing lines or weak wording still cannot pass.

New model responses use six structured line arrays with exact section lengths.
The program renders section headings and repeats the four-line chorus locally;
the model no longer has to reproduce the full eight-section text layout. Creative
instructions are shorter, and revisions can discard nonsensical imagery rather
than being told to preserve a defective hook. Review reports use version 3 and
emit static, useful failure diagnostics without dumping the song into job logs.
Existing failed draft artifacts can be supplied as `prepared_run` for recovery.

### Reviewed production song after the second lyric rejection — 2026-11-03

Run `41594691413` had correct section layout but weak, nonsensical Hindi. It stopped
before music after the written-vowel heuristic found a bridge difference of 8 units
(14 vs 22). Such estimates cannot prove acoustic rhythm: they are now warnings
passed to editorial critique, rather than a rigid meter veto. Structural errors,
word overload, inconsistent choruses and failed meaning/rhyme critique still block
an automatically drafted song. The 4B model's poetry remains fallible; these changes
are not proof that future automatic lyrics will be good.

For the next video, `lyrics/tum-laut-aao-2026-11-03.json` contains a newly authored,
Codex-edited 199-word original romantic song with natural Hindi, male narrator,
consistent तुम address, exact chorus repeats, 86 BPM directions and lyric-specific
3D scene/thumbnail prompts. Its editorial provenance is explicitly recorded as an
authored review, **not a model approval or a human listening review**. It passes the
structural and written-phrasing checks without warnings. Synthesized audio has not
yet been auditioned.

Set workflow input `authored_song=tum-laut-aao-2026-11-03` with a **fresh** run ID.
The lyrics stage loads this exact reviewed file, rechecks publication history and
phrasing, records its SHA-256, and never asks the text model to rewrite it. All audio,
images, five-second video editing and publication guards use the normal pipeline.
Leave `prepared_run` empty. Omit `authored_song` for the automatic drafting path.
An authored source cannot replace different saved lyrics/audio under an existing ID.

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
- `authored_song`: optional reviewed song identity from `lyrics/`; empty uses model drafting.
- `prepared_run`: leave empty for a new song. To resume an unfinished song, provide
  its previous numeric music workflow run and reuse the **same** run ID/voice.

Generation order: lyrics/history/channel checks → parallel ACE-Step full song and
**14 image workers**, plus independent Shorts music and **4 portrait workers** →
measured edits → checksum-verified uploads on Heart and Mind → fresh public-HD
verification and Drive cleanup.
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


## Parallel long video and independent Shorts

Every music run now starts the long audio worker and fourteen image workers directly
from the saved lyrics. Image identities use the requested duration; the final edit
still uses the measured audio and five-second cuts. A fractional audio overrun uses
the final scene again, without forcing all image workers to wait for synthesis.

The same run calls `music-short.yml` to make one companion Short. Its reviewed
chorus and bridge receive a **new 45-second ACE-Step synthesis** with a hook-first
arrangement; no long-song audio is clipped. Four image workers generate fresh
576×1024 portrait scenes, then the edit exports 1080×1920. Shorts use a dedicated
edit: an immediate hook card, audio-energy cuts
near the tempo grid, alternating two/four-beat shots, punch-in/pull-out/panning,
restrained accent flashes and large readable lyric cards inside the portrait safe
area. These cards are editorial excerpts, not forced-aligned karaoke timestamps.

Long music, long images, Short music and Short images can all run concurrently, subject to GitHub's runner
quota. The generation fan-out is 14 long-image workers + 4 portrait workers +
2 separate music workers = 20 jobs. The Short uses the same song hook, rather than
claiming to be a new song.

The companion has a separate `-short` run identity, artifacts and durable Drive
publication state. It publishes publicly on the verified Heart and Mind channel,
with synthetic-media disclosure, `#Shorts`, measured duration/dimension checks and
the same ambiguous-upload protection as long videos. YouTube selects its thumbnail
frame; the uploader does not attempt an unsupported Shorts custom-thumbnail change.
Temporary Drive media is removed only after fresh public HD/metadata verification.
`PUBLISH_ENABLED=false` disables both uploads. A failed companion does not block
long-video publication, and its state never overwrites the long-song history.

To attach a companion to a long run already in progress, dispatch **Independent
portrait music Short** with `source_run` (the numeric GitHub run ID containing
`music-input-<source_run>`) and `parent_run` (its saved song identity). Use the same
values to retry; never change the parent source under a published companion ID.
Long parent IDs receive a stable shortened companion identity.

### Lyric length failure recovery

After a full editorial revision still leaves overloaded phrases or an invalid total,
remaining bounded revisions use a stanza-only schema with 7–8 Hindi words per line.
Repeated choruses are rendered locally. Unaffected stanzas are preserved unless the
whole-song word count needs repair. Meaning, Hindi and rhyme still undergo the
editorial critique; length repair never automatically approves a song.

Rejected runs save the draft and quality report, log structural issues, and publish
a job summary plus `lyrics-recovery.json` with the original run ID and checkpoint
run. Dispatch the updated branch with that `run_id` and `prepared_run` to resume;
GitHub's re-run button uses the old commit and cannot apply a code fix.

For the rejected bus-stop draft from run `41628990806`, the new original recovery
song is `phir-saath-chalein-2026-11-03` in `lyrics/`. It has 183 sung words and passes
written checks. Use a fresh run ID with this authored source; never replace a
saved draft or audio under the previous identity. Listening review remains pending.


### Bounded lyric recovery after run 41669888401

A small CPU text model can return valid JSON and structurally correct lyrics whose
Hindi or rhyme still fails editorial review. Passing unit tests is not proof of
live creative quality. The three editorial attempts remain bounded and rejected
lyrics never become approved merely to keep a workflow green.

When `--check-history` is active and editorial attempts fail, preparation can use
an unpublished, voice-matched original explicitly opted into automatic recovery
in `lyrics/`. The reviewed source must include a matching `song_sha256`; edits
invalidate its review. Historical explicitly selected authored songs are not part
of this pool unless opted in. Title and lyric hashes are checked against the
loaded publication history, and replacement is forbidden if saved audio/video
already exists. A successful replacement saves `lyrics-recovery.json` with source
identity and digest while preserving `song-draft.json` and `lyrics-quality.json`
as the rejected model checkpoint. It does not regenerate packaging with the model.

The initial recovery original is `ab-baat-karein-2026-11-03` (male narrator).
The reviewed catalog is finite: once no unpublished voice-matched song remains,
preparation stops with `reviewed_song_unavailable` and requests a new reviewed
original. It never relabels or republishes an old song. Temporary model/runtime
errors outside lyric quality rejection are not silently converted to new content.
