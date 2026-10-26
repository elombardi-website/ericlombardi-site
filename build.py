#!/usr/bin/env python3
"""ericlombardi.ca — static site generator. Standard library only.

    python3 build.py                   # build docs/
    python3 build.py --base /repo --domain https://user.github.io/repo
                                       # test build for GitHub project pages (no CNAME written)
    python3 build.py --drafts          # include posts marked  draft: true
    python3 build.py --placeholders    # include sample events marked "placeholder": true (preview only)

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
CONTENT, ASSETS, OUT = HERE / "content", HERE / "assets", HERE / "docs"
ARGS = sys.argv[1:]
BASE = ARGS[ARGS.index("--base") + 1].rstrip("/") if "--base" in ARGS else ""
DOMAIN_OVERRIDE = ARGS[ARGS.index("--domain") + 1].rstrip("/") if "--domain" in ARGS else ""
INCLUDE_DRAFTS = "--drafts" in ARGS
INCLUDE_PLACEHOLDERS = "--placeholders" in ARGS   # sample events are excluded unless asked for


def load_json(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


SITE = load_json("site.json")
DOMAIN = DOMAIN_OVERRIDE or SITE["domain"].rstrip("/")
NAME = SITE["name"]
EMAIL = SITE["email"]
TODAY = dt.date.today()
NOW = dt.datetime.now(dt.timezone.utc)
SITEMAP = []     # (url, lastmod date)
WARN = []
PERSON_ID = DOMAIN + "/#person"
SITE_ID = DOMAIN + "/#website"
CRUMB = {"consulting": "Consulting", "writing": "Writing", "media": "Media", "policy": "Public policy",
         "events": "Events", "support": "Support", "about": "About",
         "contact": "Contact", "privacy": "Privacy", "category": "Category"}


# --------------------------------------------------------------------------- helpers
def warn(msg): WARN.append(msg)
def esc(s): return hm.escape("" if s is None else str(s), quote=True)
def u(path): return (BASE + path) if path.startswith("/") else path
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
    return "\n".join(out)


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
DECAL_PORTAL = ('<svg class="decal decal-portal" viewBox="0 0 240 240" aria-hidden="true" focusable="false">'
                '<path d="M0 4H236V240"/><path d="M136 24H216V104"/><path d="M192 24V8H232V48H216"/>'
                '<path d="M166 2A72 72 0 0 1 238 74"/></svg>')
DECAL_ARC = ('<svg class="decal decal-arc" viewBox="0 0 320 320" aria-hidden="true" focusable="false">'
             '<path d="M0 320A320 320 0 0 1 320 0"/><path d="M0 236H320"/></svg>')
SYMBOLS = {
    "grid": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M6 6H38V38H6ZM6 17H38M6 27H38M17 6V38M27 6V38"/></svg>',
    "lines": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M6 10H38M6 18H30M6 26H38M6 34H22"/></svg>',
    "portal": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M8 38V22A14 14 0 0 1 36 22V38M14 38V26M30 38V26"/></svg>',
    "steps": '<svg class="symbol" viewBox="0 0 44 44" aria-hidden="true" focusable="false"><path d="M6 38V27H17V16H28V6H38M6 38H38"/></svg>',
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
        return "No cookies, no trackers."
    parts = []
    if a:
        parts.append("privacy-friendly analytics without cookies")
    if x:
        parts.append("embedded posts from X on the public-policy page, which may set their own cookies")
    return "No advertising trackers. This site uses " + " and ".join(parts) + "."


def head_meta(title, description, path, image=None, kind="website", reading=False):
    canonical = absu(path)
    img = absu(image or SITE["og_image"])
    reading_css = f'\n<link rel="stylesheet" href="{u("/assets/css/reading.css")}">' if reading else ""
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta name="author" content="{esc(NAME)}">
<meta name="robots" content="index, follow, max-image-preview:large">
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
    return f"""<header class="site-header"><div class="wrap">
  <a class="wordmark" href="{u('/')}">{esc(NAME)}</a>
  <nav class="primary" aria-label="Primary">{links}</nav>
  <a class="btn small secondary header-cta" href="{u('/support/')}">Support</a>
  <button class="burger" aria-label="Menu" aria-expanded="false" aria-controls="mobile-nav"><span></span><span></span><span></span></button>
</div>
<nav class="mobile" id="mobile-nav" aria-label="Mobile">{links}<a href="{u('/about/')}">About</a><a class="btn secondary" href="{u('/support/')}">Support the work</a></nav>
</header>"""


def footer_html():
    socials = "".join(f'<a href="{esc(s["url"])}" rel="me noopener" target="_blank">{esc(s["name"])}</a>'
                      for s in SITE["socials"] if s.get("show", True))
    explore = nav_links() + f'<a href="{u("/media/")}">In the media</a><a href="{u("/about/")}">About</a>'
    return f"""<footer class="site-footer"><div class="wrap">
  <div class="footer-grid">
    <div><a class="wordmark" href="{u('/')}">{esc(NAME)}</a><p class="about">{esc(SITE['short_description'])}</p></div>
    <div><h4>Explore</h4><nav>{explore}</nav></div>
    <div><h4>Follow</h4><div class="links">{socials}<a href="{u('/feed.xml')}">RSS feed</a></div></div>
    <div><h4>Stay in touch</h4><div class="links"><a href="mailto:{EMAIL}">{EMAIL}</a><a href="{u('/support/#signup')}">Sign up for updates</a><a href="{u('/support/')}">Support the work</a><a href="{u('/events/')}">Where I'll be</a></div></div>
  </div>
  <p class="fine">&copy; {TODAY.year} {esc(NAME)}. {esc(SITE['location']['label'])}. <a href="{u('/privacy/')}">Privacy</a> &middot; <a href="{u('/llms.txt')}">llms.txt</a> &middot; <a href="{u('/sitemap.xml')}">Sitemap</a>. {tracking_line()}</p>
