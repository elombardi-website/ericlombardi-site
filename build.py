#!/usr/bin/env python3
"""ericlombardi.ca — static site generator. Standard library only.

    python3 build.py                   # build docs/
    python3 build.py --base /repo --domain https://user.github.io/repo
                                       # test build for GitHub project pages (no CNAME written)
    python3 build.py --drafts          # include posts marked  draft: true
    python3 build.py --placeholders    # include sample events marked "placeholder": true (preview only)
    python3 build.py --out build/local # write somewhere other than docs/

Content: content/   Design: assets/   Output: docs/  (served by GitHub Pages)
"""
import datetime as dt
import email.utils
import html as hm
import json
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
CONTENT, ASSETS = HERE / "content", HERE / "assets"
ARGS = sys.argv[1:]
OUT = pathlib.Path(ARGS[ARGS.index("--out") + 1]).resolve() if "--out" in ARGS else HERE / "docs"
BASE = ARGS[ARGS.index("--base") + 1].rstrip("/") if "--base" in ARGS else ""
DOMAIN_OVERRIDE = ARGS[ARGS.index("--domain") + 1].rstrip("/") if "--domain" in ARGS else ""
INCLUDE_DRAFTS = "--drafts" in ARGS
INCLUDE_PLACEHOLDERS = "--placeholders" in ARGS   # sample events are excluded unless asked for


def load_json(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


SITE = load_json("site.json")
STRINGS = load_json("strings.json")   # every piece of interface copy; edited through the copy workbook
from urllib.parse import quote as urlq


def R(key, **kw):
    """Raw copy string from strings.json ("group.key"); tokens in {braces} are filled from kw."""
    g, k = key.split(".", 1)
    t = STRINGS[g][k]["text"]
    return t.format(**kw) if kw else t


def S(key, **kw):
    """HTML-escaped copy string for text content; kw values are inserted unescaped (for links)."""
    g, k = key.split(".", 1)
    t = hm.escape(STRINGS[g][k]["text"], quote=False)
    return t.format(**kw) if kw else t
DOMAIN = DOMAIN_OVERRIDE or SITE["domain"].rstrip("/")
NAME = SITE["name"]
EMAIL = SITE["email"]
TODAY = dt.date.today()
NOW = dt.datetime.now(dt.timezone.utc)
SITEMAP = []     # (url, lastmod date)
WARN = []
PERSON_ID = DOMAIN + "/#person"
SITE_ID = DOMAIN + "/#website"


# --------------------------------------------------------------------------- helpers
def warn(msg): WARN.append(msg)
def esc(s): return hm.escape("" if s is None else str(s), quote=True)
def u(path): return "" if not path else ((BASE + path) if path.startswith("/") else path)
def absu(path): return path if path.startswith("http") else DOMAIN + path
def slugify(s): return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
def truthy(v): return str(v).strip().lower() in ("1", "true", "yes")
def strip_tags(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
def reading_time(h): return max(1, round(len(strip_tags(h).split()) / 230))
def localize(h):
    """Prefix site-relative src/href with BASE, skipping ones u() already prefixed."""
    if not BASE:
        return h
    pat = r'(src|href)="/(?!/)(?!' + re.escape(BASE.lstrip("/")) + r'/)'
    return re.sub(pat, lambda m: f'{m.group(1)}="{BASE}/', h)
def absolutize(h): return re.sub(r'(src|href)="/(?!/)', lambda m: f'{m.group(1)}="{DOMAIN}/', h)


def parse_date(s):
    s = str(s).strip()
    for f in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date: {s!r}")


def parse_time(t):
    if not t:
        return None
    t = t.strip().lower().replace(".", "")
    for f in ("%I:%M %p", "%I %p", "%H:%M", "%I:%M%p", "%I%p"):
        try:
            return dt.datetime.strptime(t, f).time()
        except ValueError:
            pass
    return None


def fmt_date(d): return f"{d:%B} {d.day}, {d.year}"
def rfc822(d): return email.utils.format_datetime(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc))


def write(path, text):
    p = OUT / path.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def page_file(url):
    return (url.strip("/") + "/index.html") if url.endswith("/") else url.lstrip("/")


# --------------------------------------------------------------------------- markdown
def inline(s):
    parts = re.split(r"(`[^`]+`)", s)
    out = []
    for p in parts:
        if len(p) > 1 and p.startswith("`") and p.endswith("`"):
            out.append("<code>" + hm.escape(p[1:-1]) + "</code>")
            continue
        p = re.sub(r"&(?![a-zA-Z#][a-zA-Z0-9]*;)", "&amp;", p)
        p = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', p)
        p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", r'<a href="\2">\1</a>', p)
        p = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", p)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", p)
        p = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", p)
        p = re.sub(r"(^|\s)--(\s|$)", r"\1&#8212;\2", p)
        out.append(p)
    return "".join(out)


LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
INLINE_TAGS = r"<(a|em|strong|b|i|span|code|img|br|small|sup|sub)\b"


def parse_list(lines, i):
    base = len(lines[i]) - len(lines[i].lstrip())
    ordered = bool(re.match(r"\s*\d+[.)]\s", lines[i]))
    items = []
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            m = LIST_RE.match(nxt)
            if m and len(m.group(1)) >= base:
                i += 1
                continue
            break
        indent = len(line) - len(line.lstrip())
        m = LIST_RE.match(line)
        if m and indent == base:
            items.append({"text": m.group(3), "sub": ""})
            i += 1
        elif indent > base and items:
            if m:
                sub, i = parse_list(lines, i)
                items[-1]["sub"] += sub
            else:
                items[-1]["text"] += " " + line.strip()
                i += 1
        else:
            break
    tag = "ol" if ordered else "ul"
    body = "".join(f"<li>{inline(it['text'])}{it['sub']}</li>" for it in items)
    return f"<{tag}>{body}</{tag}>", i


