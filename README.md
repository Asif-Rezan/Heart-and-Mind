# Heart and Mind — daily Hindi emotional motivational stories

The active pipeline creates **one fresh original Hindi emotional motivational story each day**, with narration and short dramatic dialogue. Each final video must measure **8–12 minutes (480–720 seconds)**. This runs in **Asif-Rezan/Heart-and-Mind**, for the existing Heart and Mind channel `UCDTjTh7ORO2J_5OrR0dESTQ`.

## Story generation, voices, music and pictures

- Qwen3-4B CPU writes a complete original six-chapter Hindi Devanagari story, about 1,100–1,500 words across 48 scenes. Approximately 75% is narration; the remaining scenes contain short male/female dialogue. The conclusion demonstrates the lesson through a character's decision. Each new daily identity gets a new generation seed, and recent titles/plots guide variety. One canonical outline is followed by **six parallel chapter jobs**, sharing fixed characters and chronological beats. A separate assembly step validates every chapter and reserves the full story before asset generation. There is no fixed-story fallback.
- **Kokoro-82M**, package `kokoro==0.9.4`, `lang_code='h'`, CPU: narrator `hm_omega`, male character `hm_psi`, female character `hf_alpha`. The runner installs `espeak-ng` for Hindi phonemization. Scene boundaries come from actual speech sample counts. If necessary the entire narration is re-synthesized at a modest native speed (0.80–1.15) to meet 8–12 minutes; it is never cut short, looped or padded with minutes of silence. Speech outside the measured range fails before upload. Pronunciation and emotional performance still need listening review.
- **ACE-Step 1.5** `acestep-v15-turbo` generates a new quiet instrumental score, using the existing pinned CPU model/source revisions. **Six independent 120-second score jobs** start alongside narration and image generation, producing enough instrumental material for the maximum 12-minute story. Only excess background accompaniment is trimmed to the final measured voice duration; the spoken story is kept complete. Requests specify instrumental/no singing/no speech; no nursery-rhyme reference audio is supplied. The bed is faded, mixed quietly and ducked under the narration. Short music output fails instead of looping or padding.
- **Pictures follow the supplied kids-rhyme reference style**, rather than the old Heart and Mind romantic-song style. [Saved reference example](assets/reference/storybook-look.png), from the reference repository's existing generated artwork. `story_image_cpu.py` uses the same pinned `segmind/SSD-1B`, 1024×576 sources and 20 steps; prompts request cute colorful 3D storybook rendering, rounded shapes, expressive faces, bright pastels, soft lighting, detailed backgrounds and gentle depth of field. Human characters/settings match the Hindi story. Character appearance/clothes/world are repeated within the episode. This is text-guided consistency, not reference-image conditioning, face locking or lip-sync; identical faces cannot be guaranteed. The other repository is only a style reference and is not this pipeline's upload destination.
- **18 CPU image jobs** produce 48 scene illustrations: 12 jobs make three images each and six jobs make two each. The 1920×1080 video uses gentle pan/zoom with picture changes at the actual spoken scene boundaries. Its thumbnail comes from the opening illustration, without generated lettering. Both final audio and video must measure 480–720 seconds before a new upload is allowed.
- Hindi story title, description and tags are used for each upload, with Education category 27, general audience (`made_for_kids=false`) and AI disclosure. An additional explicit channel guard rejects any destination other than the existing Heart and Mind ID before generation/publication. Existing Heart and Mind OAuth, private Drive folder checks and accounts are reused; no credentials are copied from another repository.
- Story history/checkpoints use `stories/` keys in Heart and Mind's existing dedicated private folder, separate from old music records. Exact titles/scripts, close summary similarity and repeated scenes are checked against reserved, unfinished and published stories. This is a practical duplicate check, not proof of global originality. Reusing a run ID resumes its reserved script. New YouTube uploads stop on an ambiguous upload checkpoint; recorded video IDs are reused for recovery rather than inserted again.
- After fresh public HD verification, only the story's exact temporary audio/video/thumbnail Drive IDs are cleaned, with a saved cleanup journal. Story scripts, history and publication state remain. Deferred cleanup is retried on the next daily run. Storage quota guards stop rather than buy more space.

## Parallel jobs and the failed outline fix

Parallel/validation update commit: `acce1c7a3b9cdd707cb5cc78f9f262bfcf7e7b35`. Previous story version: `f04ba246c1136689b3277a19b885d402d6ef7465`. The original song rollback point below is retained.

Run [41050567153](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41050567153) failed before image/voice/music generation: Qwen produced a `summary` longer than the 700-character limit on three attempts. The old inference validator rejected it before the writer could save or normalize the outline.

Story-specific inference now relaxes only the maximum lengths of **planning prose** (title, description, summary, character/world descriptions, chapter beats and scene visuals). It saves the raw valid JSON first, bounds those fields at sentence/word boundaries, then runs the original strict schema. Spoken Hindi text retains its original limits and is never truncated. Missing fields, wrong array sizes, invalid speakers and bad Hindi still fail validation. Tests reproduce the actual long-summary failure and verify that it passes after normalization in one inference response. Raw outline/scene responses and safe chapter validation counters are checkpointed for diagnosis/recovery.

The production dependency order is:

1. Canonical outline → **six chapter jobs in parallel** → validate/reserve the complete 48-scene story.
2. **18 image jobs, one Kokoro voice job and six ACE-Step score jobs** become eligible together; score generation no longer waits for voice.
3. **18 scene-render jobs** run after pictures and measured voice are ready, without waiting for music. Each job renders its own two/three scenes. Audio mixing independently waits for the voice and six score parts.
4. Publication waits for rendered scenes and mixed audio, verifies clip fingerprints, joins them without re-rendering, and applies the existing duration/channel/upload guards.

Image/render matrices explicitly allow up to 18 jobs; chapter/music matrices allow six. GitHub account concurrency and available runners can queue jobs, so these are parallel job requests, not a promise that every job starts simultaneously. Completed chapter, image, music-part and rendered-clip checkpoints can be reused on recovery. Each cache is bound to its canonical story/image/timing inputs. A missing or stale part stops joining rather than silently substituting content.

Corrected production run: [41075270533](https://github.com/Asif-Rezan/Heart-and-Mind/actions/runs/41075270533), dispatched on the fixed main commit using the same daily identity and the failed run checkpoint. At this documentation checkpoint it is running; final video/publication is not yet verified.

For the fixed code, start a **new workflow dispatch on main** with the failed identity `story-2026-10-30` and `prepared_run=41050567153` to reuse any available checkpoint. Re-running the old run directly executes its old commit and cannot apply this fix.

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

- Python 3.12: **98 tests passed**, including all original Heart music tests and new story checks for Hindi/length, saved-script resumption, duplicate detection, continuous timing, public Hindi metadata, exact Heart channel rejection, instrumental CPU/no reference requests and cleanup isolation.
- All active workflows passed actionlint 1.7.12. The new regression suite runs in CI and before production outline generation, including workflow dependencies, exact 18-worker image coverage/cache reuse, independent chapter assembly, real FFmpeg six-part audio mixing and parallel clip joining.
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