</div></footer>"""


def breadcrumb_ld(path):
    parts = [p for p in path.strip("/").split("/") if p]
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": DOMAIN + "/"}]
    acc = ""
    for i, p in enumerate(parts, start=2):
        acc += "/" + p
        items.append({"@type": "ListItem", "position": i, "name": CRUMB.get(p, p.replace("-", " ").title()), "item": DOMAIN + acc + "/"})
    return {"@type": "BreadcrumbList", "itemListElement": items}


def person_ld():
    return {"@type": "Person", "@id": PERSON_ID, "name": NAME, "url": DOMAIN + "/",
            "image": absu("/assets/img/eric-headshot.jpg"), "jobTitle": SITE["job_title"],
            "description": SITE["short_description"], "email": "mailto:" + EMAIL,
            "address": {"@type": "PostalAddress", "addressLocality": SITE["location"]["city"],
                        "addressRegion": SITE["location"]["region"], "addressCountry": SITE["location"]["country"]},
            "alumniOf": {"@type": "CollegeOrUniversity", "name": "University of Waterloo"},
            "sameAs": [s["url"] for s in SITE["socials"] if s.get("show", True)],
            "knowsAbout": SITE["knows_about"]}


def render(title, description, body, *, path, current="", image=None, kind="website", jsonld=None, lastmod=None, body_class="", sitemap=True, reading=False):
    graph = [person_ld(),
             {"@type": "WebSite", "@id": SITE_ID, "url": DOMAIN + "/", "name": NAME, "publisher": {"@id": PERSON_ID}, "inLanguage": "en-CA"},
             {"@type": "WebPage", "@id": absu(path), "url": absu(path), "name": title, "description": description,
              "isPartOf": {"@id": SITE_ID}, "about": {"@id": PERSON_ID}, "inLanguage": "en-CA",
              "breadcrumb": breadcrumb_ld(path)}]
    graph += jsonld or []
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")
    doc = f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
{head_meta(title, description, path, image, kind, reading)}
<script type="application/ld+json">{ld}</script>
</head>
<body class="{body_class}">
<a class="skip" href="#main">Skip to content</a>
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
def T(s):
    return f"{s} | {NAME}"


def label(text, rule=False):
    return f'<p class="label{" rule" if rule else ""}">{text}</p>'


def page_hero(kicker, headline, lede="", actions="", image=None, alt=""):
    lede_html = f'<p class="lede">{lede}</p>' if lede else ""
    if image:
        return (f'<section class="page-hero"><div class="wrap"><div class="inner with-image"><div>{label(esc(kicker), rule=True)}<h1>{headline}</h1>{lede_html}{actions}</div>'
                f'<img src="{u(image)}" alt="{esc(alt)}" width="1600" height="1200"></div></div></section>')
    return (f'<section class="page-hero"><div class="wrap"><div class="inner"><div>{label(esc(kicker), rule=True)}<h1>{headline}</h1></div>'
            f'<div class="side">{lede_html}{actions}</div></div></div></section>')


def cat_link(p):
    return f'<a class="cat" href="{u("/writing/category/" + p["category"] + "/")}">{esc(p["category_label"])}</a>'


def post_entry(p, compact=False):
    cls = "entry compact" if compact else "entry with-meta"
    meta = f'<div class="meta">{cat_link(p)}<span>{fmt_date(p["date"])}</span></div>'
    body = f'<div><h3 class="title-editorial"><a href="{u(p["url"])}">{esc(p["title"])}</a></h3><p>{esc(p["summary"])}</p><a class="more" href="{u(p["url"])}">Read the essay &rarr;</a></div>'
    return f'<li data-filter-item="posts" data-values="{p["category"]}"><article class="{cls}">{meta}{body}</article></li>'


def feature_post(p):
    return (f'<article class="feature-post"><div class="meta">{cat_link(p)}<span>{fmt_date(p["date"])}</span></div>'
            f'<h3 class="title-feature"><a href="{u(p["url"])}">{esc(p["title"])}</a></h3><p class="summary">{esc(p["summary"])}</p>'
            f'<a class="btn secondary small" href="{u(p["url"])}">Read the essay</a></article>')


def media_row(m, group="media", extra=False):
    fmt = m.get("format", "")
    return (f'<li data-filter-item="{group}" data-values="{esc(m["kind"])} {esc(fmt)}"{" data-extra hidden" if extra else ""}><a class="row" href="{esc(m["url"])}" target="_blank" rel="noopener">'
            f'<span class="outlet">{esc(m["outlet"])}</span><span class="title">{esc(m["title"])}</span>'
            f'<span class="date">{fmt_date(m["d"])}<br><span class="fmt">{esc(fmt)}</span></span></a></li>')


def media_by_year(items, group="media", limit=None, wide=False):
    out, year, i = [], None, 0
    cls = "list wide" if wide else "list compact"
    for m in items:
        extra = limit is not None and i >= limit
        if m["d"].year != year:
            if year is not None:
                out.append("</ul>")
            year = m["d"].year
            out.append(f'<h3 class="year-head" data-year-head="{group}"{" data-extra hidden" if extra else ""}>{year}</h3><ul class="{cls}">')
        out.append(media_row(m, group, extra))
        i += 1
    if year is not None:
        out.append("</ul>")
    html_ = "".join(out)
    if limit is not None and len(items) > limit:
        html_ = (f'<div class="expander" data-expander="{group}" data-expanded="0">{html_}'
                 f'<button class="btn secondary small expand" type="button" data-expand-for="{group}">Show all {len(items)}</button></div>')
    return html_


def event_block(e):
    d, past = e["d"], e["past"]
    where = " &middot; ".join(esc(x) for x in [e.get("venue"), e.get("city")] if x)
    when = fmt_date(d) + (f" to {fmt_date(e['end_d'])}" if e.get("end_d") else "") + (f" &middot; {esc(e['time'])}" if e.get("time") else "")
    link = ""
    if e.get("url"):
        ext = e["url"].startswith("http")
        link = f'<div class="actions"><a class="btn small {"secondary" if past else "primary"}" href="{u(e["url"]) if not ext else esc(e["url"])}"{" target=_blank rel=noopener" if ext else ""}>{"Details" if past else "Details and registration"}{" &#8599;" if ext else ""}</a></div>'
    ph = ' <span class="tag">Sample</span>' if e.get("placeholder") else ""
    summ = f'<p>{esc(e["summary"])}</p>' if e.get("summary") else ""
    return (f'<article class="event{" past" if past else ""}"><div class="datebox"><span class="m">{d:%b}</span><span class="d">{d.day}</span><span class="y">{d.year}</span></div>'
            f'<div><div class="meta"><span class="cat">{esc(e.get("kind", "Event"))}</span>{ph}</div><h3>{esc(e["title"])}</h3>'
            f'<div class="where">{when}{(" &middot; " + where) if where else ""}</div>{summ}{link}</div></article>')


def signup_form(variant="full"):
    """Visible labels in every variant. 'inline' only spreads into one row at wide widths."""
    f = SITE["form"]
    fl = f["fields"]
    hidden = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in f.get("hidden", {}).items())
    action = esc(f["endpoint"]) if f["endpoint"] else "#"
    statement = SITE["signup"]["statement"] + f' <a href="{u("/privacy/")}">Privacy</a>.'
    if SITE.get("mailing_address"):
        statement += f' {esc(NAME)}, {esc(SITE["mailing_address"])}.'
    consent = (f'<label class="consent"><input type="checkbox" name="consent" value="yes" required> {statement}</label>'
               if f.get("consent") == "checkbox" else f'<p class="consent-note">{statement}</p>')
    hp = '<div class="hp" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></div>'
    common = f'action="{action}" method="{esc(f.get("method", "POST"))}" data-endpoint="{esc(f["endpoint"])}" data-mailto="{EMAIL}"'
    fields = (f'<label>First name<input type="text" name="{esc(fl["first_name"])}" required autocomplete="given-name"></label>'
              f'<label>Last name<input type="text" name="{esc(fl["last_name"])}" required autocomplete="family-name"></label>'
              f'<label class="wide">Email<input type="email" name="{esc(fl["email"])}" required autocomplete="email"></label>'
              f'<label class="wide">Postal code or city<input type="text" name="{esc(fl["postal"])}" required autocomplete="postal-code" title="Used to invite you to events near you"></label>')
    if variant == "inline":
        return (f'<form class="signup inline" {common}><div class="fields">{fields}<button class="btn primary" type="submit">Sign up</button></div>'
                f'{consent}{hp}{hidden}<p class="form-msg" hidden></p></form>')
    return (f'<form class="signup full" {common}><div class="fields">{fields}</div>{consent}{hp}{hidden}'
            f'<div class="actions" style="margin-top:.25rem"><button class="btn primary" type="submit">Sign up</button></div><p class="form-msg" hidden></p></form>')


def signup_section(section_id="signup", dark=False):
    s = SITE["signup"]
    cls = "signup band dark" if dark else "signup"
    return (f'<section class="{cls}" id="{section_id}"><div class="wrap signup-grid"><div><h2>{esc(s["title"])}</h2><p>{esc(s["text"])}</p></div>'
            f'{signup_form("inline")}</div></section>')


def x_feed_html():
    x = SITE.get("x_feed", {})
    if not x.get("enabled"):
        return ""
    h = esc(x.get("handle", SITE["x_handle"]))
    return f"""<section class="section tight"><div class="wrap">
  <div class="section-head row"><h2 class="title-ui">Latest posts from @{h}</h2><a class="more" href="https://x.com/{h}" target="_blank" rel="noopener">Follow on X &rarr;</a></div>
  <div class="embed-box">
    <a class="twitter-timeline" data-height="{int(x.get('height', 700))}" data-dnt="true" data-chrome="noheader nofooter noborders" href="https://twitter.com/{h}?ref_src=twsrc%5Etfw">Posts by @{h}</a>
    <p class="placeholder">If the feed doesn't load here, open <a href="https://x.com/{h}" target="_blank" rel="noopener">x.com/{h}</a>.</p>
  </div>
  <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
