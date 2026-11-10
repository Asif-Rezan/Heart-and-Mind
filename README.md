# Heart and Mind — Hindi kids rhyme automation

The active generator follows `Asif-Rezan/youtube-motivation-automation` at
`44f8a3384a4e4e02d4f67e94929195cbe225c637`, adapted to Hindi Devanagari.
The original Hindi album implementation is preserved in the rollback tag below.

## Version log and rollback

Original production baseline: `e6bf309529968fc834df14e7414d11061e3b3313`.
Backup/documentation commit: `483d173`. Rollback tag:
`before-hindi-kids-reference-2026-11-09`.

- [Original README and prior behavior](docs/archive/before-hindi-kids-reference-2026-11-09-README.md)
- [Original commit log](docs/archive/before-hindi-kids-reference-2026-11-09-commits.txt)
- [Pinned reference README](docs/archive/motivation-44f8a33-README.md)

To restore the complete original tracked implementation without rewriting history:

```sh
git switch -c codex/restore-hindi-album
git restore --source before-hindi-kids-reference-2026-11-09 -- .
git commit -m "Restore Heart and Mind Hindi album generator"
git push origin codex/restore-hindi-album
```

Merge that restoration branch to make it active again. Code rollback does not
restore credentials, cloud variables, deleted media or already published videos.

## Reference behavior, in Hindi

- Default 240-second episode; 180–300 seconds allowed in five-second steps.
- Original chorus-first song, alternating four-line verses and dance choruses,
  with a fresh Hindi hook, 130 BPM, sweet adult female vocals, immediate opening
  and a short button ending. The pinned ACE-Step CPU backend receives
  `vocal_language=hi`; music remains generated singing.
- The pinned Qwen CPU writer produces Hindi Devanagari lyrics, chorus, title,
  description, story summary and chapter names. Lyrics have bounded word counts;
  failed lines are rewritten with saved accepted content, never clipped or
  replaced with canned English lyrics. Unicode normalization preserves matras
  and nukta for word counting and novelty checks.
- Public long-video and Shorts metadata are Hindi. Only the proper channel name
  `Heart and Mind` and optional `#Shorts` use Latin script. Upload defaults for
  metadata and audio are both `hi`; category, kids and AI disclosures, scheduling
  and resumable publication follow the reference.
- Cute baby animals and two toddler playmates, pastel 3D storybook art, one scene
  every five seconds, 16 landscape and four portrait workers. Thumbnail uses its
  own episode's opening scene; first frames animate that thumbnail artwork.
- Reference character motion, opening punch-in, second dance move per scene,
  face-preserving animation, 1080p landscape/portrait rendering and standalone
  Shorts music are retained. Hindi action words are mapped to motion hints.
- Technical visual descriptions, music-production captions and thumbnail focus
  stay English for the pinned image/audio models; these are not public narration
  or English sung lyrics. Images and thumbnails are text-free as in the reference.

Generative singing, precise pronunciation, character continuity and lyric/audio
alignment still require a finished-video listening/viewing check. Matching the
pipeline does not promise identical generated media or word-level lip sync.

## Destination accounts and storage

The repository remains `Asif-Rezan/Heart-and-Mind`. Existing encrypted Google
secrets and repository variables are not replaced or copied from the reference.
`EXPECTED_CHANNEL_ID` comes only from this repository's secret/variable; there is
no fallback to another channel. Existing OAuth setup remains in
`setup_accounts.py` and the Heart and Mind privacy document is retained/updated.

The existing `heart_and_mind_root=v1` Drive root and original account guard are
retained. New checkpoints/history live in an isolated
`heart_and_mind_hindi_kids_root=v1` child folder, so archived adult-album runs are
not reused, overwritten or mixed with new kids episodes. Use a fresh run ID;
previous album/story drafts are not silently translated.

Optional Facebook publication is disabled unless `FACEBOOK_PUBLISH_ENABLED=true`.
If used, configure this channel's `FACEBOOK_PAGE_ID` repository variable and
`FACEBOOK_PAGE_ACCESS_TOKEN` secret. No reference Page ID is inherited.

## Error handling and model caches

The reference creative pipeline includes the verified operational fixes from the
other destinations: bounded music-quality retries, native audio edge repair,
saved-part recovery, worker memory/time limits, atomic/checksum-verified motion
model downloads and official release/API fallback for HTTP 504. The pinned
llama-cpp-python installer retries official wheels and can compile the same CPU
release from PyPI during a GitHub wheel outage. Bounded runner package setup is
retained.

