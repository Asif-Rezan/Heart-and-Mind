# Heart and Mind — Hindi Music Automation

Adapted from [Rezan After Dark](https://github.com/Asif-Rezan/Rezan-After-Dark): staged generation, separate Google authorizations, private Drive checkpoints, resumable processing and guarded uploads. Horror narration/TTS is replaced with original Hindi vocal music. This is a new music implementation, not a copy of the horror repository.

## What it does

1. Generate original Hindi Devanagari lyrics and Hindi/English video metadata locally with Qwen/Qwen3-4B-Instruct-2507, matching the reference project; no text API key is used.
2. Generate a complete vocal song using ACE-Step 1.5 (`acestep-v15-turbo`, Hindi language), aiming at 4 minutes.
3. Measure audio and final video with ffprobe; reject anything outside 180–360 seconds. Never pad or loop short songs to meet the limit.
4. Render a 1920×1080 animated audio visualizer and branded thumbnail.
5. Save song, audio, video and checkpoint records to the dedicated private Drive folder.
6. Upload with `privacyStatus=public`, music category, Hindi audio language and AI disclosure. Verify channel, actual public visibility, processing and HD before marking published.

An interrupted upload with no saved video ID requires manual reconciliation to avoid duplicate videos. Rerun with the SAME run ID. No media is automatically deleted. Account or API restrictions never count as successful publication.

## Accounts

| Purpose | Account |
| --- | --- |
| YouTube Heart and Mind | asifrezan@gmail.com |
| Google Cloud project owner | asifrezan.office@gmail.com |
| Private Drive media folder | asifrezanit@gmail.com |

YouTube is checked by exact channel ID, because an email can contain several channels. The setup helper requires that ID; get it from Heart and Mind's YouTube Studio. Drive owner email and the folder's project marker are checked at runtime. No reference project credentials or channel IDs are reused.

## Google Cloud / OAuth setup

This repository does not imply Cloud has already been configured. In Google Cloud under `asifrezan.office@gmail.com`, inspect projects and select an unused dedicated project. Confirm it has no active integrations before reusing it. Enable YouTube Data API v3 and Google Drive API. Configure Google Auth Platform branding, audience and requested scopes. Set publishing status to **In production**, then create a Desktop OAuth client and download its JSON as `client_secrets.json` locally.

Production status must be set BEFORE fresh offline consent. Reauthorize after changing out of Testing; an existing Testing token should not be relied on. Testing grants for these scopes have a seven-day refresh-token limit. Production removes that Testing-specific limit, but tokens can still be revoked or expire for other reasons. OAuth Production status is not a guarantee of YouTube public publishing eligibility; inspect the actual returned video status.

Install Python 3.11+, GitHub CLI, FFmpeg, and dependencies:

```bash
python -m pip install -r requirements.txt
gh auth login
python setup_accounts.py youtube --channel-id YOUR_HEART_AND_MIND_CHANNEL_ID
python setup_accounts.py drive
```

Select Heart and Mind under `asifrezan@gmail.com` for YouTube. Select `asifrezanit@gmail.com` for Drive. The helper creates/reuses a project-marked folder and saves tokens, folder ID and channel ID directly to repository secrets using GitHub CLI stdin. It never writes tokens to repository files or prints them. Google login/consent remains interactive on your computer. Keep client JSON private.

## ACE-Step 1.5

Requested source: [ACE-Step/Ace-Step-v1.5](https://huggingface.co/spaces/ACE-Step/Ace-Step-v1.5). The pipeline integrates the official ACE-Step 1.5 REST API; it does not assume the public Gradio demo is a reliable unattended REST server. By default, generation uses the official Space’s published Gradio API and ACE-Step 1.5 XL turbo checkpoint. Availability and ZeroGPU quotas may interrupt a run. Configure an optional private ACE-Step 1.5 server to use the REST backend instead.

Install the official [ACE-Step-1.5](https://github.com/ace-step/ACE-Step-1.5) project on your own suitable machine, follow its installation instructions, then launch its documented `acestep-api` entry point. Configure server `ACESTEP_API_KEY`; protect remote transport with HTTPS. Configure the API URL/key as GitHub secrets below. No GPU service is purchased or provisioned by this repository. Hosted Ubuntu Actions orchestrates the API and renders video; it does not install/run the music model itself. CPU inference is available upstream, but generation time depends on your machine. Use a self-hosted runner/local server if you want generation on your own hardware.

API contract: `POST /release_task`, `POST /query_result`, then same-origin `/v1/audio` download. Task IDs are checkpointed before polling, with a one-hour deadline. API submissions are not blindly retried.

## Required GitHub secrets

| Secret | Source |
| --- | --- |
| ACESTEP_API_URL | Optional HTTPS URL of your ACE-Step 1.5 REST server |
| ACESTEP_API_KEY | Required only with the private REST server |
| YOUTUBE_TOKEN_JSON | YouTube setup helper |
| EXPECTED_CHANNEL_ID | YouTube setup helper |
| DRIVE_TOKEN_JSON | Drive setup helper |
| DRIVE_FOLDER_ID | Drive setup helper |

Lyrics use the reference project’s pinned Qwen3-4B Q4_K_M CPU model, downloaded anonymously and verified by SHA-256. Install `requirements-lyrics.txt` alongside `requirements.txt` for generation. No Groq credentials or hosted text service are used. Scheduled runs require repository variable `AUTOMATION_ENABLED=true`. Default cadence follows the reference: daily at 01:00 Asia/Dhaka. It is disabled until configuration is complete; manually run **Hindi music generation and public publishing** with a stable ID such as `first-song-001` to validate the full path. A manual run publishes publicly as requested. Enable the daily variable after that succeeds.

```bash
python -m unittest -v
python pipeline.py --run-id first-song-001
```

## Current verification limits

Unit tests cover duration boundaries, Hindi validation, interrupted submission safeguards and rejection of private-only uploads. Live music quality, account authorization, Drive access and public uploading require configured secrets and a working ACE-Step server. Hindi output is prompted and structurally checked; native listening review remains useful. The initial visual style is a branded audio visualizer rather than generated cinematic scenes or synchronized lyric captions.

Reference inspected: `Rezan-After-Dark` main, including `workflow.py`, `daily_publish.py`, authorization helpers and requirements. Relevant upstream docs: https://ace-step.github.io/ACE-Step-1.5/en/API and https://developers.google.com/identity/protocols/oauth2 .

## Dedicated Google Cloud project

Selected an unused project in organization `931428574736`, renamed **Heart and Mind**. Project ID: `project-5a0943f4-af8e-49e0-8e4`, project number `563533070055`. Before reuse its credential lists were empty, API traffic had no data over 30 days, and inventory contained only the default service registrations, log buckets/sinks, and project record.
