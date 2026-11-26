# Procedural soap cutting preview — 2026-11-26

The current preview follows the user-supplied `make_asmr.py`: low-poly Pillow
geometry, a timed blade stroke, detached/rotated soap slices, ballistic crumbs,
shadows and NumPy/SciPy stereo cutting/crunching/squishing/landing sound. A shared
timeline drives both visible contact and audio events. It no longer interpolates
AI stills. This is deterministic stylized 2.5D animation, not a physics engine.

`soap_cutting.py` fixes non-portable `/home/claude` and `/mnt/user-data` paths,
checks FFmpeg errors, verifies the completed MP4, makes texture seeding stable,
and keys geometry caches by actual extents. The output is 60 seconds, portrait
720×1280 at 30 FPS: six 10-second palette variants of five cuts each. Supersampling
at 2× matches the supplied script; final frames downsample with Lanczos.

Local checks exercised one complete ten-second take, stereo sound, a full decode
and contact/detachment/landing timing. Actions renders and validates all sixty
seconds before saving MP4, WAV and probe JSON as a 14-day artifact. Main and the
production workflow remain unchanged, and nothing is published.

The earlier kinetic-sand demo below remains as archived preview code and inputs.

---

# One-minute kinetic sand cutting ASMR preview

This branch-only experiment does not modify the production pipeline. Main baseline:
`865372e58b544ce2175538d315e986e098017640`. No merge or publication is requested.

The built-in ImageGen tool created five consistent macro keyframes: an intact
lavender/turquoise/peach kinetic-sand loaf, followed by one, two, three and four
slices, maintaining the same slate tray and camera. The first image is the identity,
material, lighting and camera reference for all four edits. Source images are stored
in `images/`, and all keyframes were inspected before use.

Prompt brief: fixed three-quarter macro camera, dark slate, fine granular layered
sand, unbranded steel scraper, no hands/text/logos. Each edit preserves framing and
material while adding one thin parallel left-end slice and moving the blade to the
new cut line. No paid inference API or image-model download runs inside Actions;
the supplied AI keyframes are inputs to the cloud render.

The workflow renders 60 seconds at 1280×720 / 24 FPS using Python/OpenCV optical
flow, feathered transition masking, local deformation, falling particles and gentle
camera movement, then encodes H.264/AAC using FFmpeg. Three 20-second passes reuse
the five keyframes with a brief fade separating resets. Sound is original local
synthesis: filtered cutting noise, granular fracture impulses, soft tray contacts
and settling tails, mixed in stereo with a -19 LUFS / -2 dBTP mastering request.
There is no speech, music, downloaded stock sound or publishing step. This is a
stylized animated-image preview rather than fully simulated blade/sand physics.

The script verifies the final duration, resolution, stereo audio stream and full
FFmpeg decode. GitHub Actions uploads the MP4, WAV and probe JSON for 14 days.