The existing/free 10 GB cache policy stores SSD-1B, Qwen and motion weights
(approximately 9.15 GiB compressed combined). Keys use exact model revisions and
checksums, shared across runs and image shards; caches save before inference.
ACE-Step's approximately 4.6 GiB archive is left runner-local to avoid evicting
the models used by twenty image workers. Competing pip caches are disabled.
GitHub may expire inactive caches; verified downloads handle misses. No paid
capacity or billing setting is changed.

Source-only legacy projects, obsolete fixed English public metadata and one-off
recovery triggers targeting reference run IDs are excluded from active code.
Original versions remain in the rollback tag/reference archive.

## Generate and verify

Run **Heart and Mind Hindi kids rhyme generation** with a fresh `run_id`.
`AUTOMATION_ENABLED=true` enables the reference's daily 03:00 Asia/Dhaka schedule.
`PUBLISH_ENABLED=true` enables publication, following the reference's first 06:00
New York slot at least 72 hours after upload. The dispatch form can choose
public/scheduled mode and an explicit future publication time.

Use **Verify real Hindi reference episode (no publishing)** to generate a real
Hindi lyric/storyboard/public package on CPU without Drive or YouTube publication.
Use **Verify and warm pinned model caches** for actual model download/cache and
BiRefNet/LaMa inference checks. Component checks include real FFmpeg regression
renders, Hindi language/grammar, vocal-language wiring, metadata, novelty,
checkpoint recovery and guarded publication tests.

For local checks, install `requirements.txt` and FFmpeg, then run:

```sh
python -m unittest discover -v
```

## Migration verification log — 2026-11-09

Migration commit: `3818138` (pinned reference `44f8a33`, Hindi adaptation).

- Local and GitHub [component checks](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42604681632): 227 tests passed, including Hindi guards, native vocal-language wiring and FFmpeg regressions. Actionlint and whitespace checks passed.
- [Camera/background and multiple-character render](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42601202705): passed.
- [Model cache warmup](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42601202709): lyrics, image and motion jobs passed; real BiRefNet/LaMa inference passed. Three model archives are saved under the existing 10 GB quota.
- [Real Hindi CPU preflight](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42601202693): first attempt superseded after a slow verse request; Hindi prompt JSON now retains native Devanagari instead of verbose Unicode escapes. Updated [preflight 42604681634](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42604681634) is running against `1d02052`: all 227 tests passed, the Qwen cache restored successfully, and the real Hindi outline passed on its first attempt. This run was superseded by the metadata field-repair/grammar fixes below; the final real Hindi preflight passed. A finished singing/video quality check remains separate.

The old reference-only motion demo workflow is archived in `docs/archive/reference-dudi-motion-demo.yml.txt`; audio recovery requires explicit destination run IDs instead of stale reference defaults.

No production video has been generated or published as part of this migration verification. A finished Hindi singing/video listening check remains necessary after the first production generation.


## Hindi packaging efficiency fix — 2026-11-09

The first real preflight completed the Hindi outline and both verse chapters,
but metadata validation repeatedly regenerated the entire package for a single
English public field or overlong thumbnail focus. This is a retry-efficiency
problem, not a model-download failure.

Packaging now sends unique verse lyrics once and only the first eight opening
actions for Shorts/thumbnail grounding, instead of repeating 24 long scene
prompts. It retains the full initial candidate before content validation, then
asks Qwen to repair only failed fields. Final Hindi, schema, title/thumbnail and
upload checks remain mandatory. Correct fields are checkpointed in
`package-draft.json` and reused after interruption; no fabricated Hindi fallback
or blind lyric truncation is added. Thumbnail-only repair has an 800-token output
budget and only the opening-scene context. A CPU inference heartbeat reports
liveness every 60 seconds without printing generated content.

Local regression checks: 231 tests passed, including overlong-thumbnail repair,
English-description repair, accepted-field preservation, interrupted metadata
resume and compact episode facts. Real CPU timing is recorded after verification;
a speedup factor is not claimed from mock tests. Hindi preflight is now manual
to avoid launching expensive model inference on every code push, and supports
`source_run` plus `saved_run_id` to reuse accepted lyrics from an earlier preflight.


Public metadata now also uses a compact native Devanagari grammar: ordinary
punctuation/digits and exact `Heart and Mind`/`#Shorts` are permitted, while English
acronyms and hashtags are blocked during sampling. Technical thumbnail focus
remains English. This prevents repeated description repair for English leakage
instead of relying only on prompt instructions. The pinned local llama.cpp
converter successfully compiled this grammar. It avoids large native prose
length expansions; final Python length/language checks still apply.


## Verified Hindi retry improvements and new full run — 2026-11-09