</div></section>"""


def cta_actions(subject="Hello"):
    out = f'<a class="btn primary" href="mailto:{EMAIL}?subject={esc(subject)}">Email me</a>'
    if SITE.get("booking_url"):
        out += f'<a class="btn secondary" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">Book a call</a>'
    return f'<div class="actions">{out}</div>'


def contact_band():
    c = SITE["contact"]
    return f"""<section class="section band dark contact-band">{DECAL_ARC}<div class="wrap two-col">
  <div><h2>{esc(c['headline'])}</h2><p class="lede">{esc(c['text'])}</p></div>
  <div class="actions" style="margin:0;align-self:center"><a class="btn primary" href="mailto:{EMAIL}">{EMAIL}</a><a class="btn secondary" href="{u('/contact/')}">Contact page</a></div>
</div></section>"""


def record_rows(items):
    rows = ""
    for it in items:
        rows += (f'<li><div class="record-row"><div class="when">{esc(it.get("dates", ""))}</div><div>'
                 f'<p class="role">{esc(it.get("role", ""))}</p><h3><a href="{u(it["url"])}">{esc(it["title"])}</a></h3>'
                 f'<p>{esc(it.get("summary", ""))}</p><a class="more" href="{u(it["url"])}">Read more &rarr;</a></div></div></li>')
    return f'<ol class="record">{rows}</ol>'


def authored_items(posts, media):
    """One collection of Eric's written work, classified by authorship, sorted by publication date.
    Local posts that are companions to an external canonical piece are linked from that piece, not listed twice."""
    items = []
    for p in posts:
        if p.get("canonical_external"):
            continue
        items.append({"title": p["title"], "d": p["date"], "url": u(p["url"]), "external": False, "source": "This site",
                      "summary": p["summary"], "cat": cat_link(p), "action": "Read the essay", "featured": p.get("featured", False), "companion": None})
    for m in media:
        if m.get("kind") != "column":
            continue
        comp = None
        if m.get("companion"):
            comp = (m.get("companion_label", "Companion note on this site"), u(m["companion"]))
        items.append({"title": m["title"], "d": m["d"], "url": m["url"], "external": True, "source": m["outlet"],
                      "summary": m.get("summary", ""), "cat": "", "action": f"Read at {m['outlet']}", "featured": False, "companion": comp,
                      "verify": m.get("verify", "")})
    items.sort(key=lambda x: x["d"], reverse=True)
    return items


def article_entry(a, compact=False):
    """One card family for local and external authored work. Source is metadata, not a different category."""
    cls = "entry compact" if compact else "entry with-meta"
    ext = ' target="_blank" rel="noopener"' if a["external"] else ""
    src = a["cat"] if a["cat"] else f'<span class="cat">{esc(a["source"])}</span>'
    meta = f'<div class="meta">{src}<span>{fmt_date(a["d"])}</span></div>'
    summ = f'<p>{esc(a["summary"])}</p>' if a.get("summary") else ""
    comp = f' <a class="more" href="{a["companion"][1]}">{esc(a["companion"][0])} &rarr;</a>' if a.get("companion") else ""
    body = f'<div><h3 class="title-editorial"><a href="{esc(a["url"])}"{ext}>{esc(a["title"])}</a></h3>{summ}<a class="more" href="{esc(a["url"])}"{ext}>{esc(a["action"])}{" &#8599;" if a["external"] else " &rarr;"}</a>{comp}</div>'
    return f'<li data-filter-item="writing" data-values="{"external" if a["external"] else "local"}"><article class="{cls}">{meta}{body}</article></li>'


def feature_article(a):
    ext = ' target="_blank" rel="noopener"' if a["external"] else ""
    src = a["cat"] if a["cat"] else f'<span class="cat">{esc(a["source"])}</span>'
    summ = f'<p class="summary">{esc(a["summary"])}</p>' if a.get("summary") else ""
    comp = f'<a class="more" href="{a["companion"][1]}" style="margin-left:1rem">{esc(a["companion"][0])} &rarr;</a>' if a.get("companion") else ""
    return (f'<article class="feature-post"><div class="meta">{src}<span>{fmt_date(a["d"])}</span></div>'
            f'<h3 class="title-feature"><a href="{esc(a["url"])}"{ext}>{esc(a["title"])}</a></h3>{summ}'
            f'<div class="actions" style="margin-top:0"><a class="btn secondary small" href="{esc(a["url"])}"{ext}>{esc(a["action"])}{" &#8599;" if a["external"] else ""}</a>{comp}</div></article>')


def band_areas(label_text, areas, cols=None):
    """Reusable dark band: label + equal areas (symbol or short rule, Canela heading, text, action) on shared rows."""
    n = cols or len(areas)
    out = ""
    for a in areas:
        sym = SYMBOLS.get(a["symbol"]) if a.get("symbol") else '<span class="symbol rule-only" aria-hidden="true"></span>'
        tag = "a" if a.get("href") else "div"
        href = f' href="{u(a["href"])}"' if a.get("href") else ""
        action = f'<span class="more">{esc(a["cta"])} &rarr;</span>' if a.get("cta") else "<span></span>"
        out += f'<{tag} class="area"{href}>{sym}<h2>{esc(a["title"])}</h2><p>{esc(a["text"])}</p>{action}</{tag}>'
    return f'<section class="band dark band-areas"><div class="wrap">{label(esc(label_text))}<div class="area-grid cols-{n}">{out}</div></div></section>'


# --------------------------------------------------------------------------- pages
def build_home(posts, media, events, policy_items):
    hero = SITE["hero"]
    headline = hero["headline"]
    if " " in headline:   # "A future / worth building." on wide screens; natural wrapping elsewhere
        first, rest = headline.split(" ", 2)[0], headline.split(" ", 1)[1]
        if headline.startswith("A future "):
            first, rest = "A future", headline[len("A future "):]
        headline = f'{esc(first)} <span class="brk">{esc(rest)}</span>'
    record = "".join(f"<span>{esc(r)}</span>" for r in hero.get("record", []))
    work = band_areas("What I do", SITE["pillars"], cols=3)
    authored = authored_items(posts, media)
    featured = next((a for a in authored if a.get("featured")), authored[0] if authored else None)
    others = [a for a in authored if a is not featured][:2]
    writing = ""
    if featured:
        writing = f'<div class="feature-grid">{feature_article(featured)}<div class="secondary"><ul class="rule-list">{"".join(article_entry(a, compact=True) for a in others)}</ul></div></div>'
    recent_media = [m for m in media if m["kind"] in ("interview", "coverage")][:6]
    half = (len(recent_media) + 1) // 2
    media_cols = (f'<div class="list-cols"><ul class="list compact">{"".join(media_row(m, "home") for m in recent_media[:half])}</ul>'
                  f'<ul class="list compact">{"".join(media_row(m, "home") for m in recent_media[half:])}</ul></div>')
    upcoming = [e for e in events if not e["past"]][:3]
    events_html = ""
    if upcoming:
        events_html = f"""<section class="section tight"><div class="wrap">
  <div class="section-head row"><h2>Upcoming events</h2><a class="more" href="{u('/events/')}">All events &rarr;</a></div>
  {''.join(event_block(e) for e in upcoming)}
