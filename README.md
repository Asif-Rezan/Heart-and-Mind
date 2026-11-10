# Heart and Mind — English family story cartoons

The active `music.yml` workflow now creates one shared English educational adventure cartoon for children and adults. It replaces the Hindi nursery-rhyme generation path. Narration, natural dialogue, humor, a believable mistake and its consequences carry the lesson; there are no separate child/adult cuts or obligatory dance choruses.

## Version log and rollback

- **Before this migration:** Hindi rhyme production commit `56aa49c`, preserved as tag `before-english-family-cartoon-2026-11-10`. Backup documentation commit `ea190ac` was pushed before implementation.
- [Complete pre-cartoon README](docs/archive/before-english-family-cartoon-2026-11-10-README.md)
- [Pre-cartoon production workflow](docs/archive/before-english-family-cartoon-music.yml.txt)
- The earlier Hindi album baseline remains `e6bf309529968fc834df14e7414d11061e3b3313`, tag `before-hindi-kids-reference-2026-11-09`.

To restore the previous Hindi rhyme implementation without rewriting Git history:

```sh
git switch -c codex/restore-hindi-rhymes
git restore --source before-english-family-cartoon-2026-11-10 -- .
git commit -m "Restore pre-cartoon Hindi rhyme production"
git push origin codex/restore-hindi-rhymes
```

Merge that restoration branch to activate it. Git restores tracked source, not credentials, repository variables, deleted cloud media or published videos.

## Current generation flow

1. The pinned Qwen CPU model writes an original English outline and twenty sequential shots, in five checkpointed batches. Each shot contains one speaker, complete spoken text, a matching illustration, emotion and a grounded action. Accepted batches survive interruptions. Duplicate dialogue, missing cast, invalid word counts and mismatched resumed requests stop clearly.
2. Kokoro 82M synthesizes three stable American English voices on CPU: narrator `af_heart`, Mira `af_bella`, Theo `am_michael`. These are natural adult synthetic voices. Model revision `f3ff3571791e39611d31c381e3a41a3af07b4987` and library `0.9.4` are pinned. Weights and voice packs use that exact revision, with a shared GitHub Actions cache.
3. Speech is measured before illustration/animation. Every scene gets its own frame-aligned duration and short reaction space. Complete narration is retained; speech is never forced into the old five-second rhyme slots. The writing target is 2–3 minutes; accepted complete media must be 2–5 minutes and each shot at most 25 seconds. Out-of-range/silent speech is rejected rather than clipped or silently replaced.
4. An original, evolving synthesized instrumental score sits quietly beneath the voices, with optional gentle discovery/footstep cues. This score uses local synthesis, not ACE-Step singing or downloaded stock songs. Spoken pauses are intentional and do not use the old music-only silence rejection rule.
5. Twenty parallel CPU illustration/motion shards create the story's settings and fixed recurring cast: Mira in a teal jacket and Theo in an amber vest. Approaching a waiting friend, following a leader and approaching a visible ball are explicit actions. Other shots use restrained reaction/idle movement. Cast geometry and available space bound travel; characters do not drift simply because a shot needs motion.
6. Cutout acting runs once over the actual spoken shot duration, with gentle camera movement and conservative blinks. Assembly blends a held outgoing frame into each incoming shot over 160 ms, preserving all dialogue timing. Output is 1920×1080 with AAC speech/music. Thumbnail uses the actual opening scene.
7. Existing Heart and Mind account verification, Drive backup, resumable YouTube upload and verified publication receipts are reused. Metadata/audio language are English; category is Film & Animation. The previous scheduled publication policy and audience/disclosure settings remain in place. Rhyme Shorts are not automatically generated from cartoon dialogue.

This is narrated cutout animation, not full 3D acting or phoneme lip-sync. Expressions largely come from scene illustrations; uncertain face rigs are left untouched. A scene with an unusable segmentation mask falls back to camera motion and records that fallback. Prompted clothes/faces improve continuity but do not guarantee identical generated characters. Left/right cutout geometry grounds interactions; the engine does not recognize character names from pixels or synthesize physical handovers/pickups.

