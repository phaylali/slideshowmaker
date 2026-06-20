#!/usr/bin/env python3
"""
Eralyon WPlace Timelapse — wplace.eralyon.net
"""

import datetime
import pathlib
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

RUN_TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = pathlib.Path("eralyon_output") / f"run_{RUN_TS}"
FRAMES = OUT / "frames"
FRAMES.mkdir(parents=True, exist_ok=True)

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


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="en-GB",
        )
        page = ctx.new_page()

        page.goto("https://wplace.eralyon.net/", wait_until="domcontentloaded")
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
        print("Navigate to your desired view, then click the red")
        print("[Start Recording] button at the top of the browser.")
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
                    return { zoom: m.getZoom().toFixed(2), lat: center.lat.toFixed(5), lng: center.lng.toFixed(5) };
                }
            }
            const p = new URLSearchParams(location.search);
            return { zoom: p.get('zoom') || '8', lat: p.get('lat') || '31.79', lng: p.get('lng') || '-7.09' };
        }""")
        print(f"  Locked position: zoom={pos['zoom']}  lat={pos['lat']}  lng={pos['lng']}")

        # ── find the slider ──
        slider_info = page.evaluate("""() => {
            const s = document.querySelector('input[type="range"]');
            if (!s) return null;
            return { min: parseInt(s.min), max: parseInt(s.max), val: parseInt(s.value) };
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

        for idx, val in enumerate(range(slider_info["min"], slider_info["max"] + 1)):
            print(f"\n  [{idx + 1}/{total}] slider={val} …", end=" ", flush=True)

            page.evaluate(native_setter_js, val)

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
                pass
            page.wait_for_timeout(2500)

            # read date from the version label
            raw = page.evaluate(
                "() => document.getElementById('wplace-version-label')?.textContent || ''"
            )
            label = _format_date(raw.strip())

            try:
                map_el = page.locator(map_selector).first
                screenshot_bytes = map_el.screenshot(timeout=10000)
            except Exception as e:
                print(f"screenshot failed: {e}")
                continue

            img = Image.open(io.BytesIO(screenshot_bytes))
            dated = overlay_date(img, label)
            safe = label.replace("/", "_").replace(":", "-")
            out = FRAMES / f"{idx:03d}_{safe}.png"
            dated.save(out)
            frames_saved += 1
            print(f"✓ {label}")

        browser.close()

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


def _format_date(raw: str) -> str:
    if not raw:
        return "unknown"
    # raw is like "2026-06-19T01"
    try:
        d = datetime.datetime.strptime(raw, "%Y-%m-%dT%H")
        return d.strftime("%-d %B %Y")
    except Exception:
        pass
    # fallback: try isoformat
    try:
        d = datetime.datetime.fromisoformat(raw)
        return d.strftime("%-d %B %Y")
    except Exception:
        return raw


if __name__ == "__main__":
    import io as _io
    globals()["io"] = _io
    main()