</div></section>"""
    body = f"""<section class="hero"><div class="hero-shell">
  <div class="hero-copy">
    {label(esc(hero['kicker']))}
    <h1 class="display">{headline}</h1>
    <p class="lede">{esc(hero['lede'])}</p>
    <div class="actions"><a class="btn primary" href="{u('/consulting/')}">Work with me</a><a class="btn secondary" href="{u('/writing/')}">Read my writing</a></div>
    <p class="record-line">{record}</p>
  </div>
  <figure class="hero-photo"><img src="{u('/assets/img/eric-hero.jpg')}" alt="{esc(NAME)}" width="1600" height="900" fetchpriority="high">{DECAL_PORTAL}</figure>
</div></section>

{signup_section()}

{work}

<section class="section"><div class="wrap">
  <div class="section-head row"><h2>Latest writing</h2><a class="more" href="{u('/writing/')}">All writing &rarr;</a></div>
  {writing}
</div></section>

<section class="section tight"><div class="wrap">
  <div class="section-head row"><h2 class="title-editorial">In the media</h2><a class="more" href="{u('/media/')}">Interviews and coverage &rarr;</a></div>
  {media_cols}
</div></section>

<section class="section"><div class="wrap">
  <div class="section-head row"><h2>Public policy</h2><a class="more" href="{u('/policy/')}">The civic work &rarr;</a></div>
  {record_rows(policy_items)}
</div></section>

{events_html}

<section class="section tight"><div class="wrap feature">
  <div><h2 class="title-editorial">Support the work</h2><p>Contributions fund events, travel and the community around the public policy work. None of it is personal income, and the support page says how it is used.</p><div class="actions"><a class="btn secondary" href="{u('/support/')}">How support works</a></div></div>
  <img src="{u('/assets/img/topic-democracy.jpg')}" alt="" loading="lazy" width="1600" height="1000">
</div></section>

{contact_band()}"""
    render(f"{NAME}: strategy consultant, writer and advocate", SITE["description"], body, path="/", current="/", lastmod=TODAY)


def build_consulting():
    c = load_json("consulting.json")
    intro = "".join(f"<p>{inline(p)}</p>" for p in c["intro"])

    services = band_areas("Services", [{"symbol": sv.get("symbol"), "title": sv["title"], "text": sv["summary"],
                                        "href": f"/consulting/#{sv['example']['anchor']}" if sv.get("example") else None,
                                        "cta": f"Example: {sv['example']['label']}" if sv.get("example") else None} for sv in c["services"]], cols=4)
    steps = "".join(f'<div><div class="num">{i}</div><h3>{esc(st["title"])}</h3><p>{esc(st["text"])}</p></div>'
                    for i, st in enumerate(c["how"]["steps"], start=1))
    partner = c["partner"]
    ptext = "".join(f"<p>{inline(p)}</p>" for p in partner["text"])
    pserv = "".join(f'<span class="tag">{esc(s)}</span>' for s in partner["services"])
    work = "".join(f'<article class="work-item-project" id="{esc(w.get("id", slugify(w["client"])))}"><div class="meta"><span>{esc(w["dates"])}</span><span>&middot;</span><span>{esc(w["role"])}</span></div><h3>{esc(w["client"])}</h3><p>{esc(w["text"])}</p></article>'
                   for w in c["work"])
    sectors = "".join(f'<span class="tag">{esc(s)}</span>' for s in c["sectors"])
    body = f"""{page_hero(c['kicker'], esc(c['headline']), esc(c['lede']), cta_actions('Consulting enquiry'), image='/assets/img/eric-consulting.jpg', alt=NAME)}
<section class="section tight"><div class="wrap"><div class="prose">{intro}</div></div></section>
{services}
<section class="section tight"><div class="wrap">{label("Sectors")}<div class="tags">{sectors}</div></div></section>
<section class="section"><div class="wrap">
  <div class="section-head">{label("How I work", rule=True)}<h2>{esc(c['how']['headline'])}</h2><p class="lede">{esc(c['how']['text'])}</p></div>
  <div class="cols cols-3 divided">{steps}</div>
