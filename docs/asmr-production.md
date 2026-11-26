# Idea-driven procedural ASMR production

This implementation lives on `codex/asmr-production`; main and the existing
cartoon publishing workflows have not been changed. The earlier approved
`make_asmr.py` preview is preserved separately. Production v2 uses distinct
activity renderers instead of applying a cutting template to every idea.

## What each new run does

The existing pinned local Qwen3-4B model writes an original episode idea, twelve
scene recipes, and separate English title/description/tags for the full video and
Short. A run-seeded sampler chooses four activity families from an eight-family
library and avoids repeating the previous episode's exact activity set. The AI
invents a coherent idea using that menu and writes the executed scene recipes.
Supported families are blade cutting, soft-material pressing, bead/water pouring,
wood/glass tapping, sand brushing, paper crinkling, sand raking and water ripples.
These are a finite implemented animation library, not arbitrary photorealistic
video generation. Each action has its own moving objects, contact events and sound.
The decoding grammar constrains each activity to compatible materials. Twelve
scenes must contain at least three different activities, with at most three cutting
scenes. Eight palettes, color patterns, shape controls and 8–10 action cycles per
scene provide variation within those families. Every scene must have a distinct
configuration; at least two visual controls must vary across the episode.
Titles cannot promise an absent material, real footage, medical effects
or invented numeric event counts. Invalid AI output is retried within a bound;
there is no canned-episode fallback and no model-generated Python is executed.
The ASMR planner passes an explicit decoding grammar for all twelve complete scene
objects and metadata fields; it does not rely on the chat adapter's generic JSON
fallback. Semantic and length validation still run after decoding, with bounded
retries and saved candidate artifacts for diagnosis.
An overlong idea summary is shortened at a sentence/word boundary without changing
any scene controls. The raw AI draft remains available. If packaging names
an absent material/activity or the Short promises an incorrect duration, only its metadata is
regenerated against the three selected scene recipes; scene selection stays fixed.
Retry feedback identifies the exact schema field and bound rather than copying
an overlong response back into the prompt.

History reserves the exact title and structural render fingerprint before the
expensive scene jobs start. Different random seeds alone do not make an identical
recipe new. Preview history persists in an Actions cache; cache eviction can limit
preview history. Production uses durable private Drive history and keeps all
reservations, including incomplete episodes. History comparison is a practical
repeat guard, not a guarantee of originality across all possible content.

Twelve scene jobs render distinct action geometry: separated slices, a descending
press and deforming slab, streams and filling containers, bouncing mallets,
bristles clearing grains, a folding/crumpling sheet, combed sand grooves, or
falling droplets and expanding rings. Sound is synthesized on each activity's event
clock: crisp cutting, low squishes, granular/water streams, wood knocks/glass tones,
brush swishes, paper crackles, dry rake friction and drips. These are stylized
illustrations with synthesized audio, not recorded footage or physical simulation.

The full video is native **1280×720 landscape (16:9)** / 30 FPS, lasting exactly
240, 270 or 300 seconds. The separate Short is native **720×1280 portrait (9:16)**,
exactly thirty seconds: ten seconds from each of three AI-selected scene recipes.
The Short is rendered with its own portrait composition, not stretched or cropped
from the landscape video. Its metadata describes only those selected scenes.
Descriptions add real timeline chapter markers and an animation/synthetic-sound
disclosure. Both products and thumbnails use the actual generated scene frames.

## Test mode: publishing is OFF

`AI ASMR long video and Short` was started by the initial test-branch push. Further
branch tests are requested by changing `.generation/asmr-request.json` (for example
`{"request":"new-preview-20261126"}`), with
all publication and cleanup gates false. No YouTube or Facebook API writes occur,
no Drive files are deleted, and no Drive client is created by default. Old global
`PUBLISH_ENABLED=true` / `FACEBOOK_PUBLISH_ENABLED=true` variables cannot enable this
new workflow. An optional `backup_to_drive` input permits private test backup;
preview media remains until explicitly handled later and is never auto-deleted.

Normal tests upload these artifacts for fourteen days:

- `asmr-plan-RUN`: original idea, renderer recipes, generated metadata and draft.
- `asmr-scene-RUN-INDEX`: per-scene video, actual frame, source identity and hashes.
- `asmr-finished-RUN`: full `video.mp4`, `short/video.mp4`, both thumbnails,
  `video-metadata.json`, `short-metadata.json`, `plan.json` and `media.json`.

