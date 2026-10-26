# Heart and Mind — Hindi Music Automation

All AI inference and video rendering run on standard **GitHub Actions CPU runners**. There is no hosted Hugging Face Space, ZeroGPU call, Groq key, remote music API, GPU rental, or self-hosted runner requirement. Public model weights are downloaded anonymously; downloads do not perform remote inference.

## Workflow

1. **Lyrics job:** original Hindi Devanagari lyrics and metadata using the same pinned Qwen3-4B CPU model as [Rezan After Dark](https://github.com/Asif-Rezan/Rezan-After-Dark).
2. **Music job:** ACE-Step 1.5 `acestep-v15-turbo` runs directly on the GitHub CPU. Hindi vocals, one complete 180–360 second song, eight diffusion steps. Optional ACE-Step planning LM is disabled because lyrics and the musical prompt are already supplied.
3. **Publish job:** measure the real audio duration, render a 1920×1080 branded waveform video and thumbnail, back up privately to Drive, upload publicly to the exact Heart & Mind channel, and verify actual public visibility and HD processing.

Songs are never looped or padded to meet the duration requirement. Images are a locally drawn branded background and thumbnail; AI scene-image generation is not implemented.

The three jobs run sequentially on separate workers to release memory between models. Only the publishing job receives Google credentials. Music inference has a 350-minute deadline, a CPU-only PyTorch installation, and 16 GB of additional swap. CPU generation can be slow; successful completion still depends on the runner's memory, disk and time limits. A failed run is not reported as published.

## Start or resume

Open GitHub Actions → **Hindi music generation and public publishing** → **Run workflow**.

- `run_id`: stable song identifier, e.g. `first-hindi-song-20261025`.
- `prepared_run`: optional numeric previous GitHub run ID with a `generated-music-<ID>` artifact. Reuse the same `run_id` to restore its lyrics and any completed audio.

Old checkpoints from the removed hosted backend can supply the lyrics. The CPU worker does not resubmit their remote tasks. A failed local music process can restart with the saved lyrics. Completed audio is reused. An interrupted YouTube upload without a saved video ID still requires reconciliation to prevent duplicate publishing.

The scheduled workflow is daily at **01:00 Asia/Dhaka**, gated by repository variable `AUTOMATION_ENABLED=true`. Scheduling stays off until a full generation and publishing run succeeds. Manual runs request public publishing.

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

`python -m unittest -v` exercises duration and Hindi validation, the pinned anonymous downloads, CPU-only generation parameters, safe local retries, and rejection of private-only upload results. A live Actions run additionally imports the real pinned ACE-Step runtime before downloading its model weights and generating audio. Unit tests alone do not establish actual song quality or completed publication.