</div></section>
<section class="section tight" id="electric-mind"><div class="wrap two-col">
  <div>{label("Partners")}<h2 class="title-editorial">{esc(partner['headline'])}</h2>{ptext}<p><a class="more" href="{esc(partner['url'])}" target="_blank" rel="noopener">Visit {esc(partner['name'])} &#8599;</a></p></div>
  <div>{label("What the partnership brings")}<div class="tags">{pserv}</div></div>
</div></section>
<section class="section" id="projects"><div class="wrap">
  <div class="section-head">{label(esc(c.get('work_title', 'Selected projects')), rule=True)}<h2>Selected projects.</h2><p class="muted">Client names are shared where I'm able to. Others are described by type.</p></div>
  <div class="cols cols-2">{work}</div>
</div></section>
<section class="section band dark"><div class="wrap two-col">
  <div><h2>{esc(c['cta']['headline'])}</h2><p class="lede">{esc(c['cta']['text'])}</p></div>
  <div class="actions" style="margin:0;align-self:center"><a class="btn primary" href="mailto:{EMAIL}?subject=Consulting%20enquiry">{EMAIL}</a>{f'<a class="btn secondary" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">Book a call</a>' if SITE.get('booking_url') else ''}</div>
</div></section>"""
    desc = "Eric Lombardi advises companies and investors in financial services and technology on strategy, acquisitions, product development and technology delivery, independently and with partner firms like Electric Mind."
    ld = [{"@type": "ProfessionalService", "@id": DOMAIN + "/consulting/#service", "name": f"{NAME} Consulting", "url": absu("/consulting/"),
           "provider": {"@id": PERSON_ID}, "areaServed": ["Canada", "United States"], "description": desc,
           "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Services", "itemListElement": [
               {"@type": "Offer", "itemOffered": {"@type": "Service", "name": s["title"], "description": s["summary"]}} for s in c["services"]]}}]
    render(T("Consulting in financial services and technology"), desc, body, path="/consulting/", current="/consulting/", image="/assets/img/eric-consulting.jpg", jsonld=ld)


def build_writing(posts, media):
    authored = authored_items(posts, media)
    chips = ('<div class="chips" data-filter-group="writing"><button class="chip" data-value="all" aria-pressed="true">All</button>'
             '<button class="chip" data-value="local" aria-pressed="false">On this site</button>'
             '<button class="chip" data-value="external" aria-pressed="false">Elsewhere</button></div>')
    entries = '<ul class="rule-list">' + "".join(article_entry(a) for a in authored) + "</ul>"
    about_me = [m for m in media if m["kind"] in ("interview", "coverage")][:6]
    media_sub = ('<ul class="list compact">' + "".join(media_row(m, "writing-media") for m in about_me) + "</ul>")
    lede = "Essays, columns and notes on politics, prosperity and technology, with a focus on Ontario. Everything I have written is here in one list, whether it was published on this site, in The Hub, in the Toronto Star or elsewhere."
    actions = f'<div class="actions"><a class="btn secondary small" href="{u("/feed.xml")}">RSS feed</a><a class="btn secondary small" href="#signup">New writing by email</a></div>'
    body = f"""{page_hero('Writing', 'Writing on politics, prosperity and technology.', lede, actions)}
<section class="section tight"><div class="wrap">{chips}{entries}</div></section>
<section class="section tight"><div class="wrap">
  <div class="section-head row"><div>{label("About the work")}<h2 class="title-editorial">In the media</h2></div><a class="more" href="{u('/media/')}">Interviews, coverage and media kit &rarr;</a></div>
  <div class="list-cols">{media_sub}</div>
</div></section>
{signup_section('signup', dark=True)}"""
    render(T("Writing"), "Essays and columns by Eric Lombardi on politics, prosperity and technology, published on this site, in The Hub, the Toronto Star and elsewhere.", body, path="/writing/", current="/writing/",
           jsonld=[{"@type": "Blog", "@id": DOMAIN + "/writing/#blog", "name": f"{NAME}: writing", "url": absu("/writing/"), "author": {"@id": PERSON_ID},
                    "blogPost": [{"@type": "BlogPosting", "headline": a["title"], "url": a["url"] if a["external"] else absu(a["url"].replace(BASE, "", 1)), "datePublished": a["d"].isoformat(),
                                  **({"publisher": {"@type": "Organization", "name": a["source"]}} if a["external"] else {})} for a in authored[:30]]}],
           lastmod=authored[0]["d"] if authored else TODAY)
    cats_used = [cat for cat in SITE["categories"] if any(p["category"] == cat for p in posts)]
    for cat in cats_used:
        sub = [p for p in posts if p["category"] == cat]
        lab = SITE["categories"][cat]
        body = f"""{page_hero('Writing', esc(lab), f'{len(sub)} post{"s" if len(sub) != 1 else ""} on this site in this category. <a href="{u("/writing/")}">All writing</a>.')}
<section class="section tight"><div class="wrap"><ul class="rule-list">{''.join(post_entry(p) for p in sub)}</ul></div></section>"""
        render(T(f"{lab}: writing"), f"Posts by {NAME} on {lab.lower()}.", body, path=f"/writing/category/{cat}/", current="/writing/", lastmod=sub[0]["date"])
    for i, p in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        pager = '<nav class="pager" aria-label="More posts">'
        pager += f'<a href="{u(older["url"])}"><span class="lbl">Older</span>{esc(older["title"])}</a>' if older else "<span></span>"
        pager += f'<a class="next" href="{u(newer["url"])}"><span class="lbl">Newer</span>{esc(newer["title"])}</a>' if newer else ""
        pager += "</nav>"
        notice = ""
        if p["origin"] == "campaign":
            notice = f'<div class="notice"><p>Originally published on ericforolp.ca during the <a href="{u("/policy/ontario-liberal-leadership-2026/")}">2026 Ontario Liberal leadership campaign</a>. Some links and asks are of their time.</p></div>'
        if p.get("canonical_external"):
            notice += f'<div class="notice"><p>This is a companion note to a piece published elsewhere: <a href="{esc(p["canonical_external"])}" target="_blank" rel="noopener">read the original &#8599;</a>.</p></div>'
        hero_img = f'<img class="ratio-16x9" src="{u(p["image"])}" alt="" style="max-width:54rem;margin-bottom:2rem" width="1600" height="900">' if p.get("image") else ""
        share_url = absu(p["url"])
        share = (f'<div class="share"><span class="muted">Share</span>'
                 f'<a href="https://x.com/intent/post?text={esc(p["title"])}&url={share_url}" target="_blank" rel="noopener">X</a>'
                 f'<a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener">LinkedIn</a>'
                 f'<a href="https://bsky.app/intent/compose?text={esc(p["title"])}%20{share_url}" target="_blank" rel="noopener">Bluesky</a>'
                 f'<a href="mailto:?subject={esc(p["title"])}&body={share_url}">Email</a></div>')
        more = [a for a in authored if a["url"] != u(p["url"])][:3]
        related = ('<section class="section tight"><div class="wrap"><div class="section-head row"><h2 class="title-editorial">More writing</h2><a class="more" href="' + u("/writing/") + '">All writing &rarr;</a></div><ul class="rule-list">' + "".join(article_entry(a, compact=True) for a in more) + "</ul></div></section>") if more else ""
        body = f"""<section class="wrap"><header class="article-head">
  {label(cat_link(p), rule=True)}
  <h1>{esc(p['title'])}</h1>
  <p class="article-meta"><span>By <a href="{u('/about/')}">{esc(NAME)}</a></span><span>&middot;</span><span>{fmt_date(p['date'])}</span><span>&middot;</span><span>{reading_time(p['html'])} min read</span></p>
