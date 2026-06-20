# WPlace Timelapse Recorder

Automatically captures map timelapses from [WPlace](https://wplace.live) archives — screenshots every historical snapshot at your chosen location and assembles them into an MP4 video.

Built primarily to document the **Spanish invasion of Moroccan territories** visible on the WPlace canvas over time.

## Supported Archives

| Site | Snapshots | Period | Command |
|------|-----------|--------|---------|
| [Samuel Scheit](https://wplace.samuelscheit.com) | ~40 | Aug 2025 – May 2026 | `./start.sh samuel` |
| [Eralyon](https://wplace.eralyon.net) | ~250+ | Aug 2025 – Jun 2026 | `./start.sh eralyon` |

## Quick Start

```bash
./start.sh eralyon
```

1. A **Chromium window** opens to the archive.
2. **Pan & zoom** to the area you want to document.
3. Click the red **Start Recording** button at the top of the page.
4. The script steps through every snapshot (oldest → newest), overlays the date, and produces an MP4.

Output is saved to `eralyon_output/run_<timestamp>/` or `samuel_output/run_<timestamp>/`.

## Requirements

- Python 3
- [Playwright for Python](https://playwright.dev/python/) (auto-installed if missing)
- [FFmpeg](https://ffmpeg.org/) (`apt install ffmpeg`)

---

&copy; 2026 [Omniversify](https://omniversify.com). All rights reserved.

[Unlicense](LICENSE) — public domain dedication.

_Made by Moroccans, for the Omniverse_

[![ReadMeSupportPalestine](https://raw.githubusercontent.com/Safouene1/support-palestine-banner/master/banner-project.svg)](https://donate.unrwa.org/-landing-page/en_EN)