- Field repair/checkpoint implementation: `9af5500`; native public Hindi grammar: `5565a49`.
- Local regression suite: **234 tests passed**. [GitHub component checks](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42611372457) passed.
- Actual same-episode metadata prompt fell from **5,822 to 2,764 tokens** (about 53% smaller). The first package response took **186.3 seconds**, versus **639.8 seconds** in the earlier run; output sizes and sampled text differ, so this is an observed run comparison, not a guaranteed speedup.
- Prompt-only language repairs still leaked Latin text. The compact native public-text grammar then resolved the saved description fields: [real Hindi preflight 42611404651](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42611404651) **completed successfully**, restoring accepted lyrics and metadata from the prior run. The full preflight checks Hindi text, 240-second/48-scene form, chorus-first opening, public long/Shorts metadata and opening-scene thumbnail wiring. It performs no publication or audio/image inference.
- At the user's request, [full production generation 42612096973](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42612096973) was started from `5565a49`, fresh ID `heart-hindi-20261109-01`, female vocal, metadata/audio language `hi`, default 240 seconds and scheduled upload mode. It is in progress; completion/publication and finished audio quality are not yet claimed.


## Publication switch incident and recovery — 2026-11-10

Run `42612096973` successfully rendered the 240-second video and its Short, but
both YouTube upload steps were **skipped**, not uploaded or scheduled. The
repository had only `AUTOMATION_ENABLED=true`; `PUBLISH_ENABLED` was absent.
Facebook jobs were also skipped: there was no Facebook enable variable, Page ID
or `FACEBOOK_PAGE_ACCESS_TOKEN` secret. A job named `publish` succeeding therefore
proved rendering, not platform publication.

`PUBLISH_ENABLED=true` has now been configured. Production/Shorts entry points and
finished-video recovery explicitly reject a disabled publishing switch before
model generation/publication rather than silently claiming success. Dedicated
no-publishing preview workflows remain available. Verified upload receipts show
the YouTube link and distinguish **scheduled, not public yet** from public,
including the release time in Asia/Dhaka. The reference 72-hour/New York 06:00
schedule policy is retained.

Recovery of the saved full video: [42758431952](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42758431952),
source `42612096973`, identity `heart-hindi-20261109-01`. No new AI generation is
needed. The existing Short can reuse its saved portrait/music assets through
Create and publish a rhyme Short with both prepared flags true.

The original baseline tag and all 150 earlier commits were searched: no Facebook
implementation/token reference was found in their Python/workflow files. An older
README explicitly said story automation had no Shorts/Facebook cross-posting.
Git cannot restore an encrypted GitHub secret value. Facebook recovery requires
the intended Heart and Mind Page ID and its Page access token configured in this
repository; no token or Page identity from another channel is copied.

Validation: 239 local tests passed, including disabled production flags and
scheduled/public receipt distinctions; active workflows passed actionlint.
Actual recovery results are recorded after the platform checks complete.

The recovery workflow also uses a per-episode recovery lock. The former
repository-wide generation lock left upload-only recovery pending behind another
episode's expensive synthesis. Recoveries for the same episode remain serialized;
this recovery does not restart or cancel the active daily episode.


Recovery progress: [Short upload 42757383766](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/42757383766)
completed successfully. YouTube read-back confirmed [JI9x3Q4u7WA](https://www.youtube.com/shorts/JI9x3Q4u7WA)
is scheduled for **2026-11-13 17:00 Asia/Dhaka** (11:00 UTC), not public yet.
The full-video recovery uses the current hosted runner pool after the old
ubuntu-24.04 request remained queued with all matching runners busy. Earlier
queued recovery requests `42756811734`/`42757342822` were superseded before upload;
the active request is `42758431952`. No active daily generation was cancelled.

Manual Facebook-only runs now execute an explicit enable/Page ID/token check,
instead of silently skipping the entire job when unconfigured. The Facebook
secret/Page identity is still missing and must be configured before a Facebook
upload can be completed.

Final local validation after the Facebook fail-fast guard: **241 tests passed**; actionlint and whitespace checks passed. Full-video recovery is still queued for a GitHub-hosted runner; no full-video upload is claimed until its platform verification succeeds.


### English family cartoon migration backup — 2026-11-10

Current Hindi rhyme production source is preserved at `56aa49c` and tag `before-english-family-cartoon-2026-11-10`. The complete README is archived at [the pre-cartoon README](docs/archive/before-english-family-cartoon-2026-11-10-README.md). Restore with `git restore --source before-english-family-cartoon-2026-11-10 -- .`, then commit and push the restoration. Credentials, external settings and published videos are not rolled back by Git.
