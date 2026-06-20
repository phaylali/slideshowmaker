#!/usr/bin/env python3
"""
Samuel's WPlace Timelapse — wplace.samuelscheit.com
"""

import datetime
import pathlib
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

# ---- only use sync Playwright API inside the guard below ----

RUN_TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = pathlib.Path("samuel_output") / f"run_{RUN_TS}"
FRAMES = OUT / "frames"
FRAMES.mkdir(parents=True, exist_ok=True)

# ── helpers ───────────────────────────────────────────────────────

FONT_CACHE = None


def _font(size=40):
    global FONT_CACHE
    if FONT_CACHE:
        return FONT_CACHE
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]:
        if pathlib.Path(p).exists():
            FONT_CACHE = ImageFont.truetype(p, size)
            return FONT_CACHE
    FONT_CACHE = ImageFont.load_default()
    return FONT_CACHE


def overlay_date(img: Image.Image, label: str) -> Image.Image:
    rgb = img.convert("RGB")
    d = ImageDraw.Draw(rgb)
    bar = Image.new("RGBA", (rgb.width, 56), (0, 0, 0, 160))
    rgb.paste(bar, (0, 0), bar)
    bb = d.textbbox((0, 0), label, font=_font())
    x = (rgb.width - bb[2]) // 2
    y = (56 - bb[3]) // 2
    d.text((x, y), label, fill=(255, 255, 255), font=_font())
    return rgb


# ── main ──────────────────────────────────────────────────────────

def main():
    # Delay import so playwright can be absent until runtime
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="en-GB",
        )
        page = ctx.new_page()

        page.goto("https://wplace.samuelscheit.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # ── inject "Start Recording" button ──
        page.evaluate("""() => {
            const btn = document.createElement('button');
            btn.textContent = 'Start Recording';
            Object.assign(btn.style, {
                position: 'fixed', zIndex: '99999',
                top: '20px', left: '50%', transform: 'translateX(-50%)',
                padding: '14px 36px',
                fontSize: '22px', fontWeight: 'bold',
                background: '#e53935', color: '#fff', border: 'none',
                borderRadius: '8px', cursor: 'pointer',
                boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
            });
            btn.id = '__wr_btn';
            btn.addEventListener('click', () => {
                btn.textContent = '▶ RECORDING';
                btn.style.background = '#2e7d32';
                btn.style.cursor = 'default';
            });
            document.body.prepend(btn);
        }""")

        print("=" * 60)
        print("Navigate to your desired view (Morocco, zoom, etc.)")
        print("Then click the red [Start Recording] button at the top of the browser.")
        print("=" * 60)
        while True:
            txt = page.evaluate(
                "() => document.getElementById('__wr_btn')?.textContent"
            )
            if txt and txt.startswith("▶"):
                break
            time.sleep(0.2)

        # ── read current position from the page ──
        pos = page.evaluate("""() => {
            const c = document.querySelector('.maplibregl-map');
            if (!c) return null;
            for (const k of ['map','_map','__map','_context']) {
                const m = c[k];
                if (m && m.getZoom) {
                    const center = m.getCenter();
                    return {
                        zoom: m.getZoom().toFixed(2),
                        lat: center.lat.toFixed(5),
                        lng: center.lng.toFixed(5),
                    };
                }
            }
            // fallback – parse hash
            const h = location.hash.replace(/^#/, '');
            const p = {};
            h.split('&').forEach(pair => {
                const [k,...v] = pair.split('=');
                if (k) p[k] = decodeURIComponent(v.join('='));
            });
            return { zoom: p.z || '8', lat: p.lat || '31.79', lng: p.lng || '-7.09' };
        }""")
        print(f"  Locked position: zoom={pos['zoom']}  lat={pos['lat']}  lng={pos['lng']}")

        # ── find the slider ──
        slider_info = page.evaluate("""() => {
            const s = document.querySelector('input[type="range"]');
            if (!s) return null;
            return {
                min: parseInt(s.min), max: parseInt(s.max),
                val: parseInt(s.value)
            };
        }""")
        if not slider_info:
            print("ERROR: date slider not found on the page.")
            browser.close()
            sys.exit(1)

        total = slider_info["max"] - slider_info["min"] + 1
        print(f"  Slider range: {slider_info['min']}–{slider_info['max']}  ({total} snapshots)")

        # ── iterate (oldest → newest) ──
        native_setter_js = """
        (value) => {
            const s = document.querySelector('input[type="range"]');
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(s, value);
            s.dispatchEvent(new Event('input', { bubbles: true }));
        }
        """

        map_selector = ".maplibregl-map"
        frames_saved = 0

        for idx, val in enumerate(range(slider_info["max"], slider_info["min"] - 1, -1)):
            print(f"\n  [{idx + 1}/{total}] slider={val} …", end=" ", flush=True)

            # set slider
            page.evaluate(native_setter_js, val)

            # wait for tiles
            try:
                page.wait_for_function(
                    """() => {
                        const loading = document.querySelectorAll(
                            '.maplibregl-tile-loading, .maplibregl-image-loading'
                        );
                        return loading.length === 0;
                    }""",
                    timeout=20000,
                )
            except Exception:
                pass  # timeout – try anyway
            page.wait_for_timeout(2500)  # let tiles paint & settle

            # read date from hash
            hash_time = page.evaluate(
                """() => {
                    const m = location.hash.match(/time=([^&]+)/);
                    return m ? m[1] : '';
                }"""
            )
            label = _format_date(hash_time)

            # screenshot the map element
            try:
                map_el = page.locator(map_selector).first
                screenshot_bytes = map_el.screenshot(timeout=10000)
            except Exception as e:
                print(f"screenshot failed: {e}")
                continue

            # overlay date and save
            img = Image.open(io.BytesIO(screenshot_bytes))
            dated = overlay_date(img, label)
            safe = label.replace("/", "_").replace(":", "-")
            out = FRAMES / f"{idx:03d}_{safe}.png"
            dated.save(out)
            frames_saved += 1
            print(f"✓ {label}")

        browser.close()

    # ── create video ──
    if frames_saved == 0:
        print("\nNo frames saved – nothing to do.")
        sys.exit(1)

    video = OUT / "timelapse.mp4"
    print(f"\nCreating video ({frames_saved} frames @ 2 fps) …")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", "2",
            "-pattern_type", "glob",
            "-i", f"{FRAMES}/*.png",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    print(f"Done!  {video}  ({frames_saved * 0.5:.1f} s)")


def _format_date(hash_time: str) -> str:
    if not hash_time:
        return "unknown"
    parts = hash_time.split("T")
    if len(parts) == 2:
        hash_time = parts[0] + "T" + parts[1].replace("-", ":")
    try:
        d = datetime.datetime.fromisoformat(hash_time.replace("Z", "+00:00"))
        return d.strftime("%-d %B %Y")
    except Exception:
        return hash_time


if __name__ == "__main__":
    import io as _io
    globals()["io"] = _io
    main()
