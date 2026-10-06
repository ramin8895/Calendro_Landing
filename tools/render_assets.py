#!/usr/bin/env python3
"""
Render raster assets with headless Chromium (Playwright):
  - assets/img/logo-192.png, logo-512.png, apple-touch-icon.png, favicon.ico
  - assets/og/<slug>.png  (1200×630 social preview per page) + assets/og/default.png

    pip install playwright && playwright install chromium
    python tools/render_assets.py

Re-run after changing page titles. Not needed for normal builds.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import base64  # noqa: E402
FONT = "data:font/woff2;base64," + base64.b64encode((ROOT / "assets/fonts/Vazirmatn-wght.woff2").read_bytes()).decode()
LOGO = (ROOT / "assets/img/favicon.svg").read_text(encoding="utf-8")

OG_TEMPLATE = """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>
@font-face {{ font-family: V; src: url('{font}') format('woff2'); font-weight: 100 900; }}
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: 1200px; height: 630px; font-family: V; background: #0E3B3B; color: #fff; position: relative; overflow: hidden; }}
.grid {{ position: absolute; inset: 0; background-image: linear-gradient(to left, rgba(255,255,255,.05) 1px, transparent 1px); background-size: calc(1200px / 7) 100%; }}
.wrap {{ position: absolute; inset: 72px 80px; display: flex; flex-direction: column; }}
.brand {{ display: flex; align-items: center; gap: 18px; font-size: 40px; font-weight: 800; }}
.brand svg {{ width: 64px; height: 64px; }}
h1 {{ margin-top: auto; font-size: {size}px; line-height: 1.38; font-weight: 800; max-width: 980px; }}
.foot {{ margin-top: 40px; display: flex; align-items: center; justify-content: space-between; }}
.chips {{ display: flex; gap: 14px; }}
.chip {{ padding: 10px 24px; border-radius: 999px; font-size: 26px; font-weight: 700; background: rgba(255,255,255,.08); color: #CFE3E0; }}
.chip.on {{ background: #FFA12E; color: #0A2F2F; }}
.domain {{ font-size: 28px; color: #B9D3D0; font-weight: 600; letter-spacing: .02em; }}
</style></head><body><div class="grid"></div><div class="wrap">
<div class="brand">{logo}<span>کلندرو</span></div>
<h1>{title}</h1>
<div class="foot"><div class="chips"><span class="chip">۱۰:۰۰</span><span class="chip">۱۱:۳۰</span><span class="chip on">۱۶:۳۰ رزرو شد</span></div><span class="domain">calendro.ir</span></div>
</div></body></html>"""

ICON_TEMPLATE = """<!doctype html><html><head><style>*{{margin:0}}body{{width:{s}px;height:{s}px;background:{bg}}}
svg{{width:{s}px;height:{s}px;display:block}}</style></head><body>{logo}</body></html>"""


def og_title(page: dict) -> str:
    t = page.get("og_title") or page.get("h1") or page["title"]
    t = re.sub(r"^\s*کلندرو\s*\|\s*", "", t)
    return re.sub(r"\s*\|\s*کلندرو\s*$", "", t)


def main() -> None:
    pages = [p for p in build.load_pages() if p["type"] != "404"]
    (ROOT / "assets/og").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(device_scale_factor=1)
        tab = ctx.new_page()

        # Icons: full-bleed square logo (rounded corners come from the SVG itself).
        for size, name in ((192, "logo-192.png"), (512, "logo-512.png")):
            tab.set_viewport_size({"width": size, "height": size})
            tab.set_content(ICON_TEMPLATE.format(s=size, bg="transparent", logo=LOGO))
            tab.screenshot(path=str(ROOT / "assets/img" / name), omit_background=True)
        # Apple touch icon: square, opaque (iOS applies its own mask).
        square = LOGO.replace('rx="11"', 'rx="0"')
        tab.set_viewport_size({"width": 180, "height": 180})
        tab.set_content(ICON_TEMPLATE.format(s=180, bg="#185C5C", logo=square))
        tab.screenshot(path=str(ROOT / "assets/img/apple-touch-icon.png"))
        img = Image.open(ROOT / "assets/img/logo-512.png")
        img.save(ROOT / "assets/img/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

        tab.set_viewport_size({"width": 1200, "height": 630})
        jobs = [("default", "نرم‌افزار نوبت‌دهی آنلاین آرایشگاه، سالن زیبایی و کلینیک")]
        for p in pages:
            slug = "home" if p["path"] == "/" else p["path"].strip("/").replace("/", "-")
            jobs.append((slug, og_title(p)))
        for slug, title in jobs:
            size = 64 if len(title) < 42 else 54 if len(title) < 62 else 46
            tab.set_content(OG_TEMPLATE.format(font=FONT, logo=LOGO, title=html.escape(title), size=size))
            tab.evaluate("document.fonts.ready")
            tab.wait_for_timeout(80)
            out = ROOT / "assets/og" / f"{slug}.png"
            tab.screenshot(path=str(out))
            Image.open(out).convert("RGB").save(out, optimize=True)
        browser.close()
    print(f"rendered icons + {len(jobs)} OG images")


if __name__ == "__main__":
    main()
