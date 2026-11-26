# Wan 2.1 Q4 Short preview

This isolated artifact-only workflow uses **Wan 2.1 T2V 1.3B calibrated Q4_K_S
GGUF**, the quantized UMT5-XXL encoder and original Wan 2.1 VAE through the official
stable-diffusion.cpp runtime. Model revisions, all three SHA-256 checksums, engine
revision and official release digest are pinned in `wan_preview.py`.

Local Qwen writes one new realistic ASMR idea and six coherent, distinct prompts.
Six parallel Actions workers each generate 41 actual diffusion frames. There is
no still-image, cartoon-renderer, loop or stock-footage fallback. Missing/failed
frames fail the run. Each five-second shot carries a prompt/profile/model identity
and content hash; assembly refuses mismatched or substituted clips.

The first speed draft uses 288×512, 20 Euler steps, CFG 6 and shift 3. Frames are
played at 8 FPS for slow ASMR pacing. Optical-flow interpolation produces 24 FPS;
Lanczos exports 720×1280. This is **not native 720p or native 24 FPS**. Six separate
clips form an exact thirty-second Short, not one continuous thirty-second take.
Reducing steps/resolution and using 8 FPS trades detail/motion fidelity for time.

The model has no native ASMR soundtrack. Assembly adds separate synthesized stereo
water/granular/paper/brush/soft sound beds selected by the shot plan, with fades
and loudness mastering. These are topic-matched sound design, not recorded sounds
or guaranteed frame-accurate contact audio. Metadata discloses AI video/sound.

The repository had no configured self-hosted GPU runner when checked. The first
test uses ordinary public CPU runners, six workers in parallel, with cached 4.725
GB model/encoder/VAE downloads. A smaller Q4 file does not make CPU diffusion as
fast as CUDA. CPU elapsed time is not guaranteed; clip jobs are bounded to two
hours and save logs/partial frames for diagnosis. No paid runner is provisioned.
For reliably short turnaround and higher native resolution, an available GPU
runner is required. The native runtime's CUDA-compatible build can replace the
CPU engine when that infrastructure is explicitly configured.

The official pinned Linux binary requires Ubuntu 26.04 userspace, so the model
jobs use `ubuntu:26.04` containers on standard `ubuntu-24.04` hosts. No runtime
compilation is needed. Only the exact model pack is downloaded, not every variant.
The first download/cache fill adds startup time; subsequent runs reuse it.

Trigger another preview by changing `.generation/wan-short-request.json` on
`codex/asmr-production`. Normal code pushes do not generate expensive videos.
Manual dispatch becomes available after review/merge to the default branch.
No publishing jobs, publication credentials, Drive writes/deletes or schedules
are present. Main and the earlier procedural pipeline remain unchanged.

References:

- [Q4 model and companion requirements](https://huggingface.co/off-grid-ai/Wan2.1-T2V-1.3B-GGUF)
- [Publisher's GPU-only benchmark and its limitations](https://huggingface.co/off-grid-ai/Wan2.1-T2V-1.3B-GGUF/blob/main/BENCHMARKS.md)
- [stable-diffusion.cpp Wan support](https://github.com/leejet/stable-diffusion.cpp/blob/52491bd9f1fc15281791723bdff13baab7fd6819/docs/models/wan.md)
- [GitHub hosted runner hardware](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
