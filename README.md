# Heart and Mind — daily Hindi emotional motivational stories

The active pipeline creates one original Hindi emotional motivational story each day for the existing Heart & Mind channel `UCDTjTh7ORO2J_5OrR0dESTQ`. New releases use `short-story-v2`: **4–6 minutes (240–360 measured seconds), one narrator, a different story image every four seconds**. A final partial image interval ends with the audio.

## Background-image video only (2026-11-01)

At the owner's request, the active pipeline now uses **only story-specific AI background images with camera motion**. Python puppet rigs/rendering, animation preview scripts/workflow/assets, daily style rotation and the style selector have been removed. `story_video.py` and the daily workflow use the original pinned SSD-1B image renderer again. The faster planning and checkpointed repetition fixes below remain active.

The version immediately before removal is preserved by [`checkpoint/before-removing-puppet-2026-11-01`](https://github.com/Asif-Rezan/Heart-and-Mind/tree/checkpoint/before-removing-puppet-2026-11-01), commit `58bf231`. The original pre-puppet version remains available at [`checkpoint/pre-puppet-animation-2026-11-01`](https://github.com/Asif-Rezan/Heart-and-Mind/tree/checkpoint/pre-puppet-animation-2026-11-01), commit `338dc40`. For a separate local inspection branch, use `git fetch origin --tags` and `git switch -c inspect/saved-version CHECKPOINT_TAG`. No force-reset of shared history is needed.

## Hindi narration delivery update (2026-11-01)

The owner listened to the same Hindi paragraph spoken by Kokoro `hm_omega`, Goonj Hindi Ravi and Goonj Hindi Atul, and selected **Kokoro — sample 1**. Production therefore keeps `hexgrad/Kokoro-82M` / `hm_omega`; the song-era ACE-Step model continues to generate music, not spoken narration. [Kokoro voice documentation](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) describes the limited Hindi training and short-utterance weaknesses, so naturalness still needs listening review.

Short-story speech now starts at native speed **1.0** and retains an in-range result. If narration falls outside 4–6 minutes, retries stay within **0.90–1.08** and target the closest duration boundary with margin. There is no post-generation time stretching, looping, voice switching or silence padding to manufacture minutes; an unsuitable script still fails rather than force an unnatural delivery. Actual scene timing always comes from generated samples.

The joiner removes only excessive model edge silence, preserves 100ms leading / 160ms trailing context around detected activity and applies 5ms edge fades. Scene pauses are shorter (80ms), questions/exclamations get 120ms and chapter boundaries 280ms; no extra pause is appended after the final scene. Word coverage, finite/non-silent waveform checks and per-scene checkpoints remain enforced. Story prompts also request idiomatic conversational Hindi, consistent name spelling and complete spoken sentences using existing model calls, with no extra planning review loop.

Voice cache identities now include the engine/model/revision, stock voice, speech processing version and rate. `voice-profile.json` locks one selected profile for a run. New runs can explicitly set repository variables `STORY_VOICE_ENGINE=kokoro` and `STORY_NARRATOR_VOICE=hm_omega`; these are the defaults. Experimental `goonj` / `hi_ravi` or `hi_atul` is opt-in, pinned to revision `7056ccc1a0b58beaad09fe2057730545d74261cb`, and never substituted automatically. Its [model card](https://huggingface.co/BH-Builds/goonj-1-82M) documents synthetic training and inherited pronunciation limitations. These samples do not prove a new model is universally more natural.

The **Hindi narration voice comparison** workflow is manual and publishes no video. [Verified run 41299328920](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41299328920) generated all three CPU samples successfully in 2m 13s. Download `hindi-narration-comparison` for the identical script, native-speed / loudness-matched WAVs and hashes; no music masks the voices. Reproduce locally with `python preview_story_voice.py` after installing the voice dependencies. The pre-change production version is saved at [`checkpoint/before-hindi-voice-upgrade-2026-11-01`](https://github.com/Asif-Rezan/Heart-and-Mind/tree/checkpoint/before-hindi-voice-upgrade-2026-11-01), commit `a991a5a`.

## Current story, voice and artwork contract

- **Engagement structure:** first two short beats open on an immediate dilemma or unanswered question, without a greeting/intro or ending spoiler. Later chapters develop causal choices, new information and earned stakes. An earlier detail pays off at the resolution. Only after that payoff, the final one or two beats invite a specific reflective comment and optionally a brief follow. One full-script editorial review creates a **fixed correction plan** against the canonical cast/summary. Corrections run in batches of at most two scenes, with two attempts per pending batch. Every accepted edit is checkpointed; later model opinions cannot reopen completed work. New text must be Hindi, change the selected line, avoid repeated substantial sentences and preserve the 520–720-word budget. A closing viewer-comment CTA is checked directly even when the model calls it present. Incomplete edits stop with `editorial_edit_incomplete` and pending indices; impossible empty progression plans stop early with `editorial_plan_incomplete`. Completion records validated edits, not an audience quality score. These checks cannot guarantee engagement or retention.
- Qwen3-4B writes six chronological chapters / 48 short narrative beats, about **520–720 Hindi words** total. One `hm_omega` Kokoro narrator speaks all lines. Narration and quoted dialogue must not echo the same event. Exact repeated sentences and substantial near-duplicates are repaired against the complete story, then rejected if they remain. Speech chunks are submitted once; the synthesis output text must cover the input exactly. This catches text echoes, not every possible acoustic pronunciation or repetition defect; listening review remains necessary.
- The complete, uncut narration must measure 240–360 seconds. Native speed starts at 1.0 for short stories; bounded 0.90–1.08 native-rate retries only recover an out-of-range result instead of forcing every story to five minutes. Mixing, rendering and publication enforce that same measured range; speech is never looped, padded to fill minutes or cut to fit. Three independent 120-second ACE-Step instrumental score jobs cover the maximum six minutes. Their prompts share an understated motif, 78 BPM and a D major/B minor palette, and use the actual story summary: curiosity at the opening, developing tension/turning point in the middle, hopeful payoff at the end. Each source is trimmed to one third of the measured story so the final musical section is heard even in four-minute videos. Short section fades soften joins; music is normalized to -23 LUFS before mixing and narration to -16 LUFS. A 0.50 music gain plus speech-driven ducking keeps the narrator dominant; final limiting controls peaks. Shared prompts do not guarantee identical motifs across independent generations, and listening review is still required.
- After final prose repairs, a separate visual planning pass reads the final narration plus canonical cast/world. Every image prompt identifies the actual action, story prop, setting and fixed visible age, hair and clothing. No generic mood-only picture substitutions. The visual plan and selected thumbnail beat are saved in the story manifest.
- Images wait for measured speech timings. Every four-second display interval selects the spoken beat occupying most of that interval; **60–90 images** cover a complete episode (the last interval may be shorter). Adjacent views alternate wide/medium composition while retaining the current story action. Rendering uses this display timeline rather than holding a single picture for a whole narration segment.
- SSD-1B uses the existing pinned public weights on CPU. All image workers reproduce the same episode-specific cast reference seed/prompt. Scenes use that reference through image-to-image conditioning (strength 0.80), together with their specific story action and consistent 3D storybook style. Reference conditioning improves continuity but does not guarantee identical faces or perfect semantic matches. Generated pictures still require visual review. Safety retries retain the requested story action rather than substitute an unrelated portrait. Negative prompts no longer suppress elderly characters when a story calls for them.
- A **separate thumbnail prompt and image-generation pass** recompose the selected main conflict/meaningful choice for mobile readability: one dominant expressive face, the central story object, bright face lighting, bold complementary colors and an uncluttered background. The prompt uses the same canonical cast, real event and setting, with the episode reference image; it must not invent events or danger. The dedicated source is fitted to 1280×720. It is not the opening frame. Prompt/seed/reference/source-scene metadata are recorded separately. This is designed for clarity and click appeal; CTR improvement requires actual audience data.
- **Entertainment category 24** is explicitly sent and verified on new uploads; Education/Academic system/Bangladesh metadata is not submitted. A separate SEO completion reads the final script and writes a specific Hindi title plus one relevant search phrase, a story-specific opening description/synopsis/lesson and 8–12 Hindi/Romanized Hindi/English tags. Tags are deduplicated and budgeted conservatively below the YouTube limit. Claims about true events, celebrity associations, popularity, cures and guaranteed results are forbidden. Packaging is checkpointed separately from narration; search visibility/CTR are not guaranteed.
- Existing AI disclosure, channel safeguards, private Drive backup, duplicate-upload recovery and verified-public cleanup remain in place. Saved legacy eight-to-twelve-minute releases retain their recovery contract; the primary generation workflow requires a new short-format identity rather than regenerate a legacy long video.

Production order: canonical outline → six chapter workers → story/repetition/visual-plan validation → narration and three score workers → **17 combined image/render workers** after measured narration; audio mixing runs separately → verified join/publication → Drive cleanup. Each image is rendered immediately on its own worker, removing the full-image-matrix barrier, 18 separate renderer setups and repeated artifact downloads. Three concurrent score workers plus 17 image/render workers peak at **20 generation jobs**; mixing becomes eligible only after the three score jobs finish. Other repositories/workflows share account runner availability and can still cause queueing. A workflow graph already dispatched stays on its original commit; this topology applies to new dispatches. Generation has not been restarted as part of this update.

## Validation and rollout

The failed plan in run `41285860535` exhausted three changing editorial judgements, then hid the reason behind generic `ValueError`. The fixed plan replaces that moving review loop, migrates saved repaired prose, bounds overlong English editorial instructions before strict schema validation, and preserves the raw response for diagnosis. All model requests log their checkpoint label at start and a heartbeat every 60 seconds. Outline summary/cast/world/chapter planning must be English (speech/title/description remain Hindi), catching the wrong-language planning shape before chapter generation.

Chapter 6 of run `41291878710` returned English narration for all eight `text` fields on six attempts. Story requests now distinguish spoken `text` (Hindi Devanagari) from English planning keys at the system/schema level. Rejected English drafts are checkpointed and corrected using text-only translation batches of at most four; valid visuals, other scenes and completed chapters are preserved. Each pending scene gets at most two language corrections per explicit recovery. Persistent wrong language, invalid structured output and model/runtime failures have separate safe error codes/messages; runtime failures are not retried as prose errors. The lower-level JSON retry also explicitly requires Hindi for spoken `text`, not only song lyrics.

Run `python -m unittest -q` and `actionlint` before rollout. Short-format coverage includes duration endpoints, cross-scene/within-scene echoes, missing/duplicated synthesis text, time-to-story mappings, shared image references, visual-plan checkpoint reuse and thumbnail selection. A real FFmpeg smoke test renders four minutes with alternating image colors and checks frames around the four/eight-second cuts plus the dedicated thumbnail source. These controlled checks do not establish production AI image quality or human listening quality.

## Faster planning and repetition recovery (2026-11-01)

[Story run 41293514297](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41293514297) completed all six chapters but failed assembly with `repeated_story_lines` after 53m 11s in the generation step. Its three repair responses returned the exact same scene 36–38 narration, which the previous repair loop accepted until the final validation failed. No narration, music, rendering or upload ran.

Repetition repair now rejects unchanged/near-duplicate/newly duplicated prose immediately, feeds back the rejected reason and already narrated lines, and checkpoints each accepted scene. Batches contain at most two scenes, with at most two attempts per unresolved batch per explicit recovery. Saved accepted repairs are reused, while an unresolved result reports pending indices and rejection reasons. Hindi, full-story word-budget and closing-CTA checks remain enforced.

CPU requests now carry the canonical plot/cast plus relevant final neighboring beats. Editorial edits and visual batches no longer resend all 48 visual descriptions; the full-script audit and thumbnail selector retain all spoken beats without redundant visuals. Using the actual failed script, the first repetition request fell from **16,386 to 2,643 characters (84% smaller)**; the first visual request fell from **11,540 to 2,717 (76% smaller)**. These are measured prompt sizes, not a promised wall-clock speedup. Request logs now include prompt character/token counts alongside inference time.

Live recovery [run 41298591612](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41298591612) reused the six completed editorial edits and repaired scenes 36–38 successfully. Its three repetition requests reported 93.3s + 37.2s + 41.0s = **2m 51.5s**, compared with 900.2s + 65.9s + 65.3s = **17m 11.4s** for the three failed old requests. This comparison covers those inference requests only, excludes setup/model download, and is not a full-pipeline duration claim. SEO/visual planning continues separately in that run.

The **Recover and time saved story planning only** workflow accepts the exact `run_id` and previous `prepared_run`, restores its `story-input` checkpoints, resumes assembly and writes measured seconds to `planning-preview.json`. It requires a saved outline, uses no Google credentials, and does not generate audio, render or publish. Its new `story-input-RUN_ID` artifact can subsequently be resumed by the normal story workflow, which performs the usual private-history/channel checks.

## Earlier implementation and recovery history

The following records describe previous releases and incidents, not the current short-format specification.

## Parallel jobs and the failed outline fix

Parallel/validation update commit: `acce1c7a3b9cdd707cb5cc78f9f262bfcf7e7b35`. Previous story version: `f04ba246c1136689b3277a19b885d402d6ef7465`. The original song rollback point below is retained.

Run [41050567153](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41050567153) failed before image/voice/music generation: Qwen produced a `summary` longer than the 700-character limit on three attempts. The old inference validator rejected it before the writer could save or normalize the outline.

Story-specific inference now relaxes only the maximum lengths of **planning prose** (title, description, summary, character/world descriptions, chapter beats and scene visuals). It saves the raw valid JSON first, bounds those fields at sentence/word boundaries, then runs the original strict schema. Spoken Hindi text is never truncated by metadata normalization; narration/dialogue limits and incremental repairs are described below. Missing fields, wrong array sizes, invalid speakers and bad Hindi still fail validation. Tests reproduce the actual long-summary failure and verify that it passes after normalization in one inference response. Raw outline/scene responses and safe chapter validation counters are checkpointed for diagnosis/recovery.

The production dependency order is:

1. Canonical outline → **six chapter jobs in parallel** → validate/reserve the complete 48-scene story.
2. **18 image jobs, one Kokoro voice job and six ACE-Step score jobs** become eligible together; score generation no longer waits for voice.
3. **18 scene-render jobs** run after pictures and measured voice are ready, without waiting for music. Each job renders its own two/three scenes. Audio mixing independently waits for the voice and six score parts.
4. Publication waits for rendered scenes and mixed audio, verifies clip fingerprints, joins them without re-rendering, and applies the existing duration/channel/upload guards.
5. **Drive cleanup** appears separately after **publish** in the graph. Publishing uses `--defer-drive-cleanup`; the cleanup job independently rechecks public HD ownership/metadata and removes only the verified story media. Cleanup failure has its own status and does not turn an already successful upload into a failed publish job. The recovery workflow also has a separate cleanup job after publication recovery.

Image/render matrices explicitly allow up to 18 jobs; chapter/music matrices allow six. GitHub account concurrency and available runners can queue jobs, so these are parallel job requests, not a promise that every job starts simultaneously. Completed chapter, image, music-part and rendered-clip checkpoints can be reused on recovery. Each cache is bound to its canonical story/image/timing inputs. A missing or stale part stops joining rather than silently substituting content.

Corrected production run: [41075270533](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41075270533), dispatched on the fixed main commit using the same daily identity and the failed run checkpoint. Its live outline step passed on the first inference attempt (1,957 completion tokens, 286.5 seconds), and all six chapter jobs started in parallel. Five subsequently failed the former per-scene word/speaker-count policy; the incremental scene repair below replaces that policy. No final video/publication was produced by this run.

For the fixed code, start a **new workflow dispatch on main** with the failed identity `story-2026-10-30` and `prepared_run=41050567153` to reuse any available checkpoint. Re-running the old run directly executes its old commit and cannot apply this fix.

## Assembly word-budget recovery

Individually valid chapters can still produce a complete script outside the required 1000–1600 Hindi words. Assembly now requests targeted prose revisions in batches of up to eight scenes, preserving speakers, visuals and the canonical outline. Only valid Hindi revisions that move the total toward the accepted range are saved. Every gain is checkpointed directly in its chapter before another model request; an interrupted dispatch can reuse those chapters. Already valid complete scripts do not invoke the model.

Repair is bounded to twelve requests per invocation. Invalid JSON/schema responses and text-generation errors retry with new seeds. Safe word counts and request counters are stored in `story-budget-repair.json`; raw responses are saved separately. Exhausted recovery reports `story_budget_repair_incomplete` and retains checkpoints. Identity, originality, measured speech duration and publication checks still apply. The assembly worker installs the CPU text runtime and allows time for repair.

Run [41254730257](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41254730257) was verified using its downloaded assembly checkpoint: its six valid chapters contain 123, 120, 149, 157, 104 and 127 words (780 total). Replaying assembly reproduces the 1000–1600-word validation failure. A regression replays these exact per-scene counts with synthetic prose and verifies bounded recovery. Word-budget validation now emits the safe `story_word_budget` code and actual/required counts instead of an opaque generic ValueError. To recover, dispatch a **new** workflow on the updated code with `run_id=story-2026-11-01` and `prepared_run=41254730257`. Re-running the original job uses its old commit. Live model/video generation still requires workflow verification.

## Chapter scene repair and recovery

The chapter jobs in run `41075270533`, including jobs `124132552574` and `124132552934`, repeatedly regenerated all eight scenes when any scene missed the old 23–31-word window or the model returned the wrong narrator count. Valid prose was lost on each retry.

The chapter writer now determines the eight scene slots and six narrator/two dialogue roles **before requesting prose**. The response schema contains only the requested `scene_N` text/visual slots, with no model-controlled speaker labels. A model therefore cannot miscount or reassign the role layout. Existing complete verified chapters are reused exactly. Legacy raw drafts are salvaged only where the prose is valid and matches the chosen role; mismatched dialogue is rewritten as narration, never silently relabeled.

Natural short Hindi sentences have no arbitrary per-scene word minimum. Speech must be nonempty Hindi and at most 400 characters. Long speech is split at word/sentence boundaries for Kokoro without changing or dropping words. The complete 48-scene story must contain 1,000–1,600 words; individual chapters may vary naturally in length. Actual Kokoro and final video measurements must still be 480–720 seconds; those guards and the native-speed bounds are unchanged. No filler, truncation, silence padding or looping substitutes for proper story writing.

Only missing/invalid scene slots are requested again. Accepted paragraphs checkpoint immediately in `chapters/progress-N.json`, tied to the run and canonical outline hash; interrupted/exhausted retries keep those paragraphs and resume with new seeds. A complete valid chapter is never rewritten to satisfy a local word quota; the complete story is validated during assembly. Requests are bounded to six per invocation, with safe counts/reasons in diagnostics and raw response checkpoints. Local sequential preparation and production parallel chapter jobs use this same writer.

Regression tests replay all six production word-count/speaker patterns using deidentified prose: all accepted scenes are retained, and the already successful chapter is unchanged. They verify speaker-by-construction schemas, accepted-scene preservation across retries, changed-outline rejection, short dialogue, and metadata bounds that never alter speech. These are controlled regression checks; live model repair/publication status is recorded separately.

Chapter repair implementation commit: `c98f6bba30dffbd6e8482db59b329d3b7cfe26e9`. Recovery run [41081794480](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41081794480) was started on the new code with the saved daily identity. Four chapters passed; two failed because natural 15–17-word narration was rejected. The follow-up removes that per-scene quota and can recover saved valid responses without model calls. Full story/video/publication has not yet been verified.

Follow-up fix `8e44ce7a2d0259659ac3d3cc5035271d59a03ca3` passed 110 local tests and workflow lint. Recovery run [41084457350](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41084457350) starts from `main` using checkpoints from `41081794480`, with the same story ID. Actual failed chapter 6 recovered locally without any model call (210 words); chapter 5 then failed its unnecessary local word quota: all eight scenes were valid but only 137 words.

The next fix removes chapter-level word rejection and budget-driven rewrites while keeping the full-story 1,000–1,600-word validation and measured 480–720-second audio/video gates. Replay of the actual run artifacts recovered all six chapters and assembled 48 scenes / 1,174 words with **zero model calls**. A regression covers the exact failed 137-word checkpoint and confirms no retry or prose replacement. All 111 tests and workflow lint pass. Publication remains unverified.

Recover on the new main code using `run_id=story-2026-10-30` and `prepared_run=41075270533`. This reuses the saved outline, successful chapter and failed raw drafts. Re-running the old workflow itself would execute its old code.

## Visible Drive cleanup job

New workflow runs show **publish → Drive cleanup**. Preview-only runs (`PUBLISH_ENABLED=false`) skip cleanup. Failed, unverified or non-public uploads cannot be cleaned. A successful cleanup marks the saved story publication complete and uploads a small `story-cleanup-RUN_NUMBER` report; scripts/history/publication journals are retained. Re-running a failed cleanup re-verifies YouTube and resumes the exact-ID deletion journal, without generating or uploading another video. Local `daily_story.py --stage publish` continues to clean immediately unless `--defer-drive-cleanup` is provided.

A workflow graph is frozen at dispatch: the already-started run `41075270533` uses its original workflow and performs cleanup inside publish. Its graph cannot acquire the new job; the separate job appears on newly dispatched/daily runs. That running generation is not restarted just to change its graph.

For cleanup-only recovery of an existing public story, run `python story_cleanup.py --run-id ORIGINAL_STORY_ID` with the existing Heart and Mind credentials, or re-run the failed cleanup job. The **Recover existing Hindi story publication** workflow likewise shows **recover → Drive cleanup**.

## Daily operation

Active workflow: [Daily Heart and Mind Hindi motivational story](.github/workflows/stories.yml).

- **03:00 Asia/Dhaka every day**, cron `0 21 * * *` UTC, preserves this repository's current generation time. Existing `AUTOMATION_ENABLED=true` was verified on 2026-10-30.
- **Public release after generation/upload**, preserving Heart and Mind's existing publication behavior. No New York release rule or 72-hour delay is introduced. CPU generation/runner queues can take time and failures can leave gaps; a scheduled start does not guarantee an exact completion time.
- Automatic publishing remains on by default, just as in the old Heart workflow. An optional explicit repository variable `PUBLISH_ENABLED=false` produces previews without upload; an absent variable does not disable publishing.
- Run the story workflow manually for an immediate start. Empty `run_id` becomes `story-YYYY-MM-DD` using the Dhaka date. To resume an interrupted story, supply its original `run_id` and previous numeric STORY workflow run as `prepared_run`; never restore a song/kids workflow as a story. Artifacts expire after seven days; the reserved script remains in Drive.
- **Recover existing Hindi story publication** reconciles only an existing uploaded story run ID. It never generates or inserts another video.
- The former daily song workflow is commented and archived, outside the active workflow directory. Its existing manual music artwork/cleanup tools remain available. New story automation has no Shorts/Facebook cross-posting jobs.

Local commands (install the workflow's stage-specific CPU dependencies, models, `espeak-ng` and FFmpeg):

```sh
python daily_story.py --run-id story-example --stage plan --check-history
python daily_story.py --run-id story-example --stage voice
python daily_story.py --run-id story-example --stage images
python daily_story.py --run-id story-example --stage music
python daily_story.py --run-id story-example --stage render
python daily_story.py --run-id story-example --stage publish
```

For a local script preview without Google credentials, omit `--check-history`; production always reserves/checks private history. References: [Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M), [Hindi voices](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md). Existing source/weight pins are recorded in `story_music_cpu.py` and `story_image_cpu.py`.

## Validation

- Local Python 3.12: **111 tests passed**, including all original Heart music tests and new story checks for Hindi/length, saved-script resumption, duplicate detection, continuous timing, public Hindi metadata, exact Heart channel rejection, instrumental CPU/no reference requests and cleanup isolation.
- All active workflows passed actionlint 1.7.12. The new regression suite runs in CI and before production outline generation, including workflow dependencies, exact 18-worker image coverage/cache reuse and independent chapter assembly. CI explicitly installs FFmpeg for real six-part audio mixing and parallel clip-joining checks; those two media checks also passed locally and are skipped only when FFmpeg is unavailable.
- Actual Kokoro CPU Hindi synthesis succeeded with all three configured voices on the same sample: `hm_omega` 11.12 seconds, `hm_psi` 11.22 seconds, `hf_alpha` 10.47 seconds. The reused voice module is unchanged from that runtime check; this does not establish subjective speech quality.
- Full 48-scene synthetic Hindi speech fixture: actual Kokoro CPU output measured **539.34 seconds (8m 59.34s)** at native speed 0.95, with all scene timings. This validates the full narration path on test text, not a newly written production story.
- The measured scene renderer was exercised with a synthetic 480-second audio/video smoke test. It verifies the media path and timing, not generated image/story/music quality. No full generated story or successful publication is claimed by these component checks; see the actual production run.

First Heart and Mind production run: [41050567153](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41050567153), dispatched on main on 2026-10-30. It failed at outline summary length validation; the corrective changes and recovery procedure are documented above. No completed production story/upload is claimed by this failed run.

## Saved Heart and Mind music version and rollback

Saved before this change on **2026-10-30**:

- Repository: `Asif-Rezan/Heart-and-Mind`.
- Story migration commit: `97b158e6d61f811d97b048bfd1182e0dfff20944` (`Add daily 8-12 minute Hindi motivational stories to Heart and Mind`).
- Full original commit: `0fca9240b5edf786f09a806401a62dcc386eb0f6`.
- Commit: `Generate text-free cinematic couple thumbnails and richer song backgrounds`.
- Backup branch: `codex/archive-heart-music-20261030`.
- Exact tracked source snapshot: [`legacy/hindi-music/`](legacy/hindi-music/), including the original README, scripts, tests, assets and workflows. Original root song modules stay intact for shared infrastructure and manual recovery; new story functionality lives in separate `story_*` modules and `daily_story.py`.
- Old daily workflow retained **commented out** at [`.github/music-hindi-songs.yml.commented`](.github/music-hindi-songs.yml.commented), outside `.github/workflows/`, so it cannot trigger alongside stories. Python is archived executable rather than commenting every line and damaging the rollback source.
- [Full saved 40-commit log](docs/hindi-music-commit-log.txt).

Inspect the exact old version in another checkout:

```sh
git fetch origin
git worktree add ../heart-music-saved origin/codex/archive-heart-music-20261030
```

Restore it as a new reversible commit, from a clean checkout:

```sh
git fetch origin
git switch -c codex/restore-heart-music origin/main
git restore --source=0fca9240b5edf786f09a806401a62dcc386eb0f6 --staged --worktree -- .
git commit -m "Restore original Heart and Mind music automation"
git push -u origin codex/restore-heart-music
# Review and merge this branch into main to reactivate the old daily song workflow.
```

No reset or force push is required. Git rollback restores tracked code, not repository variables/secrets, uploads or private Drive data; review those separately. In-progress runs execute their original commit. No new credentials or channel changes are needed to restore the old version.

Recent commits at the saved point:

```text
0fca924 | 2026-10-28 | Generate text-free cinematic couple thumbnails and richer song backgrounds
22f8214 | 2026-10-28 | Merge pull request #22 from Asif-Rezan/manual-vocal-choice
bd6bc80 | 2026-10-28 | Allow one-off vocal choices without changing the daily rotation
4e03cea | 2026-10-28 | Merge pull request #21 from Asif-Rezan/alternate-daily-vocals
2926ba5 | 2026-10-28 | Alternate male and female lead vocal directions by Bangladesh calendar day
5d58db9 | 2026-10-28 | Merge pull request #20 from Asif-Rezan/brighter-vintage-poster-artwork
4680d2a | 2026-10-28 | Generate complete thumbnail lettering inside the image model without overlays
51984b3 | 2026-10-28 | Keep poster titles clear of detected faces and strengthen display lettering
2b7985d | 2026-10-28 | Use bright colorful album posters for thumbnails and video backgrounds
e4417e0 | 2026-10-27 | Brighten vintage artwork and prioritize clear poster portraits
6557273 | 2026-10-27 | Merge pull request #19 from Asif-Rezan/full-bleed-vintage-thumbnail
a02703a | 2026-10-27 | Make vintage thumbnails full bleed with only the Hindi song title
527ef60 | 2026-10-27 | Merge pull request #18 from Asif-Rezan/fix-vintage-couple-panel
ef1d41f | 2026-10-27 | Preserve both faces in thumbnail panel and allow fast demo recomposition
b4d06f4 | 2026-10-27 | Merge pull request #17 from Asif-Rezan/vintage-monochrome-thumbnails
```

## Historical Hindi music README

The following is preserved as historical documentation of the saved song version. Use the story instructions above for the active daily automation.

---

# Heart and Mind — Hindi Music Automation

All AI inference and video rendering run on standard **GitHub Actions CPU runners**. There is no hosted Hugging Face Space, ZeroGPU call, Groq key, remote music API, GPU rental, or self-hosted runner requirement. Public model weights are downloaded anonymously; downloads do not perform remote inference.

## Workflow

The generation flow is restored from successful run **#14**, commit `dba31ba`. Music synthesis, image generation, rendering settings and model revisions match that run. There is no lyric-transcription job, five-second storyboard or image-shard matrix. The music and images jobs run in parallel. Run #14 completed in 46m 10s; that is a measured example, not a guaranteed duration.

1. **Lyrics job:** original Hindi Devanagari lyrics and metadata using the same pinned Qwen3-4B CPU model as [Rezan After Dark](https://github.com/Asif-Rezan/Rezan-After-Dark).
2. **Music job:** ACE-Step 1.5 `acestep-v15-turbo` runs directly on the GitHub CPU. Hindi vocals, one complete 180–360 second song, eight diffusion steps. Optional ACE-Step planning LM is disabled because lyrics and the musical prompt are already supplied.
3. **Images job (alongside music):** the reference project’s pinned `segmind/SSD-1B` diffusion model generates two fresh song-specific images on CPU: a cinematic background and a separate expressive thumbnail scene. Qwen writes both visual prompts from the song’s story; seeds differ by lyrics and image purpose.
4. **Publish job:** measure the real audio duration, render a 1920×1080 branded waveform video and thumbnail, back up privately to Drive, upload publicly to the exact Heart & Mind channel, and verify actual public visibility and HD processing.

Songs are never looped or padded to meet the duration requirement. Artwork is generated anew for each song, never selected from a shared image library. Romantic and separation thumbnails feature beautiful South Asian adult couples aged 25–35, with distinct expressive faces and a clear emotional moment. Healing songs may feature one hopeful young adult female lead. Both generated sources are text-free: Hindi, Romanized Hindi and English lettering are suppressed, and no title, badge or logo is added to the thumbnail. The video uses its own colorful generated scene with a low-positioned waveform.

Lyrics run first; music and images then run on separate CPU workers; publishing waits for both. Only publishing and cleanup receive Google credentials. The image job has a 120-minute deadline and 12 GB swap. It uses public weights without an image inference API or extra secret. Image failures stop publishing rather than substitute the old channel-name graphic. Music inference has a 350-minute deadline, a CPU-only PyTorch installation, and 16 GB of additional swap. CPU generation can be slow; successful completion still depends on the runner's memory, disk and time limits. A failed run is not reported as published.

## Songwriting and packaging

Eight daily directions rotate across acoustic romance, piano heartbreak, indie dream pop, uplifting folk, celebratory dance pop, contemporary ghazal-inspired ballads, cinematic soul and monsoon lo-fi. Each direction changes the story, arrangement and vocal delivery. Lyrics ask for concrete scenes, singable phrasing, a consistent chorus and a developing emotional arc. Rotation uses the Dhaka calendar date, so it also works in the isolated lyrics job without Drive access.

Songwriting and packaging use separate Qwen completions to keep each response manageable. Validated lyrics are checkpointed in `song-draft.json` before packaging; the `prepared_run` restore also supports the `music-input` artifact from a failed lyrics job. Retry logs identify the schema field, failed constraint and output token count without exposing generated text.

New `song.json` files carry `tags`, `thumbnail_text`, `visual_mood`, `background_prompt` and `thumbnail_prompt`. Title prompts prioritize the original Hindi/Romanized song name plus a truthful, mood-specific search phrase and the release year. Description prompts lead with the song name and relevant Hindi/English search terms, then its specific story and listening context. The publisher removes internal tool/model credits and unverified creator attributions, adds only the channel credit, and limits public hashtags to three. Thumbnail prompts request close chest-up compositions with distinct, clearly lit faces, natural skin and a softly blurred lyric-specific setting. Background prompts use a wider environmental view, recognizable people on the right-center, scenic depth and a clear lower edge for the existing waveform. The image worker refuses text-enabled inference; the saved thumbnail_text field remains only for backwards-compatible metadata and the existing video overlay. SSD-1B is not relied on for Hindi typography. Text-free prompts, text-suppression negatives and removal of the old poster/title instructions address the malformed-lettering problem. Generated images still need visual review for anatomy, unwanted incidental markings and story relevance. Uploads use the generated tags, deduplicate them and enforce a conservative YouTube character budget. Packaging avoids invented famous-artist associations and popularity claims. These changes improve relevance and readability; CTR and search performance require real audience data to evaluate.

SSD-1B uses revision `60987f37e94cd59c36b1cba832b9f97b57395a10`, matching Rezan After Dark. It generates 1024×576 sources at 20 steps in Actions, which are composed into 1920×1080 video artwork and a 1280×720 thumbnail. The model’s output safety handling stays enabled, with bounded retries and no blank-image fallback. Seeds, prompts, dimensions, steps and model revision are recorded in `image-manifest.json`. Cached images are reused only for the same song and generation settings, including the visual-style version, negative prompt and guidance scale. Old lettered-poster manifests are invalidated automatically. Two images take additional CPU time; quality and timing need live verification on the runner.

For local image preparation, install CPU PyTorch and `requirements-images-cpu.txt` alongside `requirements.txt`, then run `python prepare_music.py --run-id YOUR_RUN_ID --stage images` after lyrics preparation. The publishing renderer requires both generated source images. Font: bundled Oswald under the SIL Open Font License in `assets/artwork/FONT-LICENSE.txt`.

## Drive cleanup after successful publication

The main workflow shows a separate **Clean published media from Drive** job after **publish**. Publishing defers deletion to that job; local pipeline runs still clean up by default. After the upload is freshly verified as public, processed in HD, on the expected channel, with matching title, description and tags and a confirmed thumbnail upload, temporary media for that exact song is permanently deleted from the dedicated private Drive folder. This follows the reference project's exact-ID cleanup journal approach. It removes `song.wav`, `video.mp4`, `thumbnail.jpg` and generated source images; it retains `song.json`, publishing state, history, image-generation settings and the cleanup journal. Unrelated files and other runs are untouched. Failed or incomplete uploads retain their media.

Cleanup checks each target's exact filename, hashed workflow key, parent folder, owner-only permissions and non-folder type before deletion. It saves a durable manifest before deleting anything and checkpoints progress after each file. Rerunning an already published song resumes cleanup without generating or uploading another video.

The **Clean published song media from Drive** workflow also runs after a successful publishing workflow, including a generation that started before the cleanup code was added. It reads the completed song identity from that run's JSON artifact and uses trusted default-branch code to verify YouTube again. For cleanup-only recovery, manually run this workflow with the exact `run_id`; no song generation or video upload occurs.

## Start or resume

Open GitHub Actions → **Hindi album music generation and public publishing** → **Run workflow**.

- `run_id`: stable song identifier, e.g. `first-hindi-song-20261025`.
- `prepared_run`: optional numeric previous GitHub run ID with a `generated-music-<ID>` artifact. Reuse the same `run_id` to restore its lyrics and any completed audio. When available, the separate `generated-artwork-<ID>` artifact restores completed image work too; older runs without it generate fresh scenes from their saved song.

Old checkpoints from the removed hosted backend can supply the lyrics. The CPU worker does not resubmit their remote tasks. A failed local music process can restart with the saved lyrics. Completed audio is reused. An interrupted YouTube upload without a saved video ID still requires reconciliation to prevent duplicate publishing.

The scheduled workflow is enabled daily at **03:00 Asia/Dhaka (3:00 AM Bangladesh time)**, gated by repository variable `AUTOMATION_ENABLED=true`. Set that variable to `false` to pause scheduling. Manual runs request public publishing.

## Google accounts and secrets

| Purpose | Account |
| --- | --- |
| Heart & Mind YouTube | asifrezan@gmail.com |
| Google Cloud owner | asifrezan.office@gmail.com |
| Private Drive media | asifrezanit@gmail.com |

The previously unused project in organization `931428574736` is named **Heart and Mind**, project ID `project-5a0943f4-af8e-49e0-8e4`, number `563533070055`. Before reuse, credentials were empty, API traffic had no data for 30 days, and asset inventory contained only default project/services/logging resources.

The OAuth app is **In production**, with YouTube Data API v3 and Drive API enabled. Fresh offline credentials were verified for channel `UCDTjTh7ORO2J_5OrR0dESTQ` and its private project-marked Drive folder. Required encrypted repository Actions secrets:

- `YOUTUBE_TOKEN_JSON`
- `EXPECTED_CHANNEL_ID`
- `DRIVE_TOKEN_JSON`
- `DRIVE_FOLDER_ID`

No Hugging Face or Groq token is needed. Production removes the Testing-specific seven-day refresh-token limit; revocation and other expiry conditions can still require reauthorization.

For future account setup, download the dedicated Desktop client JSON as ignored `client_secrets.json`, install `requirements.txt`, then run `python setup_accounts.py youtube --channel-id UCDTjTh7ORO2J_5OrR0dESTQ` and `python setup_accounts.py drive`. The helper uses GitHub CLI if available; otherwise it prepares inputs under ignored owner-only `.credentials/` for encrypted Actions secrets. Never commit or print credentials.

## Pinned music runtime

- Official source: `ace-step/ACE-Step-1.5`, commit `ca1e85fe9430179831e6bc6be790c332190a3866`.
- Public weights: `ACE-Step/Ace-Step1.5`, revision `19671f406d603126926c1b7e2adc169acbcade22`.
- Downloaded components: turbo DiT, official VAE, Qwen3 embedding encoder. No optional 5Hz planning LM is downloaded or loaded.
- `requirements-music-cpu.txt` contains the inference dependencies. PyTorch and torchaudio CPU wheels are installed from PyTorch's official CPU index.

The wrapper checks the source commit before importing it and initializes with `device='cpu'`, no FlashAttention, no GPU backend, no compilation and no hosted fallback. It follows the official [CPU-only installation](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docs/en/INSTALL.md#cpu-only-mode) and [inference API](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docs/en/INFERENCE.md).

## Checks

`python -m unittest -v` exercises duration and Hindi validation, the pinned anonymous downloads, CPU-only generation parameters, safe local retries, rejection of private-only upload results, per-song image seeds, image checkpoint recovery, safety rejection handling, style rotation and metadata budgets. A live Actions run additionally imports the real pinned ACE-Step runtime before downloading its model weights and generating audio. Unit tests alone do not establish actual song quality or completed publication.

CPU synthesis configures the native `ACESTEP_GENERATION_TIMEOUT` to 18,000 seconds before importing ACE-Step (its default is only 600 seconds). Startup verifies the actual imported native timeout. The child worker has a separate 18,900-second hard deadline, within the 350-minute music job. A one-minute heartbeat reports elapsed CPU time and peak memory while synthesis runs. These are limits, not completion-time promises.

New songs alternate solo male/female vocal directions by Asia/Dhaka calendar date: October 28, 2026 is male, October 29 female, then repeat. Lyrics and the Hindi editing pass follow that narrator. Saved song checkpoints retain their original voice across retries; existing audio is not changed. Vocal gender is guided through the music caption, so generated audio still needs listening review.

Manual workflow dispatch can select `vocal_gender=male` or `female` for a new song; `auto` remains the default for scheduled runs. This one-off choice does not shift the daily calendar rotation. Use a new run ID when choosing a different voice; saved songs cannot be relabeled.

## Text-free visual refresh

The production style is `heart-mind-textfree-cinematic-v2`. Cast and camera instructions lead the short prompts so SSD-1B does not lose them behind scenery or typography instructions. Romance uses tender eye contact; heartbreak shows the couple apart rather than an unrelated older male stock portrait; healing uses hopeful expression. The thumbnail and video background remain distinct scenes with different song-derived seeds. Safety checks remain enabled.

Run the **Demo thumbnail and background preview** workflow with `source_run` empty to generate new review-only images using the actual production model. This workflow does not synthesize a song, upload a YouTube video or change published thumbnails. Recomposition from an old `source_run` does not regenerate its existing pixels; use a fresh preview to assess this style. Better CTR is a design aim, not a measured result; use real impressions/click-through data and compare comparable releases.

### YouTube 403 insufficientPermissions during publication

Story uploads also update AI disclosure and reconcile metadata on the existing
video. `youtube.upload` plus `youtube.readonly` permits uploading/reading but does
not authorize `videos.update`. Account setup now requests `youtube.force-ssl` as
well. Reauthorize the existing Heart and Mind channel using:

```sh
python setup_accounts.py youtube --client client_secrets.json --channel-id UCDTjTh7ORO2J_5OrR0dESTQ
```

Approve the added scope in Google's consent flow and replace the repository's
`YOUTUBE_TOKEN_JSON` with the newly granted credentials (the setup script writes
it through authenticated GitHub CLI). Merely adding a scope string to an old
secret or rerunning the job does not expand the grant. Never paste tokens in logs
or chat. After authorization, run **Recover existing Hindi story publication**
with the original run ID to finish the existing upload, avoiding regeneration or
a duplicate upload. Known upload/read-only grants are rejected by preflight
before model generation.
