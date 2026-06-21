# WPlace Timelapse Recorder

Automatically captures map timelapses from WPlace archives — screenshots every historical snapshot at your chosen location and assembles them into an MP4 video.

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
- [FFmpeg](https://ffmpeg.org/) (`yay -S ffmpeg`)

## Project Structure

```
.
├── start.sh                 # Entry point — installs deps, launches script
├── samuel_playwright.py     # Playwright script for wplace.samuelscheit.com
├── eralyon_playwright.py    # Playwright script for wplace.eralyon.net
├── LICENSE
├── README.md
├── .gitignore
├── samuel_output/           # Generated frames & videos (gitignored)
├── eralyon_output/          # Generated frames & videos (gitignored)
└── __pycache__/             # Python cache (gitignored)
```

## Architecture

Both scripts are **single-file Playwright agents** that:

1. **Launch headed Chromium** — user sees the page and positions the map manually.
2. **Inject a floating "Start Recording" button** into the DOM (red, fixed-position, z-index 99999).
3. **Poll for a button click** — Python polls `document.getElementById('__wr_btn').textContent` every 200ms until it starts with `▶` (the click handler changes the text to `▶ RECORDING`).
4. **Read slider bounds** — queries the `<input type="range">` element to get min/max values.
5. **Iterate all snapshots** (oldest → newest), for each:
   - Set slider value via `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set` followed by `dispatchEvent(new Event('input'))` — needed because React intercepts the value setter and won't fire its handler on a plain `.value = x`.
   - Wait for MapLibre tiles to finish loading (`.maplibregl-tile-loading`, `.maplibregl-image-loading` selectors, up to 20s per frame).
   - Extra 2.5s settle for tile rasterisation.
   - Screenshot the `.maplibregl-map` element via Playwright's built-in compositing (avoids WebGL `preserveDrawingBuffer` issues).
   - Read the date from the page (hash param `time=` on samuel, slider label on eralyon).
   - Overlay date text on the screenshot via Pillow (semi-transparent black bar at top, white centred text).
6. **Assemble MP4** via FFmpeg at 2 fps, libx264, CRF 18.

### Playwright over Tampermonkey + Python server

The original approach used two processes (Tampermonkey userscript → Python HTTP server). Abandoned because:
- WebGL `canvas.toBlob()` returns empty frames when `preserveDrawingBuffer` is false.
- Playwright `element.screenshot()` captures the fully-composited page (WebGL, tiles, overlays), not raw canvas.
- Single process is simpler and more reliable.

### Slider value setter

The WPlace site uses React/MapLibre with an `<input type="range">`. React intercepts the native value setter, so `inputElement.value = x` followed by `dispatchEvent(new Event('input'))` does NOT update the React state. The fix:

```javascript
const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
).set;
setter.call(slider, value);
slider.dispatchEvent(new Event('input', { bubbles: true }));
```

This calls the original `HTMLInputElement.prototype.value` setter directly, bypassing React's interception. Then `dispatchEvent('input')` triggers the React `onInput` handler.

### Start Recording button polling

Previous attempts failed:
- `page.wait_for_function("window.__wr_start === true")` — timeout, likely because React rerenders reset the window property.
- `page.expose_function("__wr_started", started.set)` — callback wasn't firing reliably.

Current approach: inject a button with `id='__wr_btn'`, change its text to `▶ RECORDING` on click, poll `document.getElementById('__wr_btn').textContent` from Python.

### Date formats

| Archive | Date location | Format | Example |
|---------|--------------|--------|---------|
| Samuel | `location.hash` param `time=` | ISO 8601 with hyphens in time: `2025-08-09T20-01-14.231Z` | Parsed via `fromisoformat` after normalising T separators |
| Eralyon | `#wplace-version-label` | `YYYY-MM-DDTHH` (no seconds): `2026-06-19T01` | Parsed via `strptime("%Y-%m-%dT%H")` |

### Tile waiting

MapLibre adds `.maplibregl-tile-loading` and `.maplibregl-image-loading` classes to tiles while they fetch. The script polls until none are found (up to 20s), then waits an additional 2.5s for tiles to fully rasterise. This sometimes times out for high-zoom or slow tiles — the script silently continues and captures what's rendered.

### Frame ordering

Snapshots are captured in **oldest → newest** order (left → right on the slider). For eralyon the iteration is `range(min, max+1)`. FFmpeg assembles them in filename order (zero-padded index: `000_9 August 2025.png`, `001_10 August 2025.png`, …).

### MapLibre selectors

Samuel's site uses `.maplibregl-*` selectors (MapLibre GL JS v4+ fork of Mapbox GL). The eralyon site uses MapLibre GL v5.7.1. Both sites' map container `<div>` gets the `.maplibregl-map` class automatically when MapLibre initialises.

---

&copy; 2026 [Omniversify](https://omniversify.com). All rights reserved.

[Unlicense](LICENSE) — public domain dedication.

_Made by Moroccans, for the Omniverse_

[![ReadMeSupportPalestine](https://raw.githubusercontent.com/Safouene1/support-palestine-banner/master/banner-project.svg)](https://donate.unrwa.org/-landing-page/en_EN)
