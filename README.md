# Heart and Mind — Hindi Album Music Automation

Creates original Indian Hindi album-style songs with fresh lyric-based music-video scenes. Lyrics, audio, timing, images and video rendering run on standard GitHub Actions CPU runners. Public titles, descriptions, tags and artwork never name internal models, providers or tools.

## Workflow

1. **Lyrics:** write an original Devanagari song with a developing emotional story, singable lines and a recurring chorus. A separate short request produces its summary, relevant search tags and thumbnail concept. Validated lyrics are saved before packaging so a retry can reuse them.
2. **Music:** generate a complete 180–360 second song with Hindi vocal language (`hi`). Audio is never looped or padded.
3. **Storyboarding:** recognize vocal words with timestamps from the real audio, match them against the supplied lyrics, and build exact five-second intervals. Each interval receives a distinct English scene prompt based on its sung lyric context. Instrumental intervals use nearby lyric context for related establishing shots. Recognition entries without a usable duration, overlapping out-of-order entries and audio padding are excluded. Scene prompts also receive the actual recognized words from their own interval. Weak lyric/audio matching stops publishing; there is no evenly spaced guessed-lyric fallback.
4. **Images:** sixteen recoverable shards generate a fresh scene per interval plus a separate expressive thumbnail scene. At most sixteen image workers run simultaneously. A four-minute song has 48 scenes; the final interval may be shorter than five seconds. Every scene has a distinct song-and-index seed. There is no shared background library or static-background fallback.
5. **Publish:** verify every required image and the storyboard's audio fingerprint, render a 1920×1080 video with cuts every five seconds and continuous original audio, back up to the dedicated private Drive folder, upload to the expected channel, and verify public HD processing.
6. **Cleanup:** a visible job after publishing freshly verifies the public HD video, channel and metadata, then permanently removes only that run's temporary Drive media. Lyrics/metadata, publishing state, history, vocal timing, storyboard and cleanup journal remain. Failed or incomplete uploads keep their media. An independent completion workflow also covers older runs and cleanup-only recovery.

Only publishing and cleanup jobs receive Google credentials. The music worker has a 350-minute deadline and 16 GB swap; image shards have 180-minute deadlines and 12 GB swap. Five-second scenes add substantially more CPU work than one static image. Singing transcription and Hindi pronunciation/creative quality still require live evaluation; unit tests do not establish these qualities.

## Hindi songwriting and SEO

Eight daily directions rotate across romantic acoustic pop, sad piano ballads, indie dream pop, uplifting folk with acoustic guitar and flute, celebratory dance pop, modern Hindi album ballads, cinematic soul and monsoon lo-fi. The Dhaka calendar controls this rotation even when the lyrics worker has no Drive history.

Titles combine the Hindi song name, Romanized Hindi name where space permits, and one relevant search phrase with the release year, such as **Hindi Romantic Song 2026**, **Hindi Sad Song 2026** or **Hindi Album Song 2026**. Descriptions lead with Hindi and English search phrases, followed by the song's own story and three relevant hashtags. Tags include the song name, genre and relevant Hindi/English music keywords within YouTube's character limit. No unrelated artist names, invented popularity claims or internal tool credits are allowed. Search ranking and CTR must be evaluated with real audience data.

New songs require Hindi sung lyrics. Use a new run ID for five-second scene productions; old single-background artifacts do not contain a complete lyric storyboard. Thumbnail hooks use large, high-contrast Romanized Hindi with small channel branding. Upload language and vocal generation language are both Hindi.

## Runtime and recovery details

The reference image backend remains pinned SSD-1B revision `60987f37e94cd59c36b1cba832b9f97b57395a10`; song timing uses the multilingual CPU recognition model pinned in `lyric_video.py`. Scene prompts, source audio fingerprint, timings, seeds and image generation settings are checkpointed. Matching completed images are reused only within the same song and scene configuration. Retry logs identify schema fields and constraints without printing generated content.

For local stages, install the relevant dependencies in addition to `requirements.txt`: `requirements-lyrics.txt` for lyrics/storyboarding, `requirements-alignment.txt` for vocal timing, CPU PyTorch plus `requirements-images-cpu.txt` for image generation, and the existing music runtime for audio. Run `prepare_music.py --run-id ID --stage lyrics`, `music`, `storyboard`, `images`, then `render`. The images stage uses `IMAGE_SHARD` from 0 through 15; `--stage all` can generate the whole production locally if all runtimes are installed. Bundled Oswald is licensed under the SIL Open Font License in `assets/artwork/FONT-LICENSE.txt`.

Cleanup uses an exact-ID journal saved before deletion. Targets must match their exact run-scoped filename, hashed workflow key, private parent folder and owner permissions. Scene files are enumerated from the validated storyboard, never from a broad folder wipe. Rerunning a published song resumes cleanup without another upload; the dedicated cleanup workflow also supports a manual exact `run_id`.

## Start or resume

Open GitHub Actions → **Hindi album music generation and public publishing** → **Run workflow**.

- `run_id`: stable song identifier, e.g. `first-hindi-song-20261025`.
- `prepared_run`: optional numeric previous GitHub run ID with a `generated-music-<ID>` artifact. Reuse the same `run_id` to restore its lyrics and any completed audio. When available, the `generated-artwork-<ID>-<SHARD>` and `song-storyboard-<ID>` artifacts restore completed image and timeline work too; older runs without it generate fresh scenes from their saved song.

Old checkpoints from the removed hosted backend can supply the lyrics. The CPU worker does not resubmit their remote tasks. A failed local music process can restart with the saved lyrics. Completed audio is reused. An interrupted YouTube upload without a saved video ID still requires reconciliation to prevent duplicate publishing.

The scheduled workflow is daily at **20:00 Asia/Dhaka (8:00 PM Bangladesh time)**, gated by repository variable `AUTOMATION_ENABLED=true`. Set the variable to `false` to pause daily generation. Manual runs request public publishing.

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

`python -m unittest -v` exercises duration and Hindi validation, the pinned anonymous downloads, CPU-only generation parameters, safe local retries, rejection of private-only upload results, Hindi language selection, public metadata rules, five-second timelines, sharded scene generation, image checkpoint recovery, safety rejection handling, style rotation and metadata budgets. A live Actions run additionally imports the real pinned ACE-Step runtime before downloading its model weights and generating audio. Unit tests alone do not establish actual song quality or completed publication.

CPU synthesis configures the native `ACESTEP_GENERATION_TIMEOUT` to 18,000 seconds before importing ACE-Step (its default is only 600 seconds). Startup verifies the actual imported native timeout. The child worker has a separate 18,900-second hard deadline, within the 350-minute music job. A one-minute heartbeat reports elapsed CPU time and peak memory while synthesis runs. These are limits, not completion-time promises.