</header>
{hero_img}{notice}
<article class="prose">{p['html']}</article>
{share}{pager}</section>
{related}
{signup_section('signup', dark=True)}"""
        ld = [{"@type": "BlogPosting", "@id": absu(p["url"]) + "#article", "headline": p["title"], "description": p["summary"], "url": absu(p["url"]),
               "datePublished": p["date"].isoformat(), "dateModified": (p["updated"] or p["date"]).isoformat(),
               "author": {"@id": PERSON_ID}, "publisher": {"@id": PERSON_ID}, "mainEntityOfPage": absu(p["url"]),
               "image": absu(p["image"]) if p.get("image") else absu(SITE["og_image"]), "articleSection": p["category_label"],
               "keywords": ", ".join(p["tags"]), "wordCount": p["words"], "inLanguage": "en-CA", "isPartOf": {"@id": DOMAIN + "/writing/#blog"}}]
        render(T(p["title"]), p["summary"] or strip_tags(p["html"])[:155], body, path=p["url"], current="/writing/", image=p.get("image") or None,
               kind="article", jsonld=ld, lastmod=p["updated"] or p["date"], reading=True)


def build_media(media):
    interviews = [m for m in media if m["kind"] == "interview"]
    coverage = [m for m in media if m["kind"] == "coverage" and not m.get("campaign")]
    formats = sorted({m.get("format", "") for m in interviews if m.get("format")})
    chips = '<div class="chips" data-filter-group="media"><button class="chip" data-value="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" data-value="{esc(f)}" aria-pressed="false">{esc(f.title())}</button>' for f in formats) + "</div>"
    lede = f"Interviews, profiles and coverage about the work. My own columns and essays are in <a href=\"{u('/writing/')}\">Writing</a>, and coverage of the 2026 leadership campaign is archived <a href=\"{u('/policy/ontario-liberal-leadership-2026/#coverage')}\">on the campaign page</a>."
    actions = f'<div class="actions"><a class="btn primary small" href="mailto:{EMAIL}?subject=Media%20request">Media and speaking requests</a><a class="btn secondary small" href="#media-kit">Media kit</a></div>'
    news = ""
    if coverage:
        news = f"""<section class="section tight"><div class="wrap"><div class="section-head"><h2 class="title-editorial">Coverage of the work</h2></div>{media_by_year(coverage, 'news', limit=6, wide=True)}</div></section>"""
    body = f"""{page_hero('In the media', 'Interviews, coverage and appearances.', lede, actions)}
<section class="section tight"><div class="wrap">
  <div class="section-head">{label("Interviews and appearances", rule=True)}<h2 class="title-editorial">Podcasts, broadcast and print</h2></div>
  {chips}
  {media_by_year(interviews, 'media', limit=10, wide=True)}
</div></section>
<section class="section band limestone" id="media-kit"><div class="wrap">
  <div class="section-head">{label("Media kit")}<h2 class="title-editorial">For producers, editors and organizers.</h2></div>
  <div class="cols cols-3 divided">
    <div><h3>Short bio</h3><p>{esc(SITE['description'])}</p></div>
    <div><h3>Headshot</h3><p>Square, 800 &times; 800, suitable for print and web.</p><div class="actions"><a class="btn secondary small" href="{u('/assets/img/eric-headshot.jpg')}" download>Download JPG</a></div></div>
    <div><h3>Requests</h3><p>For interviews, comment, columns and speaking invitations, email a few details about what you have in mind.</p><div class="actions"><a class="btn primary small" href="mailto:{EMAIL}?subject=Media%20request">{EMAIL}</a></div></div>
  </div>
</div></section>
{news}"""
    render(T("In the media: interviews and coverage"), f"Interviews, profiles and coverage of {NAME}'s work on podcasts, radio, television and in print.", body, path="/media/", current="/writing/",
           lastmod=media[0]["d"] if media else TODAY)


def build_policy(policy, media):
    idx_meta, idx_html, items = policy
    # priorities: the existing "What I argue for" list, rendered as the band component
    pri = [{"title": re.sub(r"\.$", "", strip_tags(m.group(1))), "text": strip_tags(m.group(2)).strip()} for m in re.finditer(r"<li><strong>(.*?)</strong>(.*?)</li>", idx_html, re.S)]
    band = band_areas("What I argue for", pri, cols=len(pri)) if pri else ""
    rest_html = re.sub(r"<h2>What I argue for</h2>\s*<ul>.*?</ul>", "", idx_html, flags=re.S).strip()
    panel = f'<div class="panel accent">{label("The platform")}<h3 class="title-pillar">Ontario Can Still Win</h3><p>The fully costed 2026 platform: thirteen policy areas, more than 190 commitments, reconciled to the provincial budget baseline. It remains online chapter by chapter, with the full PDF, and others are welcome to borrow from it.</p><div class="actions"><a class="btn primary small" href="{esc(SITE["platform_url"])}" target="_blank" rel="noopener">Read the platform &#8599;</a><a class="btn secondary small" href="{u("/policy/ontario-liberal-leadership-2026/")}">About the campaign</a></div></div>'
    platform_block = (f'<section class="section tight"><div class="wrap two-col"><div class="prose">{rest_html}</div><aside>{panel}</aside></div></section>' if rest_html
                      else f'<section class="section tight"><div class="wrap">{panel}</div></section>')
    body = f"""{page_hero(idx_meta.get('kicker', 'Public policy'), esc(idx_meta.get('headline', 'Public policy')), esc(idx_meta.get('lede', '')))}
{band}
<section class="section"><div class="wrap"><div class="section-head row"><h2>The record</h2></div>{record_rows(items)}</div></section>
{platform_block}
{x_feed_html()}"""
    render(T("Public policy and civic work"), f"{NAME}'s public policy work: More Neighbours Toronto, Build Toronto and the 2026 Ontario Liberal leadership campaign and platform.", body, path="/policy/", current="/policy/")
    campaign_items = [m for m in media if m.get("campaign")]
    for it in items:
        links = "".join(f'<a class="btn {"primary" if l["primary"] else "secondary"}" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} &#8599;</a>' for l in it["links"])
        facts = "".join(f'<div><dt>{k}</dt><dd>{esc(it[key])}</dd></div>' for k, key in (("Role", "role"), ("When", "dates")) if it.get(key))
        gallery = f'<div class="gallery" style="margin-top:2rem">{"".join(f"<img src=\"{u(g)}\" alt=\"\" loading=\"lazy\">" for g in it["gallery"])}</div>' if it["gallery"] else ""
        coverage = ""
        if truthy(it.get("coverage", "")) and campaign_items:
            coverage = f"""<section class="section" id="coverage"><div class="wrap">
  <div class="section-head">{label("Archive", rule=True)}<h2 class="title-editorial">Campaign coverage, columns and interviews</h2><p class="muted">{len(campaign_items)} items from the 2026 leadership campaign, kept separate from my other <a href="{u('/media/')}">media</a> and <a href="{u('/writing/')}">writing</a>.</p></div>
  <div class="chips" data-filter-group="coverage"><button class="chip" data-value="all" aria-pressed="true">All</button><button class="chip" data-value="column" aria-pressed="false">Columns by Eric</button><button class="chip" data-value="interview" aria-pressed="false">Interviews</button><button class="chip" data-value="coverage" aria-pressed="false">Coverage</button></div>
  {media_by_year(campaign_items, 'coverage', limit=12, wide=True)}
