#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

SITE="${1:-samuel}"

case "$SITE" in
  samuel|eralyon)
    SCRIPT="${SITE}_playwright.py"
    TITLE="Samuel"  ;;
  *)
    echo "Usage: $0 {samuel|eralyon}"
    echo "  samuel  — wplace.samuelscheit.com  (40 snapshots)"
    echo "  eralyon — wplace.eralyon.net       (250+ snapshots)"
    exit 1
    ;;
esac

echo "======================================="
echo "  WPlace Timelapse — ${TITLE}"
echo "======================================="
echo ""

echo "[1/3] Checking dependencies…"
python3 -c "import PIL" 2>/dev/null || pip3 install --user Pillow 2>&1 | tail -1
python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null || {
    pip3 install --user playwright 2>&1 | tail -1
    python3 -m playwright install chromium 2>&1 | tail -3
}
echo "  OK"

echo ""
echo "[2/3] Launching browser…"
echo ""
echo "  A Chromium window will open to ${TITLE}'s archive."
echo "  👉 Navigate to your desired view (pan & zoom)."
echo "  👉 Click the red [Start Recording] button at the top of the page."
echo ""

python3 "$SCRIPT"

echo ""
echo "[3/3] Done!"
echo "  Find the video in ${SITE}_output/run_$(date +%Y%m%d_%H%M%S)/"
