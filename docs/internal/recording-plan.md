# Video + Backup GIF — recording day plan (4/24)

> **Goal**: by 4/24 22:00 Beijing time, have a locked-picture 2:45 video file and a 10-second backup GIF for the README header. Editing and captioning happen 4/25.
> **Owner**: Caleb leads recording; Eiddie on standby for UI; Hak + Hamza reachable on Discord for re-run requests.

---

## Tools to install (do this BEFORE 4/24)

All free, all Windows-native:

1. **OBS Studio** — screen recording (https://obsproject.com). Pick the "Recording" optimization preset during first-run setup.
2. **Audacity** — voice recording + noise reduction (https://www.audacityteam.org/).
3. **DaVinci Resolve** — editor (https://www.blackmagicdesign.com/products/davinciresolve). The free version is more than enough. Skip the Studio version.
4. **ffmpeg** — for GIF export and format conversions. Install via `winget install Gyan.FFmpeg` or download from https://www.gyan.dev/ffmpeg/builds/.

Verify install:
```powershell
obs --version
ffmpeg -version
# (Audacity and Resolve are GUI-only; just launch them once to confirm they open)
```

---

## OBS setup (one-time, 10 min)

1. Settings → Output → Output Mode: **Advanced**.
2. Settings → Output → Recording tab:
   - Type: **Standard**
   - Recording Format: **MP4** (not MKV — Resolve handles MP4 cleanly)
   - Encoder: **NVIDIA NVENC H.264** (if no NVIDIA GPU, use `x264` with CPU preset `medium`)
   - Rate Control: **CBR**
   - Bitrate: **20000 Kbps** (overkill but cheap storage; we downsize later)
3. Settings → Video:
   - Base Resolution: **1920×1080**
   - Output Resolution: **1920×1080**
   - FPS: **60**
4. Settings → Audio:
   - Mic/Aux device: your USB mic if you have one, otherwise default input
   - Sample Rate: **48kHz**

Add a **Window Capture** source pointing at your browser window with the dashboard. Do NOT use Display Capture — it'll catch notifications.

---

## What to record (in order)

Do them in these takes so you don't have to re-set up OBS repeatedly:

### Take 1 — Hero shot (for video + backup GIF)

- Point OBS at the dashboard live URL window.
- Hit Record, then in the dashboard:
  1. Click "Run Benchmark".
  2. Let ONE task run through the full hero animation (candidates fan out, score bars animate, winner highlights, USDC flies to winner address).
  3. Immediately stop recording.
- Expected length: 12–20 seconds.
- Save as `takes/hero-raw-1.mp4` (keep 3 takes, pick the cleanest in edit).

### Take 2 — Scale reveal

- Reset the dashboard.
- Record the full 50-task run, all 12 seconds of it. Let the Sankey diagram finish building.
- Keep recording through the "50 / 15 / $0.25" number reveal.
- Save as `takes/scale-raw-1.mp4`.

### Take 3 — Generalizability hub-and-spoke

- If Eiddie built this into the dashboard, record it. If not, we'll use a still SVG from the deck for this beat.
- Save as `takes/generalizability-raw-1.mp4`.

### Take 4 — Economics comparison

- Scroll/click to the comparison panel: "Arc $0.25 vs Ethereum ~$95".
- Linger on the numbers for 5 seconds. Then the overhead ratio.
- Save as `takes/economics-raw-1.mp4`.

### Take 5 — Arc Explorer proof (mandatory for submission)

- Click one of the tx hash links from the dashboard, landing you on Arc testnet explorer.
- Scroll, show the completed transaction, the value, the recipient address.
- Do this for ONE tx only (don't be boring). ~8 seconds.
- Save as `takes/arc-explorer-raw-1.mp4`.

### Take 6 — Circle Developer Console (mandatory for submission)

- Switch windows, show the Circle Developer Console with the batch of completed transfers.
- Scroll once. ~6 seconds.
- Save as `takes/circle-console-raw-1.mp4`.

---

## Voiceover (record LAST, after visuals are locked)

Use Audacity. Quiet room, phone on airplane mode, close all apps that make noise.

- Record each scene of `docs/internal/video-script.md` twice.
- Save each as `audio/scene1-take1.wav`, `scene1-take2.wav`, etc.
- In Audacity: Effect → Noise Reduction → first sample 2 seconds of silence → Reduce by 12dB.
- Optional: Effect → Normalize to -3 dB peak.
- Export each scene as a separate WAV file for Resolve to sync against visuals.

**If accent is a concern**: we can clone the voice with ElevenLabs. 30 min of work, $5 credit. Don't do this unless a test-listener says the native read is hard to follow.

---

## Editing in DaVinci Resolve (4/25 morning, 3-4 hrs)

1. New project, 1920×1080 @ 60fps.
2. Import every `takes/*.mp4` and `audio/*.wav` into the media pool.
3. Drag to the timeline in scene order. Align voiceover to visuals.
4. Cut each take to exactly the length listed in the script's timing table.
5. Add captions: use Resolve's built-in Subtitle track. Every on-screen number from the script must have a caption.
6. Add background music: YouTube Audio Library → "Inspirational Corporate", volume at -24 dB. Ducks automatically under voice.
7. Color grade: use the "Teal & Orange" LUT on all clips for consistency.
8. Export: H.264, 1080p60, 15 Mbps, two-pass encoding. Target file size ~200 MB.

---

## Backup GIF (produced 4/24 EOD, right after hero take)

The Plan B for a dashboard outage during judging. Lives at the top of the README.

```powershell
# From the best hero take
ffmpeg -i takes/hero-raw-1.mp4 -ss 00:00:00 -t 00:00:10 -vf "fps=15,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 docs/hero.gif
```

Then in `README.md`, add at the very top:

```markdown
![ASM picks one winner from 3 candidates and pays them in USDC on Arc](docs/hero.gif)
```

Keep the GIF under 10 MB. If it balloons above that:
- Drop FPS to 12
- Drop width to 720px
- Trim to 8 seconds

---

## Upload checklist (4/25 PM)

- [ ] **Video** → YouTube, unlisted URL. Title: *"ASM — the selection layer for agentic commerce"*. Description paragraph from submission draft.
- [ ] **Deck** → export as PDF, upload as GitHub Release asset for persistent URL.
- [ ] **Hero GIF** → committed in repo at `docs/hero.gif` and referenced from README top.
- [ ] **Cover image** → committed at `docs/cover.png`, uploaded to lablab form.
- [ ] **Arc Explorer screenshots** → saved in `docs/submission-assets/arc-explorer-{1..5}.png`.
- [ ] **Circle Console screenshot** → `docs/submission-assets/circle-console.png`.

---

## Anti-risk buffer

- If OBS crashes mid-take: records are saved as segments. Resolve stitches them. Don't panic and don't re-record everything.
- If the dashboard shows a bug on camera: **don't re-run.** Cut around it in Resolve. Re-running can introduce a different bug.
- If voiceover timing drifts: slow down or speed up the audio clip in Resolve by ±5% — it stays natural-sounding.
- If a take is corrupted (happens): the scale-reveal take is the most important. Record it twice from scratch.