</div></section>"""
        feature = ""
        if it.get("feature_title"):
            feature = f"""<section class="section band limestone"><div class="wrap feature"><img src="{u(it.get('feature_image', it.get('image')))}" alt="" loading="lazy" width="1600" height="1000"><div>{label(esc(it.get('feature_kicker', '')))}<h2 class="title-editorial">{esc(it['feature_title'])}</h2><p>{esc(it.get('feature_text', ''))}</p><div class="actions"><a class="btn primary" href="{esc(it.get('feature_url', '#'))}" target="_blank" rel="noopener">{esc(it.get('feature_cta', 'Open'))} &#8599;</a></div></div></div></section>"""
        body = f"""{page_hero('Public policy', esc(it['title']), esc(it.get('summary', '')), f'<div class="actions">{links}</div>' if links else '', image=it.get('image'), alt=it['title'])}
<section class="section tight"><div class="wrap"><dl class="facts">{facts}</dl><div class="prose">{it['html']}</div>{gallery}</div></section>
{feature}{coverage}"""
        ld = []
        if it["slug"] != "ontario-liberal-leadership-2026" and it["links"]:
            ld.append({"@type": "Organization", "name": it["title"], "url": it["links"][0]["url"], "founder": {"@id": PERSON_ID}})
        render(T(it["title"]), it.get("summary", ""), body, path=it["url"], current="/policy/", image=it.get("card_image") or it.get("image"), jsonld=ld, reading=True)


def build_events(events):
    upcoming = [e for e in events if not e["past"]]
    past = list(reversed([e for e in events if e["past"]]))
    up_html = "".join(event_block(e) for e in upcoming) if upcoming else '<div class="empty">No events are scheduled at the moment. New dates are added here as they are confirmed, and sign-ups hear first.</div>'
    past_html = ""
    if past:
        past_html = f'<details class="past" style="margin-top:2.5rem"><summary>Where I have been ({len(past)})</summary>{"".join(event_block(e) for e in past)}</details>'
    ics = absu("/events.ics")
    webcal = ics.replace("https://", "webcal://").replace("http://", "webcal://")
    body = f"""{page_hero('Events', "Where I'll be.", "Talks, panels, meetups and the occasional debate. Dates are added as they're confirmed, and third-party registration links open on the organizer's site.")}
<section class="section tight"><div class="wrap two-col">
  <div>
    <div class="section-head">{label("Upcoming", rule=True)}<h2 class="title-editorial">Coming up</h2></div>
    {up_html}
    {past_html}
  </div>
  <aside class="stack">
    <div class="panel quiet">{label("Calendar")}<h3>Subscribe to the calendar</h3><p class="small">New events appear in your calendar automatically.</p><div class="actions"><a class="btn primary small" href="{webcal}">Add to calendar</a><button class="btn secondary small" type="button" data-copy="{ics}">Copy feed URL</button></div><p class="fine" style="margin-top:.75rem">Or <a href="{u('/events.ics')}">download the .ics file</a>.</p></div>
    <div class="panel quiet">{label("Invitations")}<h3>Invite me to speak</h3><p class="small">I speak on Ontario's economy, housing, infrastructure delivery, public services, and strategy in financial services and technology. Email a date, a place and an audience.</p><div class="actions"><a class="btn secondary small" href="mailto:{EMAIL}?subject=Speaking%20invitation">Email an invitation</a></div></div>
    <div class="panel quiet">{label("Updates")}<h3>Hear about events near you</h3><p class="small">Your postal code or city lets me tell you about the ones nearby.</p><div class="actions"><a class="btn secondary small" href="{u('/support/#signup')}">Sign up</a></div></div>
  </aside>
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
    render(T("Events: where I'll be"), f"Upcoming talks, panels and meetups with {NAME}, with a calendar feed you can subscribe to.", body, path="/events/", current="/events/", jsonld=ld)
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
    if live:
        monthly = f'<a class="btn primary" href="{esc(sup["contribute_url"])}" target="_blank" rel="noopener">Contribute monthly &#8599;</a>'
        once = f'<a class="btn secondary" href="{esc(sup["one_time_url"])}" target="_blank" rel="noopener">Give once &#8599;</a>' if sup.get("one_time_url") else ""
    else:
        monthly = '<a class="btn primary" href="#" aria-disabled="true">Contribute monthly</a>'
        once = '<a class="btn secondary" href="#" aria-disabled="true">Give once</a><span class="note-inline">Payments are not open yet</span>'
    hero_actions = '<div class="actions"><a class="btn primary" href="#contribute">Contribute</a><a class="btn secondary" href="#signup">Sign up for updates</a></div>'
    pledge = "".join(f"<p>{inline(p)}</p>" for p in s["pledge"]["paragraphs"])
    uses = "".join(f'<div><h3>{esc(x["title"])}</h3><p>{esc(x["text"])}</p></div>' for x in s["uses"])
    faq = "".join(f'<details class="faq"><summary>{esc(q["q"])}</summary><p>{esc(q["a"])}</p></details>' for q in s["faq"])
    c = s["contribute"]
    note = esc(c["note"]).replace("a third-party platform", platform)
    sg = SITE["signup"]
    body = f"""{page_hero(s['kicker'], esc(s['headline']), esc(s['lede']), hero_actions)}
<section class="section tight" id="contribute"><div class="wrap two-col">
  <div class="panel quiet">{label("The pledge")}<h2>{esc(s['pledge']['title'])}</h2>{pledge}</div>
  <div class="panel accent">{label("Contribute")}<h2>{esc(c['title'])}</h2><p>{esc(c['text'])}</p><div class="actions">{monthly}{once}</div><p class="fine" style="margin-top:1rem">{note}</p></div>