`media.json` records actual durations, dimensions, FPS, stereo audio and SHA-256.
Every output is fully decoded with FFmpeg before it is accepted. Encodes are
written to temporary files and only committed after validation. A changed scene
recipe or renderer hash invalidates that scene's cached render.

## Production activation after test review

Merge the reviewed branch when ready to activate its workflow on the default
branch. GitHub manual dispatch/recovery requires the workflow on the default
branch; request-file branch push tests work without a merge. Ordinary code pushes do
not start another expensive AI/video generation. No automatic ASMR schedule has
been enabled by this implementation.

To publish, BOTH the workflow dispatch input `publish=true` AND repository variable
`ASMR_PUBLISH_ENABLED=true` are required. Set `ASMR_FACEBOOK_ENABLED=true` for both
the Facebook feed video and Reel, and `ASMR_CLEANUP_ENABLED=true` for post-publication
Drive cleanup. All three variables are independently false unless explicitly set.
The full episode and Short use public visibility after platform processing, English
metadata/audio, Entertainment category, not-made-for-kids audience and AI disclosure.

Reuse the repository's existing `YOUTUBE_TOKEN_JSON`, `EXPECTED_CHANNEL_ID`,
`DRIVE_TOKEN_JSON` and `DRIVE_FOLDER_ID`. Facebook additionally requires this
project's `FACEBOOK_PAGE_ID` variable and `FACEBOOK_PAGE_ACCESS_TOKEN` secret.
No channel/Page IDs or credentials are copied from another project. Preflight
checks required names only when publishing is enabled; missing Facebook setup is
a production configuration blocker, not evidence of a connected Page.

The existing uploader checks the exact YouTube channel, durable video ID,
metadata/settings, synthetic disclosure and public HD processing. Lost/ambiguous
insert responses stop for reconciliation rather than inserting duplicate videos.
Long video and Short have separate publication checkpoints. Facebook reuses the
existing resumable Page-video/Reel uploader and requires verified YouTube success
for the matching product. Facebook failure retains media for independent recovery.

## Private backup, cleanup and recovery

ASMR uses a separate owner-only child folder under the configured project root,
marked `heart_and_mind_asmr_root=v1`; it never uses the cartoon/kids history folder.
Storage retains the existing account/owner/root/privacy/quota guards. Media is
backed up and verified before the first publication request. Plan, history,
publication checkpoint and media report are retained as essential records.

Cleanup requires fresh remote proof that BOTH YouTube products are public HD with
matching identities and metadata; when Facebook was required in the original
checkpoint, BOTH Facebook products must also be confirmed. Changing an enable flag
later cannot bypass a saved Facebook requirement. The entire deletion manifest is
validated before the first deletion. Each item must have the exact episode key,
file ID, private parent, workflow-key tag, size and MD5. Only those named disposable
media files are removed, with each deletion checkpointed; no account-wide trash
emptying, folder deletion, broad sweep or unrelated data removal is performed.
Scheduled/private/failed/ambiguous publications never qualify for cleanup.

For render recovery use the same `run_id`, original code revision and
`prepared_run` number. Matching scene artifacts are reused; missing artifacts fail
explicitly and can be regenerated by running the affected scene stage from the
saved plan. Artifacts expire after fourteen days. A production publication can
instead use `operation=recover` with publishing enabled: it restores the original
verified Drive media and resumes saved YouTube/Facebook IDs without AI regeneration.
`operation=cleanup` restores only essential metadata and retries cleanup. Use the
original renderer revision; source/hash or publication-policy changes fail closed.

Local examples:

```sh
python -m unittest -v test_asmr
python -m asmr --stage plan --run-id asmr-example --seconds 270
python -m asmr --stage scene --run-id asmr-example --index 0
# Render indices 0-11, then:
python -m asmr --stage assemble --run-id asmr-example
```

Rendering and mock publication/cleanup regressions verify implementation behavior.
Live publishing is intentionally not exercised while testing is off; successful
preview generation cannot prove current OAuth/Page-token validity, API quotas or
future platform acceptance. The cloud preview must complete before claiming an
end-to-end AI-generated episode has been validated.

## v2 compatibility

The v2 schema adds `activity` and replaces `cuts` with `cycles`. Renderer receipts
include the activity implementation and format code. Old cutting-only portrait
plans and media are deliberately not reused as v2 output. To recover an old v1
publication, check out its original revision; never migrate an existing uploaded
video ID to a new source recipe or orientation.
