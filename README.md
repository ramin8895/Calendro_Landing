# Calendro landing — calendro.ir

سایت استاتیک و سئو‌محور کلندرو. HTML خالص + یک فایل CSS + کمی JS، بدون فریم‌ورک و بدون وابستگی خارجی (فونت وزیرمتن لوکال است، هیچ درخواستی به گوگل نمی‌رود).

## ساختار

```
build.py                 # بیلدر (Python 3.9+، فقط کتابخانه استاندارد)
src/layout.html          # قالب مشترک: head، متا، OG، JSON-LD
src/partials/            # هدر، فوتر، بنر CTA، کارت اپ‌ها، لوگو
src/pages/**/index.html  # هر صفحه = یک پوشه (URL تمیز: /features/)
assets/css/main.css      # کل استایل (توکن‌ها روی :root)
assets/js/main.js        # منوی موبایل، دکمه کپی، جمع شدن فهرست مطالب
assets/icons/            # آیکون‌های Lucide (در زمان بیلد inline می‌شوند)
assets/og/               # تصویر اشتراک‌گذاری ۱۲۰۰×۶۳۰ برای هر صفحه
tools/render_assets.py   # ساخت favicon و تصاویر OG با Playwright
deploy/                  # کانفیگ nginx
dist/                    # خروجی بیلد — همین را روی سرور بگذارید
```

## بیلد و اجرا

```bash
python build.py            # خروجی در dist/
python build.py --serve    # بیلد + سرور محلی روی http://localhost:8080
```

بیلد این‌ها را خودکار می‌سازد: `sitemap.xml`، `robots.txt`، `llms.txt`، تگ canonical و OG، اسکیمای JSON-LD (Organization، WebSite، SoftwareApplication، BreadcrumbList، BlogPosting و FAQPage از روی سؤال‌های قابل‌مشاهده صفحه). لینک داخلی خراب، `<h1>` تکراری، `<img>` بدون alt و حروف عربی «ي/ك» را خطا یا هشدار می‌دهد.

## قبل از انتشار، این‌ها را پر کنید

در `build.py`، دیکشنری `SITE`:

| کلید | توضیح |
|---|---|
| `phone`, `phone_href` | شماره تماس (نمایشی و `+98...`). تا خالی باشد، دکمه «تماس برای مشاوره» نمایش داده نمی‌شود |
| `support_hours` | ساعت پاسخگویی |
| `email` | الان `info@calendro.ir` است؛ مطمئن شوید این صندوق واقعاً وجود دارد |
| `instagram`, `telegram`, `bale` | لینک شبکه‌های اجتماعی (خالی = مخفی) |
| `enamad_html` | کد نماد اعتماد الکترونیکی، بعد از دریافت |
| `google_verification`, `bing_verification` | تأیید مالکیت در Search Console و Bing |

لوگو: `assets/img/favicon.svg` و `src/partials/logo-mark.html` یک نشان موقت‌اند. لوگوی اصلی را جایگزین کنید و بعد `python tools/render_assets.py` را اجرا کنید.

## افزودن صفحه یا مقاله

یک پوشه در `src/pages/` بسازید با `index.html` که با بلوک متا شروع می‌شود:

```html
<!--meta
{ "title": "...", "description": "...", "h1": "...", "type": "article",
  "date": "2026-10-20", "nav": "blog",
  "crumbs": [["بلاگ", "/blog/"], ["عنوان کوتاه", "/blog/slug/"]] }
-->
```

- `title` حدود ۴۰ تا ۶۰ کاراکتر، `description` حدود ۱۲۰ تا ۱۶۰ کاراکتر.
- ماکروها: `{{site.key}}`، `{{icon:name}}`، `{{> partial}}`، `{{breadcrumbs}}`، `{{date_fa}}`.
- سؤال‌های `<details class="faq-item">` خودکار وارد اسکیمای FAQPage می‌شوند. برای سؤالی که در صفحه دیگری هم هست، کلاس `faq-item faq-noschema` بگذارید.
- بعد از تغییر عنوان‌ها: `python tools/render_assets.py` تا تصویر OG همان صفحه ساخته شود (نیاز به `pip install playwright` و `playwright install chromium`). بدون آن، تصویر پیش‌فرض استفاده می‌شود.
- مقاله جدید را به `src/pages/blog/index.html` و در صورت نیاز به فوتر اضافه کنید.

## استقرار روی VPS

```bash
python build.py
rsync -avz --delete dist/ user@server:/var/www/calendro-landing/
```

کانفیگ آماده در `deploy/nginx-calendro.ir.conf` است: ریدایرکت www و http به `https://calendro.ir`، اسلش انتهایی یکسان با canonical، gzip، کش یک‌ساله برای CSS/JS نسخه‌دار و صفحه 404.

## چک‌لیست سئو بعد از انتشار

1. `robots.txt` سایت فعلی را بررسی کنید؛ اگر `Disallow: /` دارد، گوگل اصلاً ایندکسش نمی‌کند. فایل جدید همه‌چیز را مجاز می‌کند و نقشه سایت را معرفی می‌کند.
2. سایت را در Google Search Console و Bing Webmaster ثبت و `https://calendro.ir/sitemap.xml` را ارسال کنید.
3. اگر سایت قبلی URLهای دیگری داشته (مثلاً `privacy.html`)، برایشان ریدایرکت ۳۰۱ بگذارید و صفحه حریم خصوصی را نگه دارید؛ کافه‌بازار به لینک حریم خصوصی نیاز دارد.
4. در صفحه هر دو اپ در کافه‌بازار، لینک وب‌سایت را `https://calendro.ir` بگذارید.
5. لینک سایت را در بیوی اینستاگرام و پروفایل‌های کلندرو قرار دهید.
6. نماد اعتماد الکترونیکی بگیرید؛ برای اعتماد مشتری ایرانی اثر واقعی دارد.
7. هر ماه یکی دو مقاله کاربردی اضافه کنید؛ رتبه گرفتن سایت تازه چند ماه طول می‌کشد.