</div></section>
<section class="section band limestone"><div class="wrap"><div class="section-head">{label("Where it goes", rule=True)}<h2 class="title-editorial">What contributions pay for.</h2></div><div class="cols cols-4 divided">{uses}</div></div></section>
<section class="section" id="signup"><div class="wrap two-col">
  <div><h2 class="title-editorial">{esc(sg['title'])}</h2><p class="lede">{esc(sg['text'])}</p><p class="small">Prefer a feed? Writing is on <a href="{u('/feed.xml')}">RSS</a>, and events on a <a href="{u('/events.ics')}">calendar feed</a>.</p></div>
  <div>{signup_form('full')}</div>
</div></section>
<section class="section tight"><div class="wrap"><div class="section-head">{label("Questions")}<h2 class="title-editorial">The fine print, in plain words.</h2></div>{faq}</div></section>"""
    render(T("Support the work"), "Support Eric Lombardi's public policy and advocacy work: sign up for updates, or contribute what you want to fund community, events, research and travel across Ontario. None of it is personal income.", body, path="/support/", current="/support/")
    for old, anchor in (("subscribe", ""), ("signup", "#signup")):
        write(f"{old}/index.html", f"""<!DOCTYPE html><html lang="en-CA"><head><meta charset="utf-8"><title>Support | {esc(NAME)}</title>
<meta http-equiv="refresh" content="0; url={u('/support/')}{anchor}"><link rel="canonical" href="{absu('/support/')}"><meta name="robots" content="noindex"></head>
<body><p>This has moved to <a href="{u('/support/')}{anchor}">the support page</a>.</p></body></html>
""")


def build_about():
    meta, md = read_md(CONTENT / "pages" / "about.md")
    facts = """<dl class="facts"><div><dt>Based in</dt><dd>Toronto, Ontario</dd></div><div><dt>Education</dt><dd>BASc, Nanotechnology Engineering, University of Waterloo</dd></div><div><dt>Work</dt><dd>Consultant, financial services and technology</dd></div><div><dt>Civic</dt><dd>Founder and former president, More Neighbours Toronto (2021 to 2026). Former chair, Build Toronto (2025 to 2026). Ontario Liberal leadership candidate, 2026.</dd></div></dl>"""
    body = f"""{page_hero('About', esc(meta.get('headline', 'About')), esc(meta.get('lede', '')), cta_actions(), image=meta.get('image'), alt=NAME)}
<section class="section tight"><div class="wrap">{facts}<div class="prose">{md_to_html(md)}</div>
<p style="margin-top:2rem"><a class="more" href="{u('/assets/img/eric-headshot.jpg')}" download>Download headshot &darr;</a> &nbsp; <a class="more" href="{u('/media/#media-kit')}">Media kit &rarr;</a></p></div></section>"""
    render(T("About Eric"), SITE["description"], body, path="/about/", current="", image=meta.get("image"), kind="profile", reading=True)


def build_contact():
    c = SITE["contact"]
    socials = "".join(f'<li><a href="{esc(s["url"])}" rel="me noopener" target="_blank">{esc(s["name"])}{(" " + esc(s["handle"])) if s.get("handle") else ""}</a></li>' for s in SITE["socials"] if s.get("show", True))
    booking = f'<a class="btn secondary small" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">Book a call</a>' if SITE.get("booking_url") else ""
    addr = f'<p class="small muted" style="margin-top:.75rem">Mail: {esc(SITE["mailing_address"])}</p>' if SITE.get("mailing_address") else ""
    body = f"""{page_hero('Contact', esc(c['headline']), esc(c['text']), f'<div class="actions"><a class="btn primary" href="mailto:{EMAIL}">{EMAIL}</a>{booking}</div>')}
<section class="section tight"><div class="wrap cols cols-3 divided">
  <div>{label("Consulting")}<h3>Work with me</h3><p>A few details about the problem and the timing are enough to start.</p><div class="actions"><a class="btn primary small" href="mailto:{EMAIL}?subject=Consulting%20enquiry">Email about a project</a></div></div>
  <div>{label("Media and speaking")}<h3>Interviews, columns, events</h3><p>For interview requests, comment, or an invitation to speak. <a href="{u('/media/#media-kit')}">Media kit and headshot</a>.</p><div class="actions"><a class="btn secondary small" href="mailto:{EMAIL}?subject=Media%20request">Email a request</a></div></div>
  <div>{label("Follow")}<h3>Social</h3><ul class="social-list">{socials}</ul>{addr}<p class="small" style="margin-top:.75rem"><a href="{u('/support/#signup')}">Sign up for updates</a>.</p></div>
</div></section>"""
    render(T("Contact"), f"Contact {NAME} for consulting, media and speaking requests.", body, path="/contact/", current="/contact/")


def build_privacy():
    meta, md = read_md(CONTENT / "pages" / "privacy.md")
    upd = fmt_date(parse_date(meta["updated"])) if meta.get("updated") else fmt_date(TODAY)
    body = f"""{page_hero('Privacy', esc(meta.get('headline', 'Privacy policy')), esc(meta.get('lede', '')))}
<section class="section tight"><div class="wrap"><p class="fine">Last updated {upd}</p><div class="prose">{md_to_html(md)}</div></div></section>"""
    render(T("Privacy policy"), "How ericlombardi.ca collects and uses personal information, and how to unsubscribe.", body, path="/privacy/", current="", reading=True)


def build_404():
    body = f"""{page_hero('404', 'That page is not here.', 'It may have moved when the site was rebuilt. Try one of these instead.')}
<section class="section tight"><div class="wrap"><div class="actions" style="margin:0"><a class="btn primary" href="{u('/')}">Home</a><a class="btn secondary" href="{u('/writing/')}">Writing</a><a class="btn secondary" href="{u('/consulting/')}">Consulting</a><a class="btn secondary" href="{u('/policy/')}">Public policy</a></div></div></section>"""
    render(T("Page not found"), "Page not found.", body, path="/404.html", current="", sitemap=False)


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
             f"Email: {EMAIL}. Location: {SITE['location']['label']}. Socials: " + ", ".join(f"{s['name']} {s['url']}" for s in SITE["socials"] if s.get("show", True)), "",
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
    write("api/site.json", json.dumps({"name": NAME, "url": DOMAIN, "description": SITE["description"], "email": EMAIL, "location": SITE["location"]["label"],
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


def copy_assets():
    shutil.copytree(ASSETS, OUT / "assets", dirs_exist_ok=True)


# --------------------------------------------------------------------------- main
def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
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
    if not SITE["support"].get("live"):
        warn("support.live is false: contribution buttons are disabled")
    print(f"Built {len(SITEMAP)} pages + feeds into {OUT.relative_to(HERE)}/ (base='{BASE or '/'}')")
    for w in WARN:
        print("  warning:", w)


if __name__ == "__main__":
    main()
