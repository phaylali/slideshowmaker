# Dev Notes

## Project Structure

```
.
├── start.sh                 # Entry point — installs deps, launches script
├── samuel_playwright.py     # Playwright script for wplace.samuelscheit.com
├── eralyon_playwright.py    # Playwright script for wplace.eralyon.net
├── DEV_NOTES.md             # This file
├── README.md                # Public docs
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

## Key Technical Decisions

### Playwright over Tampermonkey + Python server

The original approach used two processes (Tampermonkey userscript → Python HTTP server). Abandoned because:
- WebGL `canvas.toBlob()` returns empty frames when `preserveDrawingBuffer` is false.
- Playwright `element.screenshot()` captures the fully-composited page (WebGL, tiles, overlays), not raw canvas.
- Single process is simpler and more reliable.

### Slider value setter

The WPlace site uses React/MapLibre with an `<input type="range">`. React intercepts the native value setter, so `inputElement.value = x` followed by `dispatchEvent(new Event('input'))` does NOT update the React state. The fix (found by trial and error):

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

## Planned Implementation

### Date range filtering

```
./start.sh eralyon s=06-12-2025 e=07-02-2026 fps=4
```

- `s=<dd-mm-yyyy>` — start date, inclusive. Snapshots before this are skipped.
- `e=<dd-mm-yyyy>` — end date, inclusive. Snapshots after this are skipped.
- `fps=<int>` — framerate for the output MP4 (default 4). Each frame = 1/fps seconds on screen.

Implementation: pass extra args from `start.sh` to the Python script. In Python, parse the slider date labels and compare with the user's date range, only capturing frames that fall within the window. The fps is passed directly to FFmpeg's `-framerate`.

## Weird Selectors

Samuel's site sometimes uses `.maplibregl-*` selectors even though the DOM shows `.maplibregl-*` — MapLibre GL JS v4+ uses `.maplibregl-` prefixes by default (forked from Mapbox GL). The eralyon site uses MapLibre GL v5.7.1.

Both sites' map container `<div>` gets the `.maplibregl-map` class automatically when MapLibre initialises.