def md_to_html(md):
    lines = md.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            lang = s[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{hm.escape(chr(10).join(buf))}</code></pre>")
            continue
        if re.match(r"^#{1,6}\s*[*_]*\s*$", s):      # an empty heading line (e.g. "###" or "### ****") is dropped
            i += 1
            continue
        m = re.match(r"(#{1,6})\s+(.*?)\s*#*$", s)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^(?:\[)?!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)(?:\]\(([^)\s]+)\))?\s*$", s)
        if m:
            alt, src, cap, href = m.group(1), m.group(2), m.group(3), m.group(4)
            img = f'<img src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'
            if href:
                img = f'<a href="{esc(href)}" target="_blank" rel="noopener">{img}</a>'
            capt = f"<figcaption>{inline(cap)}</figcaption>" if cap else ""
            out.append(f"<figure>{img}{capt}</figure>")
            i += 1
            continue
        if s.startswith("<") and not re.match(INLINE_TAGS, s):
            buf = [line]
            i += 1
            while i < n and lines[i].strip():
                buf.append(lines[i])
                i += 1
            blk = "\n".join(buf)
            if blk.lstrip().startswith("<iframe"):
                blk = f'<div class="embed">{blk}</div>'
            out.append(blk)
            continue
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{md_to_html(chr(10).join(buf))}</blockquote>")
            continue
        if LIST_RE.match(line):
            block, i = parse_list(lines, i)
            out.append(block)
            continue
        buf = [s]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|!\[|```|\[!\[|<(?!(a|em|strong|b|i|span|code|br|small|sup|sub)\b))", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")
    h = "\n".join(out)
    levels = [int(x) for x in re.findall(r"<h([1-6])>", h)]
    if levels and min(levels) != 2:       # normalise so the body's top heading level is h2 under the page's h1
        shift = 2 - min(levels)
        h = re.sub(r"<(/?)h([1-6])>", lambda m: f"<{m.group(1)}h{min(6, max(2, int(m.group(2)) + shift))}>", h)
    return h


def read_md(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
    meta = {}
    if m:
        for line in m.group(1).split("\n"):
            k, sep, v = line.partition(":")
            if sep:
                meta[k.strip()] = v.strip().strip('"')
        body = m.group(2)
    else:
        body = raw
    return meta, body


# --------------------------------------------------------------------------- content
def load_posts():
    posts = []
    for p in sorted((CONTENT / "posts").glob("*.md")):
        meta, body = read_md(p)
        if truthy(meta.get("draft", "")) and not INCLUDE_DRAFTS:
            continue
        cat = slugify(meta.get("category", "notes"))
        if cat not in SITE["categories"]:
            warn(f"post {p.name}: category '{cat}' is not in site.json categories")
        html_body = md_to_html(body)
        posts.append({
            "slug": p.stem, "title": meta["title"], "date": parse_date(meta["date"]),
            "updated": parse_date(meta["updated"]) if meta.get("updated") else None,
            "category": cat, "category_label": SITE["categories"].get(cat, meta.get("category", "Notes")),
            "summary": meta.get("summary", ""), "image": meta.get("image", ""),
            "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
            "origin": meta.get("origin", ""), "canonical": meta.get("canonical", ""), "featured": truthy(meta.get("featured", "")), "canonical_external": meta.get("canonical_external", ""),
            "html": html_body, "url": f"/writing/{p.stem}/", "words": len(strip_tags(html_body).split()),
        })
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def load_media():
    items = load_json("media.json")
    for it in items:
        it["d"] = parse_date(it["date"])
        it.setdefault("format", "online")
        it.setdefault("campaign", False)
    items.sort(key=lambda x: x["d"], reverse=True)
    return items


def load_events():
    evs = [e for e in load_json("events.json") if INCLUDE_PLACEHOLDERS or not e.get("placeholder")]
    for e in evs:
        e["d"] = parse_date(e["date"])
        e["end_d"] = parse_date(e["end"]) if e.get("end") else None
        e["slug"] = slugify(f"{e['date']}-{e['title']}")
        e["past"] = (e["end_d"] or e["d"]) < TODAY
        if e.get("placeholder"):
            warn(f"event '{e['title']}' is a sample and is being published because --placeholders was given")
    evs.sort(key=lambda x: x["d"])
    return evs


def load_policy():
    idx_meta, idx_body = read_md(CONTENT / "policy" / "_index.md")
    items = []
    for p in sorted((CONTENT / "policy").glob("*.md")):
        if p.name.startswith("_"):
            continue
        meta, body = read_md(p)
        links = []
        for chunk in (meta.get("links", "") or "").split(";"):
            bits = [b.strip() for b in chunk.split("|")]
            if len(bits) >= 2 and bits[0]:
                links.append({"label": bits[0], "url": bits[1], "primary": len(bits) > 2 and bits[2] == "primary"})
        items.append({**meta, "slug": p.stem, "order": int(meta.get("order", 99)), "links": links,
                      "gallery": [g.strip() for g in (meta.get("gallery", "") or "").split(",") if g.strip()],
                      "html": md_to_html(body), "url": f"/policy/{p.stem}/"})
    items.sort(key=lambda x: x["order"])
    return idx_meta, md_to_html(idx_body), items


# --------------------------------------------------------------------------- layout
# Decorative SVG family: orthogonal lines, open arcs, a stepped edge. aria-hidden, no pointer events.
DECAL_ARC = ('<svg class="decal decal-arc" viewBox="0 0 320 320" aria-hidden="true" focusable="false">'
             '<path d="M0 320A320 320 0 0 1 320 0"/></svg>')
# Line symbols: one construction. Ink starts at x=0.625 (so it sits on the text edge) and stands on y=43.375.
SYMBOLS = {
    "grid": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M0.625 0.625H43.375V43.375H0.625ZM0.625 14.875H43.375M0.625 29.125H43.375M14.875 0.625V43.375M29.125 0.625V43.375"/></svg>',
    "lines": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M0.625 7H43.375M0.625 19H33M0.625 31H43.375M0.625 43.375H22"/></svg>',
    "portal": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M0.625 43.375V22A21.375 21.375 0 0 1 43.375 22V43.375M11.5 43.375V27M32.5 43.375V27"/></svg>',
    "steps": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M0.625 43.375V29.125H14.875V14.875H29.125V0.625H43.375M0.625 43.375H43.375"/></svg>',
}


def analytics_snippet():
    a = SITE.get("analytics", {})
    if not a.get("enabled"):
        return ""
    if a.get("provider") == "simpleanalytics":
        return ('<script async src="https://scripts.simpleanalyticscdn.com/latest.js"></script>\n'
                '<noscript><img src="https://queue.simpleanalyticscdn.com/noscript.gif" alt="" referrerpolicy="no-referrer-when-downgrade"></noscript>')
    return a.get("custom_snippet", "")


def tracking_line():
    """Footer statement that reflects what is actually enabled."""
    a = bool(SITE.get("analytics", {}).get("enabled"))
    x = bool(SITE.get("x_feed", {}).get("enabled"))
    if not a and not x:
        return S("site.tracking_none")
    parts = []
    if a:
        parts.append(S("site.tracking_analytics"))
    if x:
        parts.append(S("site.tracking_x"))
    return S("site.tracking_some") + " " + " and ".join(parts) + "."


def head_meta(title, description, path, image=None, kind="website", reading=False, campaign=False):
    canonical = absu(path)
    img = absu(image or SITE["og_image"])
    reading_css = (f'\n<link rel="stylesheet" href="{u("/assets/css/reading.css")}">' if reading else "") + (f'\n<link rel="stylesheet" href="{u("/assets/css/campaign.css")}">' if campaign else "")
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta name="author" content="{esc(NAME)}">
<meta name="robots" content="{"noindex, nofollow" if BASE else "index, follow, max-image-preview:large"}">
<meta name="theme-color" content="#F5F1E8">
<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{img}">
<meta property="og:locale" content="en_CA">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@{SITE['x_handle']}">
<meta name="twitter:creator" content="@{SITE['x_handle']}">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{img}">
<link rel="icon" href="{u('/assets/img/favicon.png')}" type="image/png">
<link rel="apple-touch-icon" href="{u('/assets/img/favicon.png')}">
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}: writing" href="{absu('/feed.xml')}">
<link rel="alternate" type="application/feed+json" title="{esc(NAME)}: writing" href="{absu('/feed.json')}">
<link rel="preload" href="{u('/assets/fonts/canela/Canela-Regular-Web.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{u('/assets/fonts/manrope/Manrope-latin.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{u('/assets/css/theme.css')}">
<link rel="stylesheet" href="{u('/assets/css/site.css')}">{reading_css}
{analytics_snippet()}"""


def nav_links(current=""):
    return "".join(
        f'<a href="{u(n["href"])}"{" aria-current=\"page\"" if n["href"] == current else ""}>{esc(n["label"])}</a>'
        for n in SITE["nav"])


def header_html(current=""):
    links = nav_links(current)
    sup = ' aria-current="page"' if current == "/support/" else ""
    about = ' aria-current="page"' if current == "/about/" else ""
    return f"""<header class="site-header"><div class="wrap">
  <a class="wordmark" href="{u('/')}">{esc(NAME)}</a>
  <nav class="primary" aria-label="Primary">{links}</nav>
  <a class="btn sm secondary header-cta" href="{u('/support/')}"{sup}>{S("site.header_support")}</a>
  <button class="burger" type="button" aria-label="{S('site.menu')}" aria-expanded="false" aria-controls="mobile-nav"><span></span><span></span><span></span></button>
</div>
<nav class="mobile" id="mobile-nav" aria-label="Mobile">{links}<a href="{u('/about/')}"{about}>{S("site.mobile_about")}</a><a class="btn secondary" href="{u('/support/')}"{sup}>{S("site.mobile_support")}</a></nav>
</header>"""


def footer_html():
    """Explore = the sections, About and In the media. Stay in touch = contact, sign-up, support and the feeds.
    Follow = networks only. Each destination appears once."""
    socials = "".join(f'<a href="{esc(s["url"])}" rel="me noopener" target="_blank">{esc(s["name"])}</a>'
                      for s in SITE["socials"] if s.get("show", True))
    explore = "".join(f'<a href="{u(n["href"])}">{esc(n["label"])}</a>' for n in SITE["nav"] if n["href"] != "/contact/")
    explore += f'<a href="{u("/media/")}">{S("site.footer_media_link")}</a><a href="{u("/about/")}">{S("site.footer_about_link")}</a>'
    stay = (f'<a href="{u("/contact/")}">{S("site.contact_link")}</a><a href="{u("/support/#signup")}">{S("site.footer_signup")}</a>'
            f'<a href="{u("/support/")}">{S("site.footer_support")}</a><a href="{u("/feed.xml")}">{S("site.footer_rss")}</a>'
            f'<a href="{u("/events.ics")}">{S("site.footer_calendar")}</a>')
    return f"""<footer class="site-footer"><div class="wrap">
  {PLINTH}
  <div class="footer-grid">
    <div class="f-brand"><a class="wordmark" href="{u('/')}">{esc(NAME)}</a><p class="about">{esc(SITE['short_description'])}</p></div>
    <div class="f-group"><h2 class="t-label f-title">{S("site.footer_explore")}</h2><nav aria-label="{S('site.footer_explore')}">{explore}</nav></div>
    <div class="f-group"><h2 class="t-label f-title">{S("site.footer_follow")}</h2><div class="links">{socials}</div></div>
    <div class="f-group"><h2 class="t-label f-title">{S("site.footer_stay")}</h2><div class="links">{stay}</div></div>
  </div>
  <p class="fine">&copy; {TODAY.year} {esc(NAME)}. {esc(SITE['location']['label'])}. <a href="{u('/privacy/')}">{S("site.footer_privacy")}</a> &middot; <a href="{u('/llms.txt')}">llms.txt</a> &middot; <a href="{u('/sitemap.xml')}">{S("site.footer_sitemap")}</a>. {tracking_line()}</p>
</div></footer>"""


SECTION_TITLES = {"/consulting/": "Consulting", "/writing/": "Writing and media", "/media/": "In the media", "/policy/": "Public policy",
                  "/events/": "Events", "/support/": "Support", "/about/": "About", "/contact/": "Contact", "/privacy/": "Privacy"}


def breadcrumb_ld(path, title):
    """Breadcrumbs from real pages only: segments with no page of their own (like /writing/category/) are skipped."""
    if path.endswith(".html"):
        return None
    parts = [p for p in path.strip("/").split("/") if p]
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": DOMAIN + "/"}]
    acc = ""
    for p in parts:
        acc += "/" + p
        here = acc + "/"
        if here == path:
            name = title.replace(f" | {NAME}", "")
        elif here in SECTION_TITLES:
            name = SECTION_TITLES[here]
        else:
            continue
        items.append({"@type": "ListItem", "position": len(items) + 1, "name": name, "item": DOMAIN + here})
    return {"@type": "BreadcrumbList", "itemListElement": items}


def person_ld():
    return {"@type": "Person", "@id": PERSON_ID, "name": NAME, "url": DOMAIN + "/",
            "image": absu("/assets/img/eric-headshot.jpg"), "jobTitle": SITE["job_title"],
            "description": SITE["short_description"],
            "address": {"@type": "PostalAddress", "addressLocality": SITE["location"]["city"],
                        "addressRegion": SITE["location"]["region"], "addressCountry": SITE["location"]["country"]},
            "alumniOf": {"@type": "CollegeOrUniversity", "name": "University of Waterloo"},
            "sameAs": [s["url"] for s in SITE["socials"] if s.get("show", True)],
            "knowsAbout": SITE["knows_about"]}


def render(title, description, body, *, path, current="", image=None, kind="website", jsonld=None, lastmod=None, body_class="", sitemap=True, reading=False, campaign=False):
    page = {"@type": "WebPage", "@id": absu(path), "url": absu(path), "name": title, "description": description,
            "isPartOf": {"@id": SITE_ID}, "about": {"@id": PERSON_ID}, "inLanguage": "en-CA"}
    crumbs = breadcrumb_ld(path, title)
    if crumbs:
        page["breadcrumb"] = crumbs
    graph = [person_ld(), {"@type": "WebSite", "@id": SITE_ID, "url": DOMAIN + "/", "name": NAME, "publisher": {"@id": PERSON_ID}, "inLanguage": "en-CA"}, page]
    graph += jsonld or []
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")
    if 'style="' in re.sub(r"<iframe\b[^>]*>", "", body):     # embeds from third parties keep their own
        warn(f"{path}: inline style attribute in the page body (use a class)")
    doc = f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
{head_meta(title, description, path, image, kind, reading, campaign)}
<script type="application/ld+json">{ld}</script>
</head>
<body class="{body_class}" data-m="{EMAIL[::-1]}">
<a class="skip" href="#main">{S("site.skip_link")}</a>
{header_html(current)}
<main id="main">
{localize(body)}
</main>
{footer_html()}
<script src="{u('/assets/js/site.js')}" defer></script>
</body>
</html>
"""
    write(page_file(path), doc)
    if sitemap:
        SITEMAP.append((path, lastmod or TODAY))


# --------------------------------------------------------------------------- components
# Every page is assembled from these. Each component has one definition; pages only choose content.
LIST_LIMIT = 3       # every capped list shows three, then "Show more" (Eric, 26 Oct)
HOME_PREVIEW = 3     # every home-page preview shows three
LIST_BATCH = 10      # "Show more" reveals ten at a time; a remainder of three or fewer comes along


def T(s):
    return f"{s} | {NAME}"


def label(text, rule=False, href=None):
    inner = f'<a href="{u(href)}">{text}</a>' if href else text
    return f'<p class="label{" rule" if rule else ""}">{inner}</p>'


def nowrap(s):
    return f'<span class="nowrap">{s}</span>'


def meta_line(*parts, cls=""):
    """One meta line: parts separated by a bronze dot that stays with the part before it."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    spans = "".join(p if p.startswith("<span") else f"<span>{p}</span>" for p in parts)
    return f'<p class="meta{(" " + cls) if cls else ""}">{spans}</p>'


def link_to(text, href, cls="more", download=False):
    """A quiet text link with the site's arrow convention: → internal, ↗ external (new tab), ↓ download."""
    ext = href.startswith("http")
    arrow = " &#8595;" if download else (" &#8599;" if ext else " &rarr;")
    attrs = (' target="_blank" rel="noopener"' if ext else "") + (" download" if download else "")
    return f'<a class="{cls}" href="{esc(href) if ext else u(href)}"{attrs}>{text}{arrow}</a>'


def status_p():
    return '<p class="status" role="status" aria-live="polite"></p>'


def section_head(title, kicker=None, intro=None, aside=None, tier="section", level=2, hidden=False, intro_cls="t-lede", rule=True):
    """The one section head. tier: 'section' (major), 'minor' (secondary or in a column), or a role class
    such as 't-label' (a band or group label). Kickers are ruled, except at the top of a ruled column."""
    if hidden:
        return f'<div class="section-head is-hidden"><h{level} class="visually-hidden">{title}</h{level}></div>'
    cls = {"section": "t-section", "minor": "t-sub"}.get(tier, tier)
    k = label(kicker, rule=rule) if kicker else ""
    i = f'<p class="sh-intro {intro_cls}">{intro}</p>' if intro else ""
    a = f'<div class="sh-aside">{aside}</div>' if aside else ""
    extra = " is-label" if tier == "t-label" else ""
    return f'<div class="section-head{extra}"><div class="sh-text">{k}<h{level} class="{cls}">{title}</h{level}>{i}</div>{a}</div>'


def nup_spans(n, i):
    """Column spans (md, lg, xl) for item i of an n-item row. One table for every count."""
    table = {1: ("12", "12", "12"), 2: ("6", "6", "6"), 3: ("12", "4", "4"), 4: ("6", "6", "3"), 6: ("6", "4", "4"), 8: ("6", "6", "3")}
    if n == 5:
        return ("12" if i == 4 else "6", "4" if i < 3 else "6", "4" if i < 3 else "6")
    if n == 7:
        return ("12" if i == 6 else "6", "12" if i == 6 else "4", "3" if i < 4 else "4")
    if n not in table:
        warn(f"n-up row with {n} items: using 6/4/4")
        return ("6", "4", "4")
    return table[n]


def nup(items, level=3, title_cls="t-sub", cls=""):
    """N-up row. Each item has four slots in fixed order (mark, title, body, action) so rows share lines.
    item = {mark, title (html; may hold an a.stretch for a whole-card link), body (html), action (html), card}."""
    n, out = len(items), ""
    for i, it in enumerate(items):
        md, lg, xl = nup_spans(n, i)
        extra = (" is-alone" if n == 1 or (n == 7 and i == 6) else "") + (" card" if it.get("card") else "")
        out += (f'<div class="nup-item s-md-{md} s-lg-{lg} s-xl-{xl}{extra}">'
                f'<div class="n-mark">{it.get("mark", "")}</div><h{level} class="n-title {title_cls}">{it["title"]}</h{level}>'
                f'<div class="n-body">{it.get("body", "")}</div><div class="n-action">{it.get("action", "")}</div></div>')
    return f'<div class="nup{(" " + cls) if cls else ""}">{out}</div>'


def block(title, body="", kicker=None, actions="", variant="rail", level=3, title_cls="t-block", cls=""):
    """Rail block (rule-topped) or panel (bordered): kicker, title, text, actions."""
    k = label(kicker) if kicker else ""
    return f'<div class="block block--{variant}{(" " + cls) if cls else ""}">{k}<h{level} class="{title_cls}">{title}</h{level}>{body}{actions}</div>'


def rail_block(kicker, body):
    """A side-column block with a label and no title: facts, links, short notes."""
    return f'<div class="block block--rail">{label(kicker)}{body}</div>'


def disclosure(summary, body):
    return f'<details class="disclosure"><summary><span>{summary}</span></summary>{body}</details>'


def tabs(current):
    """Writing and In the media are two pages of one section: tabs at the top of both."""
    items = [("/writing/", S("writing.tab_writing")), ("/media/", S("writing.tab_media"))]
    links = "".join(f'<a href="{u(h)}"{" aria-current=\"page\"" if h == current else ""}>{l}</a>' for h, l in items)
    return f'<nav class="tabs" aria-label="{S("writing.kicker")}">{links}</nav>'


def page_hero(kicker, headline, lede="", actions="", image=None, alt="", mark="default", meta="", kicker_href=None, display=False, foot="", img_attrs="", tabs_html=""):
    """Page header on the master grid, led by the text. Text in columns 1-8 with a mark in 10-12, or text in
    1-7 with an image in 8-12 that stretches to the text's height. Always closes with the entablature."""
    lede_html = f'<p class="t-lede">{lede}</p>' if lede else ""
    h1 = f'<h1 class="{"t-display" if display else "t-page"}">{headline}</h1>'
    top = tabs_html or label(esc(kicker), rule=True, href=kicker_href)
    text = f'<div class="text">{top}{h1}{lede_html}{meta}{actions}{foot}</div>'
    cls = "page-hero" + (" with-image" if image else "") + (" display" if display else "")
    if image:
        media_html = portrait(image, alt, attrs=img_attrs) if is_cutout(image) else f'<img src="{u(image)}" alt="{esc(alt)}" width="1600" height="1200" {img_attrs}>'
        side = f'<div class="media">{media_html}</div>'
    else:
        side = f'<div class="side">{header_mark(mark)}</div>'
    return f'<section class="{cls}"><div class="wrap"><div class="inner">{text}{side}</div>{ENTABLATURE}</div></section>'


def cat_link(p):
    return f'<a class="cat over" href="{u("/writing/category/" + p["category"] + "/")}">{esc(p["category_label"])}</a>'


def chips_html(key, options):
    """Filter chips for the list with id=key. options: [(value, label html)]; the first is pressed."""
    return (f'<div class="chips" role="group" data-filter-for="list-{key}">' +
            "".join(f'<button class="chip" type="button" data-filter="{esc(v)}" aria-pressed="{"true" if i == 0 else "false"}">{lab}</button>'
                    for i, (v, lab) in enumerate(options)) + "</div>")


def expander(inner, key, total, limit=LIST_LIMIT, batch=LIST_BATCH, chips=""):
    """The one list wrapper: optional chips, the list, a Show-more button and a status line. State lives in site.js."""
    btn = ""
    if total > limit:
        btn = (f'<div class="actions"><button class="btn secondary sm" type="button" data-expand aria-controls="list-{key}-items" '
               f'data-template="{esc(R("site.show_more", n="{n}"))}">{S("site.show_more", n=total - limit)}</button></div>')
    status = f'<p class="status visually-hidden" role="status" aria-live="polite" data-template="{esc(R("site.showing", shown="{shown}", total="{total}"))}"></p>'
    return (f'<div class="expander" id="list-{key}" data-expander data-limit="{limit}" data-batch="{batch}">{chips}'
            f'<div id="list-{key}-items">{inner}</div>{btn}{status}</div>')


def grouped(items, row, list_cls, limit, years):
    """Rows in one list, or in year groups when the items span more than one year."""
    if years is None:
        years = len({it["d"].year for it in items}) > 1
    if not years:
        return f'<ul class="{list_cls}">' + "".join(row(it, i >= limit) for i, it in enumerate(items)) + "</ul>"
    groups = {}
    for i, it in enumerate(items):
        groups.setdefault(it["d"].year, []).append((i, it))
    out = ""
    for y, rows in groups.items():
        hidden = " hidden" if all(i >= limit for i, _ in rows) else ""
        out += (f'<div class="year-group"{hidden}><p class="t-label is-muted year-head">{y}</p><ul class="{list_cls}">' +
                "".join(row(it, i >= limit) for i, it in rows) + "</ul></div>")
    return out


def media_row(m, filterable=False, extra=False):
    fmt = m.get("format", "")
    data = f' data-item data-values="{esc(m["kind"])} {esc(fmt)}"' if filterable else ""
    meta = meta_line(esc(m["outlet"]), nowrap(fmt_date(m["d"])), nowrap(esc(fmt.capitalize())) if fmt else "", cls="r-meta")
    return (f'<li{data}{" hidden" if extra else ""}><a class="row" href="{esc(m["url"])}" target="_blank" rel="noopener">'
            f'{meta}<span class="r-title">{esc(m["title"])}&nbsp;<span aria-hidden="true">&#8599;</span></span></a></li>')


def media_list(items, key, limit=LIST_LIMIT, wide=True, chips="", years=None, preview=False):
    cls = "list wide" if wide else "list compact"
    if preview:
        return grouped(items, lambda m, x: media_row(m), cls, 10**6, False)
    inner = grouped(items, lambda m, x: media_row(m, True, x), cls, limit, years)
    return expander(inner, key, len(items), limit, chips=chips)


def media_items(media):
    """What /media/ lists: interviews, and coverage outside the campaign. Previews use the same selection."""
    return [m for m in media if m["kind"] == "interview" or (m["kind"] == "coverage" and not m.get("campaign"))]


def authored_items(posts, media):
    """One collection of Eric's written work, classified by authorship, sorted by publication date.
    Local posts that are companions to an external canonical piece are linked from that piece, not listed twice."""
    def pic(slug, fallback=""):
        cand = ASSETS / "img" / "writing" / f"{slug}.jpg"
        if cand.exists():
            return f"/assets/img/writing/{slug}.jpg"
        return fallback or "/assets/img/article-placeholder.jpg"
    items = []
    for p in posts:
        if p.get("canonical_external"):
            continue
        items.append({"title": p["title"], "d": p["date"], "url": u(p["url"]), "external": False, "source": "This site",
                      "summary": p["summary"], "cat": cat_link(p), "category": p["category"], "action": R("site.read_essay"), "featured": p.get("featured", False), "companion": None,
                      "image": pic(p["slug"], p.get("image", ""))})
    for m in media:
        if m.get("kind") != "column":
            continue
        comp = None
        if m.get("companion"):
            comp = (m.get("companion_label", "Companion note on this site"), u(m["companion"]))
        items.append({"title": m["title"], "d": m["d"], "url": m["url"], "external": True, "source": m["outlet"],
                      "summary": m.get("summary", ""), "cat": "", "category": "", "action": R("site.read_at", source=m["outlet"]), "featured": False, "companion": comp,
                      "verify": m.get("verify", ""), "image": pic(m.get("id", ""))})
    items.sort(key=lambda x: x["d"], reverse=True)
    return items


def article_entry(a, compact=False, extra=False, filterable=False, show_cat=True, row=False, level=3):
    """One entry for local and external authored work. One link (the title, stretched over the card);
    the source appears once, in the action line."""
    ext = ' target="_blank" rel="noopener"' if a["external"] else ""
    meta = meta_line(a["cat"] if (a.get("cat") and show_cat) else "", nowrap(fmt_date(a["d"])))
    summ = "" if compact else (f'<p>{esc(a["summary"])}</p>' if a.get("summary") else "")
    comp = f'<a class="more over" href="{a["companion"][1]}">{esc(a["companion"][0])} &rarr;</a>' if a.get("companion") else ""
    action = f'<span class="more">{esc(a["action"])}{" &#8599;" if a["external"] else " &rarr;"}</span>'
    title = f'<h{level} class="t-item"><a class="stretch" href="{esc(a["url"])}"{ext}>{esc(a["title"])}</a></h{level}>'
    data = f' data-item data-values="{"external" if a["external"] else "local"}"' if filterable else ""
    cls = "entry card" + (" compact" if compact else "") + (" row" if row else "")
    inner = f'{title}{summ}<p class="entry-actions">{action}{comp}</p>'
    body = f'{meta}<div class="flow">{inner}</div>'
    return f'<li{data}{" hidden" if extra else ""}><article class="{cls}">{body}</article></li>'


def writing_list(items, key, limit=LIST_LIMIT, compact=True, years=None, chips="", row=False):
    inner = grouped(items, lambda a, x: article_entry(a, compact=compact, extra=x, filterable=True, row=row), "rule-list", limit, years)
    return expander(inner, key, len(items), limit, chips=chips)


def feature_article(a, level=3):
    """The featured piece: image (cols 1-7) and text (cols 8-12), tops level. One link, the title, over the card."""
    ext = ' target="_blank" rel="noopener"' if a["external"] else ""
    meta = meta_line(a["cat"] if a.get("cat") else "", nowrap(fmt_date(a["d"])))
    summ = f'<p class="summary">{esc(a["summary"])}</p>' if a.get("summary") else ""
    comp = f'<a class="more over" href="{a["companion"][1]}">{esc(a["companion"][0])} &rarr;</a>' if a.get("companion") else ""
    return (f'<article class="pair card"><figure class="p-media" aria-hidden="true"><img src="{u(a["image"])}" alt="" width="1600" height="1000"></figure>'
            f'<div class="p-body">{meta}<h{level} class="t-feature"><a class="stretch" href="{esc(a["url"])}"{ext}>{esc(a["title"])}</a></h{level}>{summ}'
            f'<div class="actions"><span class="btn secondary sm">{esc(a["action"])}{" &#8599;" if a["external"] else ""}</span>{comp}</div></div></article>')


def next_items(items, label_for=None):
    """Authored items as n-up cards: meta line, title (one link), action line."""
    out = []
    for a in items:
        ext = ' target="_blank" rel="noopener"' if a["external"] else ""
        lab = label_for(a) if label_for else ""
        out.append({"card": True, "mark": meta_line(lab, nowrap(fmt_date(a["d"]))),
                    "title": f'<a class="stretch" href="{esc(a["url"])}"{ext}>{esc(a["title"])}</a>',
                    "action": f'<span class="more">{esc(a["action"])}{" &#8599;" if a["external"] else " &rarr;"}</span>'})
    return out


def feature_group(featured, others):
    if not featured:
        return ""
    return f'{feature_article(featured)}<div class="feature-next">{nup(next_items(others), title_cls="t-item")}</div>'


def event_item(e, variant="full"):
    d = e["d"]
    when = fmt_date(d) + (f" to {fmt_date(e['end_d'])}" if e.get("end_d") else "")
    link = ""
    if e.get("url"):
        link = link_to(S("site.event_details") if e["past"] else S("site.event_register"), e["url"])
    tag = f' <span class="tag">{S("site.sample_tag")}</span>' if e.get("placeholder") else ""
    time = nowrap(esc(e["time"])) if e.get("time") else ""
    place = esc(", ".join(x for x in [e.get("venue"), e.get("city")] if x))
    if variant == "compact":
        return (f'<li class="event">{meta_line(nowrap(when), time, esc(e.get("city", "")))}'
                f'<h3 class="t-item">{esc(e["title"])}{tag}</h3><div class="ev-action">{link}</div></li>')
    datebox = f'<div class="datebox" aria-hidden="true"><span class="m">{d:%b}</span><span class="d">{d.day}</span><span class="y">{d.year}</span></div>'
    meta = meta_line(esc(e.get("kind", "Event")), f'<span class="nowrap date-sm">{when}</span>', time, place)
    summ = f'<p>{esc(e["summary"])}</p>' if e.get("summary") else ""
    return (f'<li class="event{" past" if e["past"] else ""}">{datebox}<div class="flow">{meta}<h3 class="t-item">{esc(e["title"])}{tag}</h3>'
            f'{summ}{("<p>" + link + "</p>") if link else ""}</div></li>')


def events_list(events, variant="full"):
    return f'<ol class="events-list{" compact" if variant == "compact" else ""}">{"".join(event_item(e, variant) for e in events)}</ol>'


def signup_form(variant="full"):
    """One form component. Fields, then the footer (button and status), then the note, in every variant.
    'inline' puts the button in the field row once the form is wide enough."""
    f = SITE["form"]
    fl = f["fields"]
    hidden = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in f.get("hidden", {}).items())
    action = esc(f["endpoint"]) if f["endpoint"] else "#"
    # Brevo's form URL answers with JSON only when asked; without scripts the plain URL shows Brevo's own page.
    post_url = f["endpoint"] + "?isAjax=1" if "sibforms.com" in f["endpoint"] else f["endpoint"]
    statement = SITE["signup"]["statement"] + f' <a href="{u("/privacy/")}">{S("site.privacy_link")}</a>.'
    if SITE.get("mailing_address"):
        statement += f' {esc(NAME)}, {esc(SITE["mailing_address"])}.'
    note = (f'<label class="consent"><input type="checkbox" name="consent" value="yes" required> {statement}</label>'
            if f.get("consent") == "checkbox" else f'<p class="form-note">{statement}</p>')
    hp = '<div class="hp" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></div>'
    data = (f'data-form="signup" data-endpoint="{esc(post_url)}" data-fallback-msg="{esc(R("site.form_signup_fallback"))}" '
            f'data-sent-msg="{esc(R("site.form_signup_confirm" if f.get("double_opt_in") else "site.form_signup_sent"))}" data-error-msg="{esc(R("site.form_error"))}" data-invalid-msg="{esc(R("site.form_invalid"))}" '
            f'data-city-field="{esc(fl["city"])}" data-postal-field="{esc(fl["postal"])}" data-riding-field="{esc(fl["riding"])}" data-riding-set="{esc(f["riding_set"])}"')
    fields = (f'<label>{S("site.form_first_name")}<input type="text" name="{esc(fl["first_name"])}" required autocomplete="given-name"></label>'
              f'<label>{S("site.form_last_name")}<input type="text" name="{esc(fl["last_name"])}" required autocomplete="family-name"></label>'
              f'<label class="wide">{S("site.form_email")}<input type="email" name="{esc(fl["email"])}" required autocomplete="email"></label>'
              f'<label class="wide">{S("site.form_location")}<input type="text" name="{esc(fl["city"])}" autocomplete="postal-code" title="{esc(R("site.form_location_help"))}"></label>')
    submit = f'<button class="btn primary" type="submit">{S("site.form_submit")}</button>'
    inline = variant == "inline"
    cls = "form form--signup " + ("form--inline" if inline else "form--full")
    return (f'<form class="{cls}" action="{action}" method="{esc(f.get("method", "POST"))}" {data} novalidate>'
            f'<div class="form-fields">{fields}{submit if inline else ""}</div>'
            f'<div class="form-footer">{"" if inline else submit}{status_p()}</div>{note}{hp}{hidden}</form>')


def signup_section(section_id="signup", dark=False):
    s = SITE["signup"]
    return (f'<section class="section signup-band{" band dark" if dark else ""}" id="{section_id}"><div class="wrap signup-grid">'
            f'<div class="sg-text"><h2 class="t-sub">{esc(s["title"])}</h2><p>{esc(s["text"])}</p></div>{signup_form("inline")}</div></section>')


def contact_form():
    c = SITE["contact"]
    hidden = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in c.get("hidden", {}).items())
    action = esc(c["endpoint"]) if c.get("endpoint") else "#"
    topics = "".join(f'<option value="{esc(t["id"])}">{esc(t["label"])}</option>' for t in c["topics"])
    note = S("site.form_privacy_note", link=f'<a href="{u("/privacy/")}">{S("site.privacy_link")}</a>')
    return (f'<form class="form form--contact" action="{action}" method="{esc(c.get("method", "POST"))}" data-form="contact" data-endpoint="{esc(c.get("endpoint", ""))}" '
            f'data-sent="{esc(R("site.form_sent"))}" data-fallback="{esc(R("site.form_fallback"))}" data-error-msg="{esc(R("site.form_error"))}" data-invalid-msg="{esc(R("site.form_invalid"))}" novalidate>'
            f'<div class="form-fields"><label>{S("site.form_name")}<input type="text" name="name" required autocomplete="name"></label>'
            f'<label>{S("site.form_reply")}<input type="email" name="email" required autocomplete="email"></label>'
            f'<label class="wide">{S("site.form_topic")}<select name="topic">{topics}</select></label>'
            f'<label class="wide">{S("site.form_message")}<textarea name="message" required rows="7"></textarea></label></div>'
            f'<div class="hp" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></div>{hidden}'
            f'<div class="form-footer"><button class="btn primary" type="submit">{S("site.form_send")}</button>{status_p()}</div>'
            f'<p class="form-note">{note}</p></form>')


def x_feed_html():
    x = SITE.get("x_feed", {})
    if not x.get("enabled"):
        return ""
    h = esc(x.get("handle", SITE["x_handle"]))
    return f"""<section class="section"><div class="wrap">
  {section_head(S("site.x_feed_heading", handle=h), tier="minor", aside=link_to(S("site.x_feed_link"), f"https://x.com/{h}"))}
  <div class="embed-box"><a class="twitter-timeline more" data-height="{int(x.get('height', 700))}" data-dnt="true" data-chrome="noheader nofooter noborders" href="https://twitter.com/{h}?ref_src=twsrc%5Etfw">{S("site.x_feed_line", handle=h)} &#8599;</a></div>
  <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
</div></section>"""


def contact_href(topic=""):
    return u("/contact/") + (f"?topic={topic}" if topic else "")


def cta_actions(topic="other"):
    out = f'<a class="btn primary" href="{contact_href(topic)}">{S("site.email_me")}</a>'
    if SITE.get("booking_url"):
        out += f'<a class="btn secondary" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">{S("site.book_call")}</a>'
    return f'<div class="actions">{out}</div>'


def cta_band(headline, text, topic=""):
    """The closing dark band: headline, line of text, actions, with the arc decal."""
    return (f'<section class="band dark cta-band">{DECAL_ARC}<div class="wrap cta-grid"><div class="cta-text">'
            f'<h2 class="t-section">{esc(headline)}</h2><p class="t-lede">{esc(text)}</p>{cta_actions(topic)}</div></div></section>')


def record_rows(items, level=3):
    """Public-work record rows: photo slot (cols 1-4) and text (cols 5-12). A missing photo leaves an empty niche."""
    rows = ""
    for it in items:
        img = it.get("card_image") or it.get("image")
        if img:
            pic = f'<figure class="pic" aria-hidden="true"><img src="{u(img)}" alt="" loading="lazy" width="800" height="600"></figure>'
        else:
            warn(f"content/policy/{it['slug']}.md: no photo")
            pic = '<figure class="pic is-empty" aria-hidden="true"></figure>'
        meta = meta_line(nowrap(esc(it["dates"]))) if it.get("dates") else ""
        rows += (f'<li class="record-row card">{pic}<div class="flow"><p class="t-label">{esc(it.get("role", ""))}</p>'
                 f'<h{level} class="t-sub"><a class="stretch" href="{u(it["url"])}">{esc(it["title"])}</a></h{level}>'
                 f'<p>{esc(it.get("summary", ""))}</p>{meta}<span class="more">{S("policy.read_more")} &rarr;</span></div></li>')
    return f'<ol class="record">{rows}</ol>'


def band_areas(label_text, areas, compact=False):
    """Dark band: a label, then the areas as an n-up row (symbol or short rule, title, text, action)."""
    items = []
    for a in areas:
        sym = SYMBOLS.get(a["symbol"]) if a.get("symbol") else '<span class="symbol rule-only" aria-hidden="true"></span>'
        title = f'<a class="stretch" href="{u(a["href"])}">{esc(a["title"])}</a>' if a.get("href") else esc(a["title"])
        items.append({"mark": sym, "title": title, "body": f'<p>{esc(a["text"])}</p>', "card": bool(a.get("href")),
                      "action": f'<span class="more">{esc(a["cta"])} &rarr;</span>' if a.get("cta") else ""})
    return (f'<section class="band dark band-areas{" compact" if compact else ""}"><div class="wrap">'
            f'{section_head(esc(label_text), tier="t-label")}{nup(items)}</div></section>')


def timelines(h):
    """A list whose every item opens with a bold date ("**June 9.** ...") renders as a dated timeline."""
    def conv(m):
        lis = re.findall(r"<li>(.*?)</li>", m.group(1), re.S)
        rows = []
        for li in lis:
            mm = re.match(r"\s*<strong>(.*?)</strong>\s*(.*)$", li, re.S)
            if not mm or not re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December|\d{4})", mm.group(1)):
                return m.group(0)
            rows.append(f'<li><time>{mm.group(1).rstrip(".")}</time><div class="tl-text">{mm.group(2).strip()}</div></li>')
        return f'<ol class="timeline">{"".join(rows)}</ol>' if rows else m.group(0)
    return re.sub(r"<ul>((?:<li>\s*<strong>.*?</li>)+)</ul>", conv, h, flags=re.S)


def page_close(heading, items, all_text, all_href):
    """End of an article or record page: the next things to read, then a link to the whole section."""
    if not items:
        return ""
    return f'<div class="page-close">{section_head(heading, tier="minor", aside=link_to(all_text, all_href))}{nup(items, title_cls="t-item")}</div>'


# --------------------------------------------------------------------------- pages
def build_home(posts, media, events, policy_items):
    hero = SITE["hero"]
    headline = esc(hero["headline"])
    if hero["headline"].startswith("A future "):   # "A future / worth building." on wide screens
        headline = f'A future <span class="brk">{esc(hero["headline"][len("A future "):])}</span>'
    record = meta_line(*[nowrap(esc(r)) for r in hero.get("record", [])], cls="record-line")
    actions = (f'<div class="actions"><a class="btn primary" href="{u("/consulting/")}">{S("home.cta_primary")}</a>'
               f'<a class="btn secondary" href="{u("/writing/")}">{S("home.cta_secondary")}</a></div>')
    opening = page_hero(hero["kicker"], headline, esc(hero["lede"]), actions, image=img_path("eric-hero"), alt=NAME,
                        display=True, foot=record, img_attrs='fetchpriority="high"')
    authored = authored_items(posts, media)
    featured = next((a for a in authored if a.get("featured")), authored[0] if authored else None)
    others = [a for a in authored if a is not featured][:3]
    upcoming = [e for e in events if not e["past"]][:HOME_PREVIEW]
    events_html = ""
    if upcoming:
        events_html = f"""<section class="section"><div class="wrap">
  {section_head(S("home.events_heading"), tier="minor", aside=link_to(S("home.events_link"), "/events/"))}{events_list(upcoming, "compact")}
</div></section>"""
    body = f"""{opening}
{signup_section()}
{band_areas(R("home.work_label"), SITE["pillars"], compact=True)}
<section class="section"><div class="wrap">
  {section_head(S("home.writing_heading"), aside=link_to(S("home.writing_link"), "/writing/"))}{feature_group(featured, others)}
</div></section>
<section class="section"><div class="wrap">
  {section_head(S("home.media_heading"), tier="minor", aside=link_to(S("home.media_link"), "/media/"))}{media_list(media_items(media)[:HOME_PREVIEW], "home-media", preview=True)}
</div></section>
<section class="section"><div class="wrap">
  {section_head(S("home.policy_heading"), aside=link_to(S("home.policy_link"), "/policy/"))}{record_rows(policy_items[:HOME_PREVIEW])}
</div></section>
{events_html}
<section class="section"><div class="wrap"><div class="pair text-first">
  <div class="p-body"><h2 class="t-sub">{S("home.support_heading")}</h2><p>{S("home.support_text")}</p><div class="actions"><a class="btn secondary" href="{u('/support/')}">{S("home.support_cta")}</a></div></div>
  <figure class="p-media" aria-hidden="true"><img src="{u('/assets/img/support.jpg')}" alt="" loading="lazy" width="1600" height="1000"></figure>
</div></div></section>
{cta_band(SITE['contact']['headline'], SITE['contact']['text'])}"""
    render(R("home.meta_title"), SITE["description"], body, path="/", current="/", lastmod=TODAY)


def build_consulting():
    c = load_json("consulting.json")
    services = band_areas(R("consulting.services_label"), [{"symbol": sv.get("symbol"), "title": sv["title"], "text": sv["summary"]} for sv in c["services"]])
    steps = [{"mark": f'<p class="num">{i}</p>', "title": esc(st["title"]), "body": f'<p>{esc(st["text"])}</p>'} for i, st in enumerate(c["how"]["steps"], start=1)]
    partner = c["partner"]
    ptext = "".join(f"<p>{inline(p)}</p>" for p in partner["text"])
    pserv = "".join(f'<span class="tag">{esc(s)}</span>' for s in partner["services"])
    sectors = "".join(f'<span class="tag">{esc(s)}</span>' for s in c["sectors"])
    body = f"""{page_hero(c['kicker'], esc(c['headline']), esc(c['lede']), cta_actions('consulting'), image=img_path('eric-consulting'), alt=NAME)}
{services}
<section class="section"><div class="wrap">{section_head(S("consulting.sectors_label"), tier="t-label")}<div class="tags">{sectors}</div></div></section>
<section class="section"><div class="wrap">
  {section_head(esc(c['how']['headline']), kicker=S("consulting.how_label"), intro=esc(c['how']['text']))}{nup(steps)}
</div></section>
<section class="section" id="electric-mind"><div class="wrap two-col">
  <div class="flow">{label(S("consulting.partners_label"))}<h2 class="t-sub">{esc(partner['headline'])}</h2>{ptext}<p>{link_to(S("consulting.partners_visit", name=esc(partner['name'])), partner['url'])}</p></div>
  <div class="flow">{label(S("consulting.partners_brings_label"))}<div class="tags">{pserv}</div></div>
</div></section>
{cta_band(c['cta']['headline'], c['cta']['text'], 'consulting')}"""
    desc = R("consulting.meta_description")
    ld = [{"@type": "ProfessionalService", "@id": DOMAIN + "/consulting/#service", "name": f"{NAME} Consulting", "url": absu("/consulting/"),
           "provider": {"@id": PERSON_ID}, "areaServed": ["Canada", "United States"], "description": desc,
           "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Services", "itemListElement": [
               {"@type": "Offer", "itemOffered": {"@type": "Service", "name": s["title"], "description": s["summary"]}} for s in c["services"]]}}]
    render(T(R("consulting.meta_title")), desc, body, path="/consulting/", current="/consulting/", image=None if is_cutout(img_path("eric-consulting")) else img_path("eric-consulting"), jsonld=ld)


def build_writing(posts, media):
    authored = authored_items(posts, media)
    by_url = {a["url"]: a for a in authored}
    featured = next((a for a in authored if a.get("featured")), authored[0] if authored else None)
    rest = [a for a in authored if a is not featured]
    top3, archive = rest[:3], rest[3:]
    chips = chips_html("writing-archive", [("all", S("writing.filter_all")), ("local", S("writing.filter_local")), ("external", S("writing.filter_external"))])
    lede = S("writing.lede")
    actions = f'<div class="actions"><a class="btn secondary sm" href="{u("/feed.xml")}">{S("writing.rss_button")}</a><a class="btn secondary sm" href="#signup">{S("writing.email_button")}</a></div>'
    body = f"""{page_hero(R('writing.kicker'), S('writing.headline'), lede, actions, mark='writing', tabs_html=tabs("/writing/"))}
<section class="section"><div class="wrap">{section_head(S("writing.feature_heading"), hidden=True)}{feature_group(featured, top3)}</div></section>
<section class="section"><div class="wrap">
  {section_head(S("writing.more_heading"), tier="minor", aside=chips)}{writing_list(archive, "writing-archive", row=True)}
</div></section>
{signup_section('signup', dark=True)}"""
    render(T(R("writing.meta_title")), R("writing.meta_description"), body, path="/writing/", current="/writing/",
           jsonld=[{"@type": "Blog", "@id": DOMAIN + "/writing/#blog", "name": f"{NAME}: writing", "url": absu("/writing/"), "author": {"@id": PERSON_ID},
                    "blogPost": [{"@type": "BlogPosting", "headline": a["title"], "url": a["url"] if a["external"] else absu(a["url"].replace(BASE, "", 1)), "datePublished": a["d"].isoformat(),
                                  **({"publisher": {"@type": "Organization", "name": a["source"]}} if a["external"] else {})} for a in authored[:30]]}],
           lastmod=authored[0]["d"] if authored else TODAY)
    # category pages: the authored posts in each category (companion notes belong to their original piece)
    listed = [p for p in posts if not p.get("canonical_external")]
    for cat in [c for c in SITE["categories"] if any(p["category"] == c for p in listed)]:
        sub = [p for p in listed if p["category"] == cat]
        lab = SITE["categories"][cat]
        count = f"{len(sub)} {R('writing.post_singular' if len(sub) == 1 else 'writing.post_plural')}"
        rows = "".join(article_entry(by_url[u(p["url"])], show_cat=False, row=True) for p in sub)
        body = f"""{page_hero(R('writing.kicker'), esc(lab), S('writing.category_lede', n=count, link=f'<a href="{u("/writing/")}">{S("writing.category_link")}</a>'), mark='writing', kicker_href='/writing/')}
<section class="section"><div class="wrap"><ul class="rule-list">{rows}</ul></div></section>"""
        render(T(f"{lab}: writing"), f"Posts by {NAME} on {lab.lower()}.", body, path=f"/writing/category/{cat}/", current="/writing/", lastmod=sub[0]["date"])
    # articles
    companions = {m.get("companion"): m for m in media if m.get("companion")}
    for p in posts:
        here = u(p["url"])
        idx = next((i for i, a in enumerate(authored) if a["url"] == here), None)
        provenance, kicker, khref = "", p["category_label"], f"/writing/category/{p['category']}/"
        if p["origin"] == "campaign":
            provenance = S("article.provenance_campaign", link=f'<a href="{u("/policy/ontario-liberal-leadership-2026/")}">{S("article.campaign_link")}</a>')
        if p.get("canonical_external"):
            src = companions.get(p["url"], {}).get("outlet", "")
            provenance = S("article.provenance_companion", link=f'<a href="{esc(p["canonical_external"])}" target="_blank" rel="noopener">{S("article.companion_meta_link", source=esc(src))} &#8599;</a>')
            kicker, khref = R("writing.kicker"), "/writing/"
        meta = meta_line(f'{S("article.by")} <a href="{u("/about/")}">{esc(NAME)}</a>', nowrap(fmt_date(p["date"])), nowrap(S("article.min_read", n=reading_time(p["html"]))), provenance)
        hero_img = ""
        if p.get("hero") and p["hero"] not in p["html"]:
            hero_img = f'<figure class="article-hero"><img src="{u(p["hero"])}" alt=""></figure>'
        share_url = absu(p["url"])
        share = (f'<ul class="link-list">'
                 f'<li><a href="https://x.com/intent/post?text={esc(p["title"])}&url={share_url}" target="_blank" rel="noopener">X</a></li>'
                 f'<li><a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener">LinkedIn</a></li>'
                 f'<li><a href="https://bsky.app/intent/compose?text={esc(p["title"])}%20{share_url}" target="_blank" rel="noopener">Bluesky</a></li>'
                 f'<li><a href="mailto:?subject={esc(p["title"])}&body={share_url}">{S("article.share_email")}</a></li></ul>')
        if p.get("canonical_external"):
            topic = rail_block(S("article.rail_original"), f'<p>{link_to(S("article.companion_meta_link", source=esc(src)), p["canonical_external"])}</p>')
        else:
            topic = rail_block(S("article.rail_topic"), f'<p>{link_to(S("article.rail_topic_link", topic=esc(p["category_label"])), khref)}</p>')
        rail = (topic + rail_block(S("article.share"), share) +
                rail_block(S("article.rail_signup_heading"), f'<p>{link_to(S("article.rail_signup_link"), "#signup")}</p>'))
        # keep reading: the older and newer pieces in the one collection, then related work to make three
        picks, labels = [], {}
        if idx is not None:
            if idx + 1 < len(authored):
                picks.append(authored[idx + 1]); labels[id(authored[idx + 1])] = S("article.older")
            if idx > 0:
                picks.append(authored[idx - 1]); labels[id(authored[idx - 1])] = S("article.newer")
        related = [a for a in authored if a["url"] != here and a not in picks and a.get("category") == p["category"]]
        related += [a for a in authored if a["url"] != here and a not in picks and a not in related]
        for a in related[:3 - len(picks)]:
            picks.append(a); labels[id(a)] = S("article.related")
        close = page_close(S("article.keep_reading"), next_items(picks, lambda a: labels.get(id(a), "")), S("article.more_link"), "/writing/")
        body = f"""{page_hero(kicker, esc(p['title']), esc(p['summary']), meta=meta, mark='writing', kicker_href=khref)}
<section class="section"><div class="wrap main-rail reading">
  <div>{hero_img}<article class="prose">{p['html']}</article>
  <div class="endmark-wrap">{ENDMARK}<span class="visually-hidden">{S("article.end_mark_label")}</span></div></div>
  <aside class="rail">{rail}</aside>
</div></section>
<section class="section"><div class="wrap">{close}</div></section>
{signup_section('signup', dark=True)}"""
        ld = [{"@type": "BlogPosting", "@id": absu(p["url"]) + "#article", "headline": p["title"], "description": p["summary"], "url": absu(p["url"]),
               "datePublished": p["date"].isoformat(), "dateModified": (p["updated"] or p["date"]).isoformat(),
               "author": {"@id": PERSON_ID}, "publisher": {"@id": PERSON_ID}, "mainEntityOfPage": absu(p["url"]),
               "image": absu(p["image"]) if p.get("image") else absu(SITE["og_image"]),
               "keywords": ", ".join(p["tags"]), "wordCount": p["words"], "inLanguage": "en-CA", "isPartOf": {"@id": DOMAIN + "/writing/#blog"},
               **({} if p.get("canonical_external") else {"articleSection": p["category_label"]})}]
        render(T(p["title"]), p["summary"] or strip_tags(p["html"])[:155], body, path=p["url"], current="/writing/", image=p.get("image") or None,
               kind="article", jsonld=ld, lastmod=p["updated"] or p["date"], reading=True)


def build_media(media):
    items = media_items(media)
    formats = sorted({m.get("format", "") for m in items if m.get("format")})
    chips = chips_html("media", [("all", S("media.filter_all"))] + [(f, esc(f.title())) for f in formats])
    lede = S("media.lede", writing=f'<a href="{u("/writing/")}">{S("media.lede_writing_link")}</a>', campaign=f'<a href="{u("/policy/ontario-liberal-leadership-2026/#coverage")}">{S("media.lede_campaign_link")}</a>')
    actions = f'<div class="actions"><a class="btn primary sm" href="{contact_href("media")}">{S("media.requests_button")}</a><a class="btn secondary sm" href="#media-kit">{S("media.kit_button")}</a></div>'
    kit = [{"title": S("media.kit_bio_heading"), "body": f"<p>{esc(SITE['description'])}</p>"},
           {"title": S("media.kit_headshot_heading"), "body": f'<p>{S("media.kit_headshot_text")}</p>',
            "action": f'<a class="btn secondary sm" href="{u("/assets/img/eric-headshot.jpg")}" download>{S("media.kit_headshot_button")} &#8595;</a>'},
           {"title": S("media.kit_requests_heading"), "body": f'<p>{S("media.kit_requests_text")}</p>',
            "action": f'<a class="btn primary sm" href="{contact_href("media")}">{S("media.kit_requests_button")}</a>'}]
    body = f"""{page_hero(R('media.kicker'), S('media.headline'), lede, actions, mark='media', tabs_html=tabs("/media/"))}
<section class="section"><div class="wrap">
  {section_head(S("media.interviews_heading"), kicker=S("media.interviews_label"))}{media_list(items, 'media', chips=chips)}
</div></section>
<section class="section band limestone" id="media-kit"><div class="wrap">
  {section_head(S("media.kit_heading"), kicker=S("media.kit_label"), tier="minor")}{nup(kit)}
</div></section>"""
    render(T(R("media.meta_title")), R("media.meta_description"), body, path="/media/", current="/writing/",
           lastmod=media[0]["d"] if media else TODAY)


def build_policy(policy, media):
    idx_meta, idx_html, items = policy
    # the first "## heading + bullet list" in policy/_index.md becomes the dark band of advocacy areas
    mh = re.search(r"<h2>(.*?)</h2>\s*<ul>(.*?)</ul>", idx_html, re.S)
    pri = [{"title": re.sub(r"\.$", "", strip_tags(m.group(1))), "text": strip_tags(m.group(2)).strip()} for m in re.finditer(r"<li><strong>(.*?)</strong>(.*?)</li>", mh.group(2), re.S)] if mh else []
    band = band_areas(strip_tags(mh.group(1)), pri) if pri else ""
    rest_html = (idx_html[:mh.start()] + idx_html[mh.end():]).strip() if mh else idx_html.strip()
    panel = block(S("policy.platform_heading"), f'<p>{S("policy.platform_text")}</p>', kicker=S("policy.platform_label"), variant="panel", title_cls="t-sub", cls="accent",
                  actions=f'<div class="actions"><a class="btn primary sm" href="{esc(SITE["platform_url"])}" target="_blank" rel="noopener">{S("policy.platform_button")} &#8599;</a><a class="btn secondary sm" href="{u("/policy/ontario-liberal-leadership-2026/")}">{S("policy.platform_campaign_button")}</a></div>')
    platform_block = (f'<section class="section"><div class="wrap two-col"><div class="prose">{rest_html}</div><aside>{panel}</aside></div></section>' if rest_html
                      else f'<section class="section"><div class="wrap grid"><div class="lg-8">{panel}</div></div></section>')
    body = f"""{page_hero(idx_meta.get('kicker', 'Public policy'), esc(idx_meta.get('headline', 'Public policy')), esc(idx_meta.get('lede', '')), mark='policy')}
{band}
<section class="section"><div class="wrap">{section_head(S("policy.record_heading"))}{record_rows(items)}</div></section>
{platform_block}
{x_feed_html()}"""
    render(T(R("policy.meta_title")), R("policy.meta_description"), body, path="/policy/", current="/policy/")
    campaign_items = [m for m in media if m.get("campaign")]
    for it in items:
        links = "".join(f'<a class="btn {"primary" if l["primary"] else "secondary"}" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} &#8599;</a>' for l in it["links"])
        meta = meta_line(esc(it.get("role", "")), nowrap(esc(it["dates"])) if it.get("dates") else "")
        gallery = f'<div class="gallery" data-grid="own">{"".join(f"<img src=\"{u(g)}\" alt=\"\" loading=\"lazy\">" for g in it["gallery"])}</div>' if it["gallery"] else ""
        coverage = ""
        if truthy(it.get("coverage", "")) and campaign_items:
            chips = chips_html("coverage", [("all", S("policy.archive_filter_all")), ("column", S("policy.archive_filter_columns")),
                                            ("interview", S("policy.archive_filter_interviews")), ("coverage", S("policy.archive_filter_coverage"))])
            intro = S("policy.archive_text", n=len(campaign_items), media=f'<a href="{u("/media/")}">{S("policy.archive_media_link")}</a>', writing=f'<a href="{u("/writing/")}">{S("policy.archive_writing_link")}</a>')
            coverage = f"""<section class="section" id="coverage"><div class="wrap">
  {section_head(S("policy.archive_heading"), kicker=S("policy.archive_label"), intro=intro, intro_cls="muted", tier="minor")}{media_list(campaign_items, 'coverage', chips=chips)}
</div></section>"""
        feature = campaign_capsule() if truthy(it.get("capsule", "")) else ""
        others = [o for o in items if o is not it]
        close_items = [{"card": True, "mark": f'<p class="t-label">{esc(o.get("role", ""))}</p>', "title": f'<a class="stretch" href="{u(o["url"])}">{esc(o["title"])}</a>',
                        "body": f'<p>{esc(o.get("summary", ""))}</p>', "action": f'<span class="more">{S("policy.read_more")} &rarr;</span>'} for o in others]
        glance = f'<dl class="glance"><div><dt>{S("policy.fact_role")}</dt><dd>{esc(it.get("role", ""))}</dd></div>' + (f'<div><dt>{S("policy.fact_when")}</dt><dd>{esc(it["dates"])}</dd></div>' if it.get("dates") else "") + "</dl>"
        ext = "".join(f'<li>{link_to(esc(l["label"]), l["url"])}</li>' for l in it["links"])
        more = "".join(f'<li><a href="{u(o["url"])}">{esc(o["title"])}</a><span class="t-meta">{esc(o.get("role", ""))}</span></li>' for o in others)
        rail = (rail_block(S("policy.glance_label"), glance) +
                rail_block(S("policy.more_records"), f'<ul class="link-list stacked">{more}</ul><p>{link_to(S("policy.all_link"), "/policy/")}</p>'))
        body = f"""{page_hero(R('policy.subpage_kicker'), esc(it['title']), esc(it.get('summary', '')), f'<div class="actions">{links}</div>' if links else '', image=it.get('image'), alt=it['title'], meta=meta, kicker_href='/policy/')}
<section class="section"><div class="wrap main-rail reading"><div><div class="prose">{timelines(it['html'])}</div>{gallery}</div><aside class="rail">{rail}</aside></div></section>
{feature}{coverage}"""
        ld = []
        if it["slug"] != "ontario-liberal-leadership-2026" and it["links"]:
            ld.append({"@type": "Organization", "name": it["title"], "url": it["links"][0]["url"], "founder": {"@id": PERSON_ID}})
        render(T(it["title"]), it.get("summary", ""), body, path=it["url"], current="/policy/", image=it.get("card_image") or it.get("image"), jsonld=ld, reading=True, campaign=truthy(it.get("capsule", "")))


def campaign_capsule():
    """The 2026 campaign as a page within a page, in the campaign's own design language."""
    cp = load_json("campaign.json")
    cards = "".join(f'<a class="c-card" href="{esc(ch["url"])}" target="_blank" rel="noopener">{f"<img src=\"{u(ch["image"])}\" alt=\"\" loading=\"lazy\" width=\"900\" height=\"506\">" if ch.get("image") else "<span class=\"c-noimg\"></span>"}'
                    f'<span class="c-kicker">Chapter {i + 1}</span><span class="c-title">{esc(ch["title"])}</span><span class="c-tag">{esc(ch["tagline"])}</span><span class="c-more">Read the chapter &#8599;</span></a>'
                    for i, ch in enumerate(cp["chapters"]))
    return f"""<section class="section" id="platform"><div class="wrap">
  {section_head(S("policy.capsule_heading"), kicker=S("policy.capsule_label"), intro=esc(cp['note']), intro_cls="muted", tier="minor")}
  <div class="capsule" data-grid="own">
    <div class="c-head"><img class="c-logo" src="{u('/assets/img/campaign/logo.svg')}" alt="{esc(cp['wordmark_alt'])}" width="708" height="223"><p class="c-slogan">{esc(cp['slogan'])}</p></div>
    <h3>{esc(cp['platform_title'])}</h3>
    <p class="c-sub">{esc(cp['platform_sub'])}</p>
    <div class="c-actions"><a class="c-btn" href="{esc(cp['platform_url'])}" target="_blank" rel="noopener">Explore the full platform &#8599;</a><a class="c-btn ghost" href="{esc(cp['pdf_url'])}" target="_blank" rel="noopener">Platform PDF &#8599;</a></div>
    <div class="c-grid">{cards}</div>
  </div>
</div></section>"""


def build_events(events):
    upcoming = [e for e in events if not e["past"]]
    past = list(reversed([e for e in events if e["past"]]))
    up_html = events_list(upcoming) if upcoming else f'<p class="empty">{S("events.empty")}</p>'
    past_html = f'<div class="disclosures">{disclosure(S("events.past_summary", n=len(past)), events_list(past))}</div>' if past else ""
    ics = absu("/events.ics")
    webcal = ics.replace("https://", "webcal://").replace("http://", "webcal://")
    calendar = (f'<div class="actions"><a class="btn primary sm" href="{webcal}">{S("events.calendar_add")}</a>'
                f'<button class="btn secondary sm" type="button" data-copy="{ics}" data-copied="{esc(R("site.status_copied"))}" data-manual="{esc(R("site.status_copy_manual"))}">{S("events.calendar_copy")}</button></div>'
                f'<input class="copy-field" type="text" value="{ics}" readonly hidden aria-label="{S("events.calendar_heading")}">{status_p()}'
                f'<p class="fine">{S("events.calendar_download", link=f"<a href=\"{u("/events.ics")}\">{S("events.calendar_download_link")}</a>")}</p>')
    updates = ""
    if len(upcoming) <= 2:   # few dates: invite people to hear about the next ones, right where they look
        updates = (f'<div class="subsection">{section_head(S("events.updates_heading"), kicker=S("events.updates_label"), intro=S("events.updates_text"), intro_cls="t-body", tier="minor", rule=False)}'
                   f'{signup_form("full")}</div>')
    rail = (block(S("events.calendar_heading"), f'<p>{S("events.calendar_text")}</p>', kicker=S("events.calendar_label"), actions=calendar) +
            block(S("events.invite_heading"), f'<p>{S("events.invite_text")}</p>', kicker=S("events.invite_label"),
                  actions=f'<div class="actions"><a class="btn secondary sm" href="{contact_href("speaking")}">{S("events.invite_button")}</a></div>'))
    body = f"""{page_hero(R('events.kicker'), S('events.headline'), S('events.lede'), mark='events')}
<section class="section"><div class="wrap main-rail">
  <div>{section_head(S("events.upcoming_heading"), kicker=S("events.upcoming_label"), tier="minor", rule=False)}{up_html}{past_html}{updates}</div>
  <aside class="rail">{rail}</aside>
</div></section>"""
    ld = []
    for e in upcoming:
        t = parse_time(e.get("time", ""))
        start = f"{e['d'].isoformat()}T{t.strftime('%H:%M')}:00-05:00" if t else e["d"].isoformat()
        ev = {"@type": "Event", "name": e["title"], "startDate": start, "eventStatus": "https://schema.org/EventScheduled",
              "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "performer": {"@id": PERSON_ID}, "organizer": {"@id": PERSON_ID},
              "description": e.get("summary", ""), "url": e["url"] if e.get("url", "").startswith("http") else absu("/events/")}
        if e.get("city") or e.get("venue"):
            ev["location"] = {"@type": "Place", "name": e.get("venue") or e.get("city"), "address": {"@type": "PostalAddress", "addressLocality": e.get("city", ""), "addressRegion": "ON", "addressCountry": "CA"}}
        ld.append(ev)
    render(T(R("events.meta_title")), R("events.meta_description"), body, path="/events/", current="/events/", jsonld=ld)
    def ics_esc(s): return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    host = DOMAIN.split("//")[1].split("/")[0]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{NAME}//{host}//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{ics_esc(NAME)}: events", "X-WR-TIMEZONE:America/Toronto"]
    for e in events:
        t = parse_time(e.get("time", ""))
        te = parse_time(e.get("end_time", ""))
        lines += ["BEGIN:VEVENT", f"UID:{e['slug']}@{host}", f"DTSTAMP:{NOW:%Y%m%dT%H%M%SZ}"]
        if t:
            start = dt.datetime.combine(e["d"], t)
            end = dt.datetime.combine(e["end_d"] or e["d"], te) if te else start + dt.timedelta(hours=1, minutes=30)
            lines += [f"DTSTART;TZID=America/Toronto:{start:%Y%m%dT%H%M%S}", f"DTEND;TZID=America/Toronto:{end:%Y%m%dT%H%M%S}"]
        else:
            end = (e["end_d"] or e["d"]) + dt.timedelta(days=1)
            lines += [f"DTSTART;VALUE=DATE:{e['d']:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}"]
        loc = ", ".join(x for x in [e.get("venue"), e.get("city")] if x)
        lines.append(f"SUMMARY:{ics_esc(e['title'])}")
        if loc:
            lines.append(f"LOCATION:{ics_esc(loc)}")
        url = e["url"] if e.get("url", "").startswith("http") else absu(e.get("url") or "/events/")
        lines.append(f"URL:{url}")
        if e.get("summary"):
            lines.append(f"DESCRIPTION:{ics_esc(e['summary'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    write("events.ics", "\r\n".join(lines) + "\r\n")


def build_support():
    s = load_json("support.json")
    sup = SITE["support"]
    live = bool(sup.get("live")) and bool(sup.get("contribute_url"))
    platform = esc(sup.get("platform") or "a third-party platform")
    pay = ""
    if live:   # contribution links render only when payments are open (decision 10)
        pay = f'<a class="btn primary" href="{esc(sup["contribute_url"])}" target="_blank" rel="noopener">{S("support.monthly_button")} &#8599;</a>'
        if sup.get("one_time_url"):
            pay += f'<a class="btn secondary" href="{esc(sup["one_time_url"])}" target="_blank" rel="noopener">{S("support.once_button")} &#8599;</a>'
        pay = f'<div class="actions">{pay}</div>'
    hero_actions = (f'<div class="actions"><a class="btn primary" href="#contribute">{S("support.hero_contribute")}</a><a class="btn secondary" href="#signup">{S("support.hero_signup")}</a></div>' if live
                    else f'<div class="actions"><a class="btn primary" href="#signup">{S("support.hero_signup")}</a></div>')
    pledge = "".join(f"<p>{inline(p)}</p>" for p in s["pledge"]["paragraphs"])
    uses = [{"title": esc(x["title"]), "body": f'<p>{esc(x["text"])}</p>'} for x in s["uses"]]
    faq = "".join(disclosure(esc(q["q"]), f'<div class="d-body"><p>{esc(q["a"])}</p></div>') for q in s["faq"])
    c = s["contribute"]
    note = esc(c["note"]).replace("a third-party platform", platform)
    sg = SITE["signup"]
    body = f"""{page_hero(s['kicker'], esc(s['headline']), esc(s['lede']), hero_actions, mark='support')}
<section class="section" id="contribute"><div class="wrap two-col">
  {block(esc(s['pledge']['title']), pledge, kicker=S("support.pledge_label"), variant="panel", level=2, title_cls="t-sub", cls="quiet")}
  {block(esc(c['title']), f'<p>{esc(c["text"])}</p>' + pay + f'<p class="fine">{note}</p>', kicker=S("support.contribute_label"), variant="panel", level=2, title_cls="t-sub", cls="accent")}
</div></section>
<section class="section band limestone"><div class="wrap">{section_head(S("support.uses_heading"), kicker=S("support.uses_label"), tier="minor")}{nup(uses)}</div></section>
<section class="section" id="signup"><div class="wrap two-col">
  <div class="flow"><h2 class="t-sub">{esc(sg['title'])}</h2><p class="t-lede">{esc(sg['text'])}</p><p class="t-small">{S("support.feed_note", rss=f'<a href="{u("/feed.xml")}">{S("support.feed_rss_link")}</a>', calendar=f'<a href="{u("/events.ics")}">{S("support.feed_calendar_link")}</a>')}</p></div>
  <div>{signup_form('full')}</div>
</div></section>
<section class="section"><div class="wrap grid"><div class="lg-8">{section_head(S("support.faq_heading"), kicker=S("support.faq_label"), tier="minor")}<div class="disclosures">{faq}</div></div></div></section>"""
    render(T(R("support.meta_title")), R("support.meta_description"), body, path="/support/", current="/support/")
    for old, anchor in (("subscribe", ""), ("signup", "#signup")):
        write(f"{old}/index.html", f"""<!DOCTYPE html><html lang="en-CA"><head><meta charset="utf-8"><title>Support | {esc(NAME)}</title>
<meta http-equiv="refresh" content="0; url={u('/support/')}{anchor}"><link rel="canonical" href="{absu('/support/')}"><meta name="robots" content="noindex"></head>
<body><p>This has moved to <a href="{u('/support/')}{anchor}">the support page</a>.</p></body></html>
""")


def build_about():
    meta, md = read_md(CONTENT / "pages" / "about.md")
    facts = "".join(f'<div><dt>{S("about.fact_" + k + "_label")}</dt><dd>{S("about.fact_" + k)}</dd></div>' for k in ("based", "education", "work", "civic"))
    facts = f'<dl class="glance">{facts}</dl>'
    about_img = img_path('eric-about') if meta.get('image', '').startswith('/assets/img/eric-about') else meta.get('image')
    body = f"""{page_hero(R('about.kicker'), esc(meta.get('headline', 'About')), esc(meta.get('lede', '')), cta_actions(), image=about_img, alt=NAME)}
<section class="section"><div class="wrap main-rail reading"><div class="prose">{md_to_html(md)}</div>
<aside class="rail">{rail_block(S("about.glance_label"), facts)}{rail_block(S("about.press_label"), f'<ul class="link-list"><li>{link_to(S("about.headshot_link"), "/assets/img/eric-headshot.jpg", download=True)}</li><li>{link_to(S("about.kit_link"), "/media/#media-kit")}</li></ul>')}</aside></div></section>"""
    render(T(R("about.meta_title")), SITE["description"], body, path="/about/", current="/about/", image=meta.get("image"), kind="profile", reading=True)


def build_contact():
    c = SITE["contact"]
    socials = "".join(f'<li><a href="{esc(sc["url"])}" rel="me noopener" target="_blank">{esc(sc["name"])}{(" " + esc(sc["handle"])) if sc.get("handle") else ""}</a></li>' for sc in SITE["socials"] if sc.get("show", True))
    booking = f'<div class="actions"><a class="btn secondary sm" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">{S("site.book_call")}</a></div>' if SITE.get("booking_url") else ""
    addr = f'<p class="t-small muted">{S("contact.mail_prefix")} {esc(SITE["mailing_address"])}</p>' if SITE.get("mailing_address") else ""
    rail = (block(S("contact.consulting_heading"), f'<p>{S("contact.consulting_text")}</p>', kicker=S("contact.consulting_label"),
                  actions=f'<p>{link_to(S("contact.consulting_button"), contact_href("consulting").replace(BASE, "", 1))}</p>') +
            block(S("contact.media_heading"), f'<p>{S("contact.media_text", link=f"<a href=\"{u("/media/#media-kit")}\">{S("contact.media_link")}</a>")}</p>', kicker=S("contact.media_label"),
                  actions=f'<p>{link_to(S("contact.media_button"), contact_href("media").replace(BASE, "", 1))}</p>') +
            block(S("contact.follow_heading"), f'<ul class="social-list">{socials}</ul>{addr}<p class="t-small">{link_to(S("contact.signup_link"), "/support/#signup")}</p>', kicker=S("contact.follow_label")))
    body = f"""{page_hero(R('contact.kicker'), esc(c['headline']), esc(c['text']), mark='contact')}
<section class="section"><div class="wrap main-rail">
  <div>{label(S("contact.form_label"))}{contact_form()}{booking}</div>
  <aside class="rail">{rail}</aside>
</div></section>"""
    render(T(R("contact.meta_title")), R("contact.meta_description"), body, path="/contact/", current="/contact/")


def build_privacy():
    meta, md = read_md(CONTENT / "pages" / "privacy.md")
    upd = fmt_date(parse_date(meta["updated"])) if meta.get("updated") else fmt_date(TODAY)
    body = f"""{page_hero(R('privacy.kicker'), esc(meta.get('headline', 'Privacy policy')), esc(meta.get('lede', '')), mark='privacy', meta=meta_line(S("privacy.updated", date=upd)))}
<section class="section"><div class="wrap main-rail reading"><div class="prose">{md_to_html(md)}</div>
<aside class="rail">{rail_block(S("privacy.rail_label"), f'<p>{S("privacy.rail_text")}</p><p>{link_to(S("privacy.rail_link"), "/contact/")}</p>')}</aside></div></section>"""
    render(T(R("privacy.meta_title")), R("privacy.meta_description"), body, path="/privacy/", current="", reading=True)


def build_404():
    body = f"""{page_hero(R('notfound.kicker'), S('notfound.headline'), S('notfound.lede'), mark='notfound')}
<section class="section"><div class="wrap"><div class="actions notfound-actions"><a class="btn primary" href="{u('/')}">{S("notfound.home")}</a><a class="btn secondary" href="{u('/writing/')}">{S("notfound.writing")}</a><a class="btn secondary" href="{u('/consulting/')}">{S("notfound.consulting")}</a><a class="btn secondary" href="{u('/policy/')}">{S("notfound.policy")}</a></div><div class="empty-arch">{DECAL_STAGE}</div></div></section>"""
    render(T(R("notfound.meta_title")), R("notfound.meta_title") + ".", body, path="/404.html", current="", sitemap=False)


# --------------------------------------------------------------------------- feeds and machine-readable
def build_feeds(posts, media):
    authored = authored_items(posts, media)
    by_url = {u(p["url"]): p for p in posts}
    items, jitems = [], []
    for a in authored[:40]:
        if a["external"]:
            link, desc, content = a["url"], a["summary"] or f"Published in {a['source']}.", f"<p>Published in {esc(a['source'])}. <a href=\"{esc(a['url'])}\">Read at {esc(a['source'])}</a>.</p>"
        else:
            p_ = by_url[a["url"]]
            link, desc, content = absu(p_["url"]), p_["summary"], absolutize(p_["html"])
        items.append(f"""<item>
<title>{esc(a['title'])}</title>
<link>{esc(link)}</link>
<guid isPermaLink="true">{esc(link)}</guid>
<pubDate>{rfc822(a['d'])}</pubDate>
<category>{esc(a['source'])}</category>
<description>{esc(desc)}</description>
<content:encoded><![CDATA[{content}]]></content:encoded>
</item>""")
        jitems.append({"id": link, "url": link, "title": a["title"], "summary": desc, "content_html": content,
                       "date_published": a["d"].isoformat() + "T12:00:00Z", "tags": [a["source"]],
                       **({"external_url": a["url"]} if a["external"] else {})})
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{esc(NAME)}: writing</title>
<link>{DOMAIN}/writing/</link>
<atom:link href="{DOMAIN}/feed.xml" rel="self" type="application/rss+xml"/>
<description>{esc(SITE['short_description'])}</description>
<language>en-ca</language>
<lastBuildDate>{email.utils.format_datetime(NOW)}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
    write("feed.xml", rss)
    jf = {"version": "https://jsonfeed.org/version/1.1", "title": f"{NAME}: writing", "home_page_url": DOMAIN + "/writing/",
          "feed_url": DOMAIN + "/feed.json", "description": SITE["short_description"], "language": "en-CA",
          "authors": [{"name": NAME, "url": DOMAIN + "/"}], "items": jitems}
    write("feed.json", json.dumps(jf, ensure_ascii=False, indent=1))


def build_sitemap_robots():
    urls = "".join(f"<url><loc>{absu(p)}</loc><lastmod>{d.isoformat()}</lastmod></url>\n" for p, d in SITEMAP)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")


def build_llms(posts, media, events, policy_items):
    authored = authored_items(posts, media)
    about = [m for m in media if m["kind"] in ("interview", "coverage")]
    up = [e for e in events if not e["past"]]
    lines = [f"# {NAME}", "", f"> {SITE['description']}", "",
             f"Contact: {DOMAIN}/contact/ (form). Location: {SITE['location']['label']}. Socials: " + ", ".join(f"{s['name']} {s['url']}" for s in SITE["socials"] if s.get("show", True)), "",
             "## Pages", ""]
    for n in SITE["nav"] + [{"label": "In the media", "href": "/media/"}, {"label": "About", "href": "/about/"}, {"label": "Support and sign-up", "href": "/support/"}, {"label": "Privacy", "href": "/privacy/"}]:
        lines.append(f"- [{n['label']}]({absu(n['href'])})")
    lines += ["", "## Machine-readable", "", f"- RSS: {DOMAIN}/feed.xml", f"- JSON Feed: {DOMAIN}/feed.json", f"- Calendar (iCalendar): {DOMAIN}/events.ics",
              f"- Sitemap: {DOMAIN}/sitemap.xml", f"- JSON API: {DOMAIN}/api/site.json, /api/writing.json, /api/posts.json, /api/media.json, /api/events.json", "",
              "## Public policy work", ""]
    for it in policy_items:
        lines.append(f"- [{it['title']}]({absu(it['url'])}): {it.get('role', '')}. {it.get('summary', '')}")
    lines += ["", "## Writing (by Eric, wherever published)", ""]
    for a in authored:
        link = a["url"] if a["external"] else absu(a["url"].replace(BASE, "", 1))
        lines.append(f"- [{a['title']}]({link}) ({a['d'].isoformat()}, {a['source']}){(': ' + a['summary']) if a.get('summary') else ''}")
    lines += ["", "## In the media (about Eric)", ""]
    for m in about:
        lines.append(f"- {m['outlet']}: [{m['title']}]({m['url']}) ({m['date']}, {m['kind']}, {m.get('format', '')})")
    if up:
        lines += ["", "## Upcoming events", ""]
        for e in up:
            lines.append(f"- {e['date']}: {e['title']} ({e.get('city', '')}) {e.get('url', '')}".rstrip())
    write("llms.txt", "\n".join(lines) + "\n")


def build_api(posts, media, events):
    def clean(d, drop=("d", "end_d", "html")):
        return {k: v for k, v in d.items() if k not in drop}
    write("api/site.json", json.dumps({"name": NAME, "url": DOMAIN, "description": SITE["description"], "contact": DOMAIN + "/contact/", "location": SITE["location"]["label"],
                                       "socials": [{"name": s["name"], "url": s["url"]} for s in SITE["socials"] if s.get("show", True)],
                                       "pages": [{"label": n["label"], "url": absu(n["href"])} for n in SITE["nav"]],
                                       "feeds": {"rss": DOMAIN + "/feed.xml", "json": DOMAIN + "/feed.json", "ics": DOMAIN + "/events.ics"},
                                       "generated": NOW.isoformat()}, ensure_ascii=False, indent=1))
    write("api/posts.json", json.dumps([{"title": p["title"], "url": absu(p["url"]), "date": p["date"].isoformat(), "category": p["category_label"],
                                         "summary": p["summary"], "tags": p["tags"], "word_count": p["words"], "image": absu(p["image"]) if p.get("image") else None} for p in posts], ensure_ascii=False, indent=1))
    write("api/media.json", json.dumps([clean(m) for m in media], ensure_ascii=False, indent=1))
    write("api/writing.json", json.dumps([{"title": a["title"], "date": a["d"].isoformat(), "url": a["url"] if a["external"] else absu(a["url"].replace(BASE, "", 1)),
                                           "source": a["source"], "external": a["external"], "author": NAME, "summary": a.get("summary", ""),
                                           **({"companion": absu(a["companion"][1].replace(BASE, "", 1))} if a.get("companion") else {})}
                                          for a in authored_items(posts, media)], ensure_ascii=False, indent=1))
    write("api/events.json", json.dumps([clean(e) for e in events], ensure_ascii=False, indent=1))


PHOTO_SLOTS = {  # photos/<name> -> assets/img/<target>, max dimension
    "hero": ("eric-hero.jpg", 1800), "consulting": ("eric-consulting.jpg", 1800), "about": ("eric-about.jpg", 1600),
    "headshot": ("eric-headshot.jpg", 1600), "support": ("support.jpg", 1800), "campaign": ("eric-campaign.jpg", 1800),
    "more-neighbours": ("more-neighbours.jpg", 1800), "build-toronto": ("build-toronto.jpg", 1800),
    "article-placeholder": ("article-placeholder.jpg", 1200),
}


def sync_photos():
    """Copy photographs from the photos/ drop folder into assets/img, resized, replacing placeholders."""
    import subprocess
    pdir = HERE / "photos"
    if not pdir.exists():
        return
    exts = (".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp")
    def has_alpha(src):
        r = subprocess.run(["sips", "-g", "hasAlpha", str(src)], capture_output=True, text=True)
        return "hasAlpha: yes" in r.stdout
    def source_max(src):
        r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(src)], capture_output=True, text=True)
        dims = [int(x.split(":")[1]) for x in r.stdout.splitlines() if "pixel" in x]
        return max(dims) if dims else 0
    def convert(src, dest, maxdim):
        maxdim = min(maxdim, source_max(src) or maxdim)            # never upscale
        if src.suffix.lower() == ".png" and has_alpha(src):      # keep cut-outs transparent
            dest = dest.with_suffix(".png")
            subprocess.run(["sips", "-s", "format", "png", "-Z", str(maxdim), str(src), "--out", str(dest)], capture_output=True)
            jpg = dest.with_suffix(".jpg")
            if jpg.exists():
                jpg.unlink()
        else:
            dest = dest.with_suffix(".jpg")
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", "-Z", str(maxdim), str(src), "--out", str(dest)], capture_output=True)
            png = dest.with_suffix(".png")
            if png.exists():
                png.unlink()
        return dest
    for stem, (target, maxdim) in PHOTO_SLOTS.items():
        for ext in exts:
            src = pdir / (stem + ext)
            if src.exists():
                out = convert(src, ASSETS / "img" / target, maxdim)
                print("  photo:", src.name, "->", out.name)
                break
    for ext in exts:
        src = pdir / ("share" + ext)
        if src.exists():
            dest = ASSETS / "img" / "og-default.jpg"
            convert(src, dest, 1200)
            subprocess.run(["sips", "-c", "630", "1200", str(dest)], capture_output=True)
            print("  photo: share ->", dest.name)
            break
    wdir = pdir / "writing"
    if wdir.exists():
        (ASSETS / "img" / "writing").mkdir(exist_ok=True)
        for src in sorted(wdir.iterdir()):
            if src.suffix.lower() in exts:
                convert(src, ASSETS / "img" / "writing" / (src.stem + ".jpg"), 1200)
                print("  photo: writing/" + src.name)


def img_path(stem):
    """Site path for an image slot: the transparent .png if one was supplied, otherwise the .jpg."""
    for ext in (".png", ".jpg"):
        if (ASSETS / "img" / (stem + ext)).exists():
            return f"/assets/img/{stem}{ext}"
    return f"/assets/img/{stem}.jpg"


def is_cutout(path):
    return path.endswith(".png")


# Portrait stage: all ink inside the 400x520 viewBox (spring lines end at its edges; plinth below the baseline).
DECAL_STAGE = ('<svg class="decal decal-stage" viewBox="0 0 400 520" preserveAspectRatio="xMidYMax meet" aria-hidden="true" focusable="false">'
               '<path class="niche" d="M44 500V214A156 156 0 0 1 356 214V500Z"/>'
               '<path class="heavy" d="M14 500V204A186 186 0 0 1 386 204V500"/>'
               '<path d="M44 500V214A156 156 0 0 1 356 214V500"/>'
               '<path d="M1.25 204H14M386 204H398.75M1.25 214H44M356 214H398.75"/>'
               '<path class="heavy" d="M200 18V34"/>'
               '<path class="heavy" d="M1.25 500H398.75"/><path d="M1.25 514H398.75"/><path class="heavy" d="M14 500V514M386 500V514"/>'
               '</svg>')

# Entablature under every header: drawn in CSS from the grid itself (heavy and thin rule, a tick on every
# gutter centre and at both ends), so the ticks ARE the columns.
ENTABLATURE = '<div class="entablature" aria-hidden="true"></div>'
PLINTH = '<div class="plinth" aria-hidden="true"></div>'

# Header marks: square 300x300 drawings in the archway family (heavy outer arch, thin inner arch, limestone niche),
# one composition per page, each standing on a double base rule at y 286/298.
# Ink stays inside the viewBox; the mark fills the shorter side of its zone, bottom-right.
_BASE = '<path class="heavy" d="M1.25 286H298.75"/><path d="M1.25 298H298.75"/>'
HEADER_MARKS = {
    "writing": '<path class="niche" d="M62 286V152A88.0 88.0 0 0 1 238 152V286Z"/><path class="heavy" d="M50 286V140A100.0 100.0 0 0 1 250 140V286"/><path d="M62 286V152A88.0 88.0 0 0 1 238 152V286"/><path d="M1.25 140H50M250 140H298.75"/><path d="M92 180H208M92 204H190M92 228H208M92 252H170"/>' + _BASE,
    "media": '<path class="niche" d="M102 286V192A48.0 48.0 0 0 1 198 192V286Z"/><path class="heavy" d="M90 286V180A60.0 60.0 0 0 1 210 180V286"/><path d="M102 286V192A48.0 48.0 0 0 1 198 192V286"/><path d="M60 180A90 90 0 0 1 240 180M30 180A120 120 0 0 1 270 180M1.25 180A148.75 148.75 0 0 1 298.75 180"/>' + _BASE,
    "events": '<path class="heavy" d="M1.25 150H298.75"/><path d="M1.25 162H298.75"/><path d="M8 286V216A22.0 22.0 0 0 1 52 216V286"/><path d="M68 286V216A22.0 22.0 0 0 1 112 216V286"/><path class="niche" d="M128 286V216A22.0 22.0 0 0 1 172 216V286Z"/><path class="heavy" d="M122 286V210A28.0 28.0 0 0 1 178 210V286"/><path d="M128 286V216A22.0 22.0 0 0 1 172 216V286"/><path d="M188 286V216A22.0 22.0 0 0 1 232 216V286"/><path d="M248 286V216A22.0 22.0 0 0 1 292 216V286"/>' + _BASE,
    "policy": '<path class="heavy" d="M1.25 30H298.75"/><path d="M1.25 44H298.75"/><path class="niche" d="M124 286V132A26.0 26.0 0 0 1 176 132V286Z"/><path class="heavy" d="M112 286V120A38.0 38.0 0 0 1 188 120V286"/><path d="M124 286V132A26.0 26.0 0 0 1 176 132V286"/><path d="M20 286V120A38.0 38.0 0 0 1 96 120V286"/><path d="M204 286V120A38.0 38.0 0 0 1 280 120V286"/>' + _BASE,
    "support": '<path class="niche" d="M82 254V152A68 68 0 0 1 218 152V254Z"/><path class="heavy" d="M70 254V140A80 80 0 0 1 230 140V254"/><path d="M82 254V152A68 68 0 0 1 218 152V254"/><path d="M40 254H260M20 270H280"/><path d="M40 254V270M260 254V270M20 270V286M280 270V286"/>' + _BASE,
    "contact": '<path class="niche" d="M74 286V124A76 76 0 0 1 226 124V286Z"/><path class="heavy" d="M60 286V110A90 90 0 0 1 240 110V286"/><path d="M74 286V124A76 76 0 0 1 226 124V286"/><path d="M60 124H240"/><path d="M1.25 110H60M240 110H298.75"/>' + _BASE,
    "privacy": '<path class="niche" d="M62 286V162A88.0 88.0 0 0 1 238 162V286Z"/><path class="heavy" d="M50 286V150A100.0 100.0 0 0 1 250 150V286"/><path d="M62 286V162A88.0 88.0 0 0 1 238 162V286"/><path d="M100 286V96M150 286V74M200 286V96M62 200H238M62 244H238"/>' + _BASE,
    "notfound": '<path class="heavy" d="M50 286V150A100 100 0 0 1 135 51.1"/><path class="heavy" d="M165 51.1A100 100 0 0 1 250 150V286"/><path class="niche" d="M62 286V162A88.0 88.0 0 0 1 238 162V286Z"/><path d="M62 286V162A88.0 88.0 0 0 1 238 162V286"/><path class="heavy" d="M141 268H159V286H141Z"/>' + _BASE,
}
HEADER_MARKS["default"] = HEADER_MARKS["contact"]


def header_mark(name):
    paths = HEADER_MARKS.get(name) or HEADER_MARKS["default"]
    return f'<svg class="header-mark" viewBox="0 0 300 300" preserveAspectRatio="xMaxYMax meet" aria-hidden="true" focusable="false">{paths}</svg>'


ENDMARK = ('<svg class="endmark" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M8 40V22A14 14 0 0 1 36 22V40M2 40H42"/></svg>')


def portrait(path, alt, cls="portrait-stage", attrs=""):
    """A portrait slot: a cut-out stands on a baseline inside an open portal; a photograph is shown plain."""
    if is_cutout(path):
        return f'<figure class="{cls} cutout">{DECAL_STAGE}<img src="{u(path)}" alt="{esc(alt)}" width="1122" height="1402" {attrs}></figure>'
    return f'<figure class="{cls}"><img src="{u(path)}" alt="{esc(alt)}" width="1600" height="1200" {attrs}></figure>'


def copy_assets():
    shutil.copytree(ASSETS, OUT / "assets", dirs_exist_ok=True)


# --------------------------------------------------------------------------- main
def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    sync_photos()
    copy_assets()
    posts, media, events = load_posts(), load_media(), load_events()
    policy = load_policy()
    build_home(posts, media, events, policy[2])
    build_consulting()
    build_writing(posts, media)
    build_media(media)
    build_policy(policy, media)
    build_events(events)
    build_support()
    build_about()
    build_contact()
    build_privacy()
    build_404()
    build_feeds(posts, media)
    build_sitemap_robots()
    build_llms(posts, media, events, policy[2])
    build_api(posts, media, events)
    write(".nojekyll", "")
    if not BASE and not DOMAIN_OVERRIDE:
        write("CNAME", DOMAIN.split("//")[1] + "\n")   # custom domain only on the production build
    for s in SITE["socials"]:
        if s.get("verify"):
            warn(f"social {s['name']}: {s['verify']}")
    if not SITE["form"]["endpoint"]:
        warn("form.endpoint is empty: subscribe form falls back to mailto")
    elif "sibforms.com" in SITE["form"]["endpoint"] and "EMAIL" not in SITE["form"]["fields"].values():
        warn("form.fields do not use Brevo's attribute names (EMAIL, FIRSTNAME, ...): Brevo will refuse sign-ups")
    if not SITE["support"].get("live"):
        warn("support.live is false: contribution buttons are disabled")
    print(f"Built {len(SITEMAP)} pages + feeds into {OUT.relative_to(HERE) if OUT.is_relative_to(HERE) else OUT}/ (base='{BASE or '/'}')")
    for w in WARN:
        print("  warning:", w)


if __name__ == "__main__":
    main()