## Run or resume

GitHub Actions → **Heart and Mind English family cartoon** → **Run workflow**:

- `run_id`: a fresh identity such as `cartoon-map-20261110-01`.
- `topic`: the shared story theme; default is a funny misunderstanding resolved through cooperation.
- `upload_mode` / `publish_at`: existing scheduled/public controls.
- `prepared_run`: optional numeric ID of a previous **cartoon** run. Reuse the same `run_id` and topic; expired/mismatched artifacts fail clearly. The story/speech checkpoint and available matching image shards are restored; matching audio/clip hashes avoid repeated inference. Hindi rhyme checkpoints belong to the archived generation path.

Partial story, speech, image/motion and publication diagnostics are uploaded even when a stage fails, retained for seven days. Kokoro candidates are validated before becoming reusable speech checkpoints. Encoder output is committed only after duration/frame checks. Failed YouTube uploads retain the existing ambiguous-upload guard, so retries cannot blindly duplicate a video.

For local development use Python 3.12, FFmpeg/ffprobe, espeak-ng, the base requirements and the stage-specific requirements. `requirements-cartoon.txt` pins Kokoro and explicitly installs its English pronunciation model. The workflow installs CPU PyTorch separately and verifies regression tests before model generation. Run `python -m unittest -v` and actionlint before pushing.

## Accounts, caches and legacy tools

Repository and destination remain `Asif-Rezan/Heart-and-Mind`; no other channel's credentials or Page token are copied. Existing `PUBLISH_ENABLED`, `AUTOMATION_ENABLED`, Google secrets and channel verification still apply. Facebook remains optional and requires this project's Page ID/access-token configuration. Changing the cartoon format does not configure that missing account connection.

The existing lyrics/image/motion model caches are retained, with a small additional Kokoro cache. Repository cache quota stays at the owner-approved 10 GB; eviction can cause a future download. No ACE-Step model is needed by the active cartoon workflow. Manual Hindi/Shorts/recovery tools remain for old content; they do not define the new daily cartoon format. Use the active workflow with `prepared_run` for cartoon generation recovery.

## Validation for the migration

Real Kokoro synthesis was exercised for all three selected voices. Regression coverage includes checkpointed story resumption, English/cast guards, corrupted speech recovery without regenerating accepted shots, silence rejection, sample/frame-aligned audio mixing, grounded action selection, variable-length actor rendering, and real FFmpeg assembly/decode of a complete 140.8-second test timeline with transitions. A generated episode still needs a finished-video viewing/listening check for creative quality and factual accuracy.


### 2026-11-10 — English outline punctuation regression

First cartoon run `42793148672` stopped during outline creation: `summary` failed an ASCII-only pattern three times. That pattern also rejected English paragraphs and typographic quotes/dashes. English story fields now accept whitespace, Latin characters and common Unicode punctuation, while retaining string/word-count bounds and excluding other writing systems/control bytes. The saved schema validator remains active; no story is substituted or truncated. A regression exercises multi-paragraph English with curly quotes, an apostrophe and an em dash through the real request/validation path without model retries, and rejects Hindi, Chinese and NUL input.


### 2026-11-10 — restore twenty parallel workers and post-publication cleanup

New episodes have twenty story shots and a twenty-worker image/motion matrix with `max-parallel: 20`. Each worker generates and animates one shot. Existing accepted sixteen-shot checkpoints remain compatible. YouTube publication waits for every image worker; the original guarded Drive cleanup sweep runs after successful publication and shares the existing cleanup lock. Scheduled/private/not-yet-HD videos remain in Drive until the hourly verified-public sweep makes them eligible. Actual simultaneous execution still depends on GitHub's account-wide runner capacity. Already running workflows retain their original commit and worker count.
