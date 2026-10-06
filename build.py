#!/usr/bin/env python3
"""
Calendro landing — static site builder (Python 3.9+, standard library only).

    python build.py            # build into ./dist
    python build.py --serve    # build, then serve ./dist on http://localhost:8080

Pages live in src/pages/<path>/index.html. Each page starts with a JSON meta block:

    <!--meta
    { "title": "...", "description": "...", "nav": "features",
      "crumbs": [["امکانات", "/features/"]], "type": "page" }
    -->

Macros available in pages, partials and the layout:
    {{site.key}}              value from SITE below
    {{page.key}}              value from the page's meta block
    {{icon:name}}             inline Lucide icon from assets/icons/<name>.svg
    {{> partial}}             contents of src/partials/<partial>.html
    <!--if:site.key--> ... <!--endif:site.key-->   kept only when site.key is non-empty

The build also writes sitemap.xml, robots.txt, llms.txt, JSON-LD (Organization,
WebSite, SoftwareApplication, BreadcrumbList, FAQPage from visible FAQ items,
BlogPosting), and fails on broken internal links.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"

# ---------------------------------------------------------------------------
# Site settings — edit these. Empty values hide the related UI and are
# reported as warnings at build time.
# ---------------------------------------------------------------------------
SITE = {
    "url": "https://calendro.ir",
    "name": "کلندرو",
    "name_en": "Calendro",
    "tagline": "نرم‌افزار نوبت‌دهی آنلاین آرایشگاه، سالن زیبایی و کلینیک",
    "panel_url": "https://panel.calendro.ir",
    "bazaar_customer": "https://cafebazaar.ir/app/ir.calendro.app",
    "bazaar_center": "https://cafebazaar.ir/app/ir.calendro.centerpanel",
    # Contact — fill these before going live.
    "email": "info@calendro.ir",
    "phone": "",            # e.g. "۰۹۱۲۱۲۳۴۵۶۷" (display form)
    "phone_href": "",       # e.g. "+989121234567" (tel: link form)
    "support_hours": "",    # e.g. "شنبه تا چهارشنبه، ۹ تا ۱۷"
    "city": "",             # e.g. "تهران"
    "instagram": "",        # full URL
    "telegram": "",         # full URL
    "bale": "",             # full URL
    "enamad_html": "",      # paste the e-Namad badge snippet here once issued
    # Search engine verification (content value only)
    "google_verification": "",
    "bing_verification": "",
    "theme_color": "#185C5C",
}

REQUIRED_BEFORE_LAUNCH = ["09145275658", "09145275658", "09145275658"]

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
FA_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def to_fa(s) -> str:
    return str(s).translate(FA_DIGITS)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_label(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{to_fa(jd)} {FA_MONTHS[jm - 1]} {to_fa(jy)}"


TODAY = dt.date.today()
BUILD_JY = gregorian_to_jalali(TODAY.year, TODAY.month, TODAY.day)[0]

WARNINGS: list[str] = []
ERRORS: list[str] = []

META_RE = re.compile(r"^\s*<!--meta\s*(\{.*?\})\s*-->", re.S)
IF_RE = re.compile(r"<!--if:site\.(\w+)-->(.*?)<!--endif:site\.\1-->", re.S)
ICON_RE = re.compile(r"\{\{icon:([a-z0-9-]+)(?:\|([\w -]+))?\}\}")
PARTIAL_RE = re.compile(r"\{\{>\s*([\w-]+)\s*\}\}")
SITE_RE = re.compile(r"\{\{site\.(\w+)\}\}")
RAW_RE = re.compile(r"\{\{raw:site\.(\w+)\}\}")
PAGE_RE = re.compile(r"\{\{page\.(\w+)\}\}")
NAV_RE = re.compile(r"\{\{nav:([\w-]+)\}\}")
FAQ_RE = re.compile(
    r'<details class="faq-item"[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>', re.S)
TAG_RE = re.compile(r"<[^>]+>")

_icon_cache: dict[str, str] = {}


def icon(name: str, cls: str | None = None) -> str:
    if name not in _icon_cache:
        p = ASSETS / "icons" / f"{name}.svg"
        if not p.exists():
            ERRORS.append(f"missing icon: {name}")
            return ""
        svg = p.read_text(encoding="utf-8")
        svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
        svg = re.sub(r'\s*class="[^"]*"', "", svg)
        svg = re.sub(r'\s*(width|height)="24"', "", svg)
        svg = re.sub(r"\s+", " ", svg).replace("> <", "><").strip()
        _icon_cache[name] = svg
    klass = f"icon {cls}" if cls else "icon"
    return _icon_cache[name].replace(
        "<svg ", f'<svg class="{klass}" aria-hidden="true" focusable="false" ', 1)


def render_macros(text: str, page: dict | None = None, depth: int = 0) -> str:
    if depth > 5:
        ERRORS.append("partial include depth exceeded")
        return text

    def partial(m):
        p = SRC / "partials" / f"{m.group(1)}.html"
        if not p.exists():
            ERRORS.append(f"missing partial: {m.group(1)}")
            return ""
        return render_macros(p.read_text(encoding="utf-8"), page, depth + 1)

    text = PARTIAL_RE.sub(partial, text)
    text = IF_RE.sub(lambda m: m.group(2) if SITE.get(m.group(1)) else "", text)
    text = ICON_RE.sub(lambda m: icon(m.group(1), m.group(2)), text)
    text = RAW_RE.sub(lambda m: str(SITE.get(m.group(1), "")), text)  # unescaped (e.g. e-Namad snippet)
    text = SITE_RE.sub(lambda m: html.escape(str(SITE.get(m.group(1), "")), quote=True), text)
    text = text.replace("{{year_fa}}", to_fa(BUILD_JY))
    if page is not None:
        active = page.get("nav", "")
        text = NAV_RE.sub(lambda m: ' aria-current="page"' if m.group(1) == active else "", text)
        text = PAGE_RE.sub(lambda m: html.escape(str(page.get(m.group(1), "")), quote=True), text)
    return text


def plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", fragment))).strip()


def abs_url(path: str) -> str:
    return SITE["url"].rstrip("/") + path


# ---------------------------------------------------------------------------
# Structured data
# ---------------------------------------------------------------------------
def org_ld() -> dict:
    same_as = [SITE[k] for k in ("bazaar_customer", "bazaar_center", "instagram", "telegram", "bale") if SITE.get(k)]
    org = {
        "@type": "Organization",
        "@id": abs_url("/#organization"),
        "name": SITE["name"],
        "alternateName": SITE["name_en"],
        "url": abs_url("/"),
        "logo": abs_url("/assets/img/logo-512.png"),
        "sameAs": same_as,
    }
    contact = {"@type": "ContactPoint", "contactType": "customer support",
               "areaServed": "IR", "availableLanguage": ["fa"]}
    if SITE.get("email"):
        contact["email"] = SITE["email"]
    if SITE.get("phone_href"):
        contact["telephone"] = SITE["phone_href"]
    org["contactPoint"] = contact
    return org


def website_ld() -> dict:
    return {"@type": "WebSite", "@id": abs_url("/#website"), "url": abs_url("/"),
            "name": SITE["name"], "alternateName": SITE["name_en"], "inLanguage": "fa-IR",
            "publisher": {"@id": abs_url("/#organization")}}


def software_ld() -> list[dict]:
    return [
        {"@type": "SoftwareApplication", "name": "کلندرو — اپ نوبت‌گیری مشتریان",
         "applicationCategory": "LifestyleApplication", "operatingSystem": "Android",
         "inLanguage": "fa-IR", "downloadUrl": SITE["bazaar_customer"],
         "publisher": {"@id": abs_url("/#organization")}},
        {"@type": "SoftwareApplication", "name": "کلندرو — پنل مدیریت مرکز",
         "applicationCategory": "BusinessApplication", "operatingSystem": "Android, Web",
         "inLanguage": "fa-IR", "downloadUrl": SITE["bazaar_center"], "url": SITE["panel_url"],
         "publisher": {"@id": abs_url("/#organization")}},
    ]


def breadcrumb_ld(crumbs: list) -> dict:
    items = [{"@type": "ListItem", "position": i + 1, "name": n, "item": abs_url(p)}
             for i, (n, p) in enumerate(crumbs)]
    return {"@type": "BreadcrumbList", "itemListElement": items}


def faq_ld(body: str) -> dict | None:
    qa = FAQ_RE.findall(body)
    if not qa:
        return None
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": plain(q),
         "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in qa]}


def article_ld(page: dict, url: str, image: str) -> dict:
    return {"@type": "BlogPosting", "headline": page["h1"] if page.get("h1") else page["title"],
            "description": page["description"], "inLanguage": "fa-IR",
            "datePublished": page["date"], "dateModified": page.get("updated", page["date"]),
            "mainEntityOfPage": url, "image": image,
            "author": {"@type": "Organization", "name": "تیم کلندرو", "url": abs_url("/about/")},
            "publisher": {"@id": abs_url("/#organization")}}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def page_path(src_file: Path) -> str:
    rel = src_file.parent.relative_to(SRC / "pages").as_posix()
    if src_file.name == "404.html":
        return "/404.html"
    return "/" if rel == "." else f"/{rel}/"


def load_pages() -> list[dict]:
    pages = []
    for f in sorted((SRC / "pages").rglob("*.html")):
        raw = f.read_text(encoding="utf-8")
        m = META_RE.match(raw)
        if not m:
            ERRORS.append(f"{f}: missing <!--meta {{...}} --> block")
            continue
        try:
            meta = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            ERRORS.append(f"{f}: bad meta JSON: {e}")
            continue
        meta["path"] = page_path(f)
        meta["body_src"] = raw[m.end():]
        meta.setdefault("type", "page")
        pages.append(meta)
    return pages


def asset_version(*files: Path) -> str:
    h = hashlib.sha1()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


def render_breadcrumbs(crumbs: list) -> str:
    if len(crumbs) < 2:
        return ""
    parts = []
    for i, (name, path) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            parts.append(f'<li><span aria-current="page">{html.escape(name)}</span></li>')
        else:
            parts.append(f'<li><a href="{path}">{html.escape(name)}</a></li>')
    return ('<nav class="breadcrumbs" aria-label="مسیر صفحه"><ol>' + "".join(parts) + "</ol></nav>")


def lint(page: dict, out_html: str) -> None:
    where = page["path"]
    t, d = page.get("title", ""), page.get("description", "")
    if not 20 <= len(t) <= 70:
        WARNINGS.append(f"{where}: title length {len(t)} (aim 30–65)")
    if page["type"] != "404" and not 70 <= len(d) <= 170:
        WARNINGS.append(f"{where}: description length {len(d)} (aim 110–160)")
    h1 = len(re.findall(r"<h1[\s>]", out_html))
    if h1 != 1:
        ERRORS.append(f"{where}: expected exactly one <h1>, found {h1}")
    for img in re.findall(r"<img\b[^>]*>", out_html):
        if " alt=" not in img:
            ERRORS.append(f"{where}: <img> without alt: {img[:80]}")
    if re.search(r"[يك]", plain(out_html)):
        WARNINGS.append(f"{where}: Arabic ي/ك found — use Persian ی/ک")


def build() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(ASSETS, DIST / "assets", ignore=shutil.ignore_patterns("icons", "*.md"))
    for name in ("favicon.svg", "favicon.ico", "apple-touch-icon.png", "site.webmanifest"):
        src = ASSETS / "img" / name
        if src.exists():
            shutil.copy2(src, DIST / name)

    layout = (SRC / "layout.html").read_text(encoding="utf-8")
    ver = asset_version(ASSETS / "css" / "main.css", ASSETS / "js" / "main.js")
    pages = load_pages()

    for page in pages:
        url = abs_url(page["path"]) if page["type"] != "404" else abs_url("/")
        crumbs = [["خانه", "/"]] + page.get("crumbs", [])
        body = render_macros(page["body_src"], page)

        slug = "home" if page["path"] == "/" else page["path"].strip("/").replace("/", "-")
        og_rel = f"/assets/og/{slug}.png"
        og_image = abs_url(og_rel if (ASSETS / "og" / f"{slug}.png").exists() else "/assets/og/default.png")

        graph: list[dict] = []
        if page["path"] == "/":
            graph += [org_ld(), website_ld(), *software_ld()]
        else:
            graph.append({"@type": "WebPage", "@id": url, "url": url, "name": page["title"],
                          "description": page["description"], "inLanguage": "fa-IR",
                          "isPartOf": {"@id": abs_url("/#website")}})
        if len(crumbs) > 1:
            graph.append(breadcrumb_ld(crumbs))
        if page["type"] == "article":
            graph.append(article_ld(page, url, og_image))
        faq = faq_ld(body)
        if faq:
            graph.append(faq)
        graph += page.get("schema", [])
        json_ld = ""
        if page["type"] != "404":
            json_ld = ('<script type="application/ld+json">'
                       + json.dumps({"@context": "https://schema.org", "@graph": graph},
                                    ensure_ascii=False, separators=(",", ":"))
                       + "</script>")

        if page["type"] == "article":
            page["date_fa"] = jalali_label(page["date"])
            page["updated_fa"] = jalali_label(page.get("updated", page["date"]))

        robots = "noindex, follow" if page["type"] == "404" else \
            "index, follow, max-image-preview:large, max-snippet:-1"
        verify = ""
        if SITE["google_verification"]:
            verify += f'<meta name="google-site-verification" content="{SITE["google_verification"]}">'
        if SITE["bing_verification"]:
            verify += f'<meta name="msvalidate.01" content="{SITE["bing_verification"]}">'

        out = layout
        out = out.replace("{{content}}", body)
        out = out.replace("{{breadcrumbs}}", render_breadcrumbs(crumbs) if page["type"] != "home" else "")
        out = render_macros(out, page)
        out = (out.replace("{{canonical}}", url)
                  .replace("{{og_image}}", og_image)
                  .replace("{{og_type}}", "article" if page["type"] == "article" else "website")
                  .replace("{{json_ld}}", json_ld)
                  .replace("{{robots}}", robots)
                  .replace("{{verification}}", verify)
                  .replace("{{ver}}", ver)
                  .replace("{{body_class}}", f"page-{page['type']}"))
        if page["type"] == "article":
            out = out.replace("</head>",
                              f'<meta property="article:published_time" content="{page["date"]}">'
                              f'<meta property="article:modified_time" content="{page.get("updated", page["date"])}">'
                              "</head>")
        out = out.replace("{{date_fa}}", page.get("date_fa", "")).replace("{{updated_fa}}", page.get("updated_fa", ""))
        leftovers = re.findall(r"\{\{[^}]+\}\}", out)
        if leftovers:
            ERRORS.append(f"{page['path']}: unresolved macros {sorted(set(leftovers))}")

        lint(page, out)
        target = DIST / ("404.html" if page["type"] == "404" else page["path"].lstrip("/") + "index.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
        page["out"] = target

    indexable = [p for p in pages if p["type"] != "404"]
    write_sitemap(indexable)
    write_robots()
    write_llms(indexable)
    check_links(pages)
    return report(len(pages))


def write_sitemap(pages: list[dict]) -> None:
    rows = []
    for p in sorted(pages, key=lambda x: (-float(x.get("priority", 0.6)), x["path"])):
        lastmod = p.get("updated", p.get("date", TODAY.isoformat()))
        rows.append(f"  <url><loc>{abs_url(p['path'])}</loc><lastmod>{lastmod}</lastmod>"
                    f"<priority>{p.get('priority', 0.6)}</priority></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(rows) + "\n</urlset>\n")
    (DIST / "sitemap.xml").write_text(xml, encoding="utf-8")


def write_robots() -> None:
    (DIST / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {abs_url('/sitemap.xml')}\n", encoding="utf-8")


def write_llms(pages: list[dict]) -> None:
    lines = [f"# {SITE['name']} ({SITE['name_en']})", "",
             f"> {SITE['tagline']}. کلندرو یک سامانه نوبت‌دهی آنلاین فارسی برای مراکز خدماتی ایران است: "
             "مشتری از اپ اندروید کلندرو نوبت می‌گیرد و مرکز نوبت‌ها، خدمات، پرسنل و شیفت‌ها را در پنل "
             "موبایل یا وب مدیریت می‌کند.", ""]
    groups = {"صفحات اصلی": [], "راهنما": [], "کاربردها": [], "بلاگ": []}
    for p in pages:
        key = ("راهنما" if p["path"].startswith("/guide/") else
               "کاربردها" if p["path"].startswith("/for/") else
               "بلاگ" if p["path"].startswith("/blog/") else "صفحات اصلی")
        groups[key].append(f"- [{p['title']}]({abs_url(p['path'])}): {p['description']}")
    for k, v in groups.items():
        if v:
            lines += [f"## {k}", *v, ""]
    (DIST / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def check_links(pages: list[dict]) -> None:
    href_re = re.compile(r'(?:href|src)="(/[^"#?]*)')
    for p in pages:
        text = p["out"].read_text(encoding="utf-8")
        for link in set(href_re.findall(text)):
            if link.startswith("//"):
                continue
            target = DIST / link.lstrip("/")
            if link.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                ERRORS.append(f"{p['path']}: broken internal link {link}")
        for anchor in set(re.findall(r'href="#([\w-]+)"', text)):
            if f'id="{anchor}"' not in text:
                ERRORS.append(f"{p['path']}: missing anchor #{anchor}")


def report(n: int) -> int:
    missing = [k for k in REQUIRED_BEFORE_LAUNCH if not SITE.get(k)]
    if missing:
        WARNINGS.append("contact fields still empty in SITE: " + ", ".join(missing))
    for w in WARNINGS:
        print(f"  warn  {w}")
    for e in ERRORS:
        print(f"  ERROR {e}")
    print(f"built {n} pages into {DIST.relative_to(ROOT)}/ — {len(ERRORS)} errors, {len(WARNINGS)} warnings")
    return 1 if ERRORS else 0


def serve() -> None:
    import functools
    import http.server

    class Handler(http.server.SimpleHTTPRequestHandler):
        def send_error(self, code, message=None, explain=None):
            if code == 404 and (DIST / "404.html").exists():
                body = (DIST / "404.html").read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().send_error(code, message, explain)

    handler = functools.partial(Handler, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("0.0.0.0", 8080), handler) as httpd:
        print("serving dist/ on http://localhost:8080 (Ctrl+C to stop)")
        httpd.serve_forever()


if __name__ == "__main__":
    code = build()
    if "--serve" in sys.argv and code == 0:
        serve()
    sys.exit(code)
