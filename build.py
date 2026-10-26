#!/usr/bin/env python3
"""ericlombardi.ca — static site generator. Standard library only.

    python3 build.py                   # build docs/
    python3 build.py --base /repo --domain https://user.github.io/repo
                                       # test build for GitHub project pages (no CNAME written)
    python3 build.py --drafts          # include posts marked  draft: true
    python3 build.py --no-placeholders # drop events marked "placeholder": true

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
DROP_PLACEHOLDERS = "--no-placeholders" in ARGS


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
            "origin": meta.get("origin", ""), "canonical": meta.get("canonical", ""),
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
    evs = [e for e in load_json("events.json") if not (DROP_PLACEHOLDERS and e.get("placeholder"))]
    for e in evs:
        e["d"] = parse_date(e["date"])
        e["end_d"] = parse_date(e["end"]) if e.get("end") else None
        e["slug"] = slugify(f"{e['date']}-{e['title']}")
        e["past"] = (e["end_d"] or e["d"]) < TODAY
        if e.get("placeholder") and not e["past"]:
            warn(f"event '{e['title']}' is a placeholder and will be published (use --no-placeholders or delete it)")
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
def analytics_snippet():
    a = SITE.get("analytics", {})
    if not a.get("enabled"):
        return ""
    if a.get("provider") == "simpleanalytics":
        return ('<script async src="https://scripts.simpleanalyticscdn.com/latest.js"></script>\n'
                '<noscript><img src="https://queue.simpleanalyticscdn.com/noscript.gif" alt="" referrerpolicy="no-referrer-when-downgrade"></noscript>')
    return a.get("custom_snippet", "")


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
  <a class="btn small primary header-cta" href="{u('/support/')}">Support</a>
  <button class="burger" aria-label="Menu" aria-expanded="false" aria-controls="mobile-nav"><span></span><span></span><span></span></button>
</div>
<nav class="mobile" id="mobile-nav" aria-label="Mobile">{links}<a href="{u('/about/')}">About</a><a class="btn primary" href="{u('/support/')}">Support the work</a></nav>
</header>"""


def footer_html():
    socials = "".join(f'<a href="{esc(s["url"])}" rel="me noopener" target="_blank">{esc(s["name"])}</a>'
                      for s in SITE["socials"] if s.get("show", True))
    explore = nav_links() + f'<a href="{u("/about/")}">About</a>'
    return f"""<footer class="site-footer"><div class="wrap">
  <div class="footer-grid">
    <div><a class="wordmark" href="{u('/')}">{esc(NAME)}</a><p class="about">{esc(SITE['short_description'])}</p></div>
    <div><h4>Explore</h4><nav>{explore}</nav></div>
    <div><h4>Follow</h4><div class="links">{socials}<a href="{u('/feed.xml')}">RSS feed</a></div></div>
    <div><h4>Stay in touch</h4><div class="links"><a href="mailto:{EMAIL}">{EMAIL}</a><a href="{u('/support/#signup')}">Sign up for updates</a><a href="{u('/support/')}">Support the work</a><a href="{u('/events/')}">Where I'll be</a></div></div>
  </div>
  <p class="fine">&copy; {TODAY.year} {esc(NAME)}. {esc(SITE['location']['label'])}. <a href="{u('/privacy/')}">Privacy</a> &middot; <a href="{u('/llms.txt')}">llms.txt</a> &middot; <a href="{u('/sitemap.xml')}">Sitemap</a>. No cookies, no trackers.</p>
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


def post_entry(p):
    return (f'<li data-filter-item="posts" data-values="{p["category"]}"><article class="entry with-meta">'
            f'<div class="meta"><a class="cat" href="{u("/writing/category/" + p["category"] + "/")}">{esc(p["category_label"])}</a><span>{fmt_date(p["date"])}</span></div>'
            f'<div><h3><a href="{u(p["url"])}">{esc(p["title"])}</a></h3><p>{esc(p["summary"])}</p><a class="more" href="{u(p["url"])}">Read the essay &rarr;</a></div></article></li>')


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
    ph = ' <span class="tag">Placeholder</span>' if e.get("placeholder") else ""
    summ = f'<p>{esc(e["summary"])}</p>' if e.get("summary") else ""
    return (f'<article class="event{" past" if past else ""}"><div class="datebox"><span class="m">{d:%b}</span><span class="d">{d.day}</span><span class="y">{d.year}</span></div>'
            f'<div><div class="meta"><span class="cat">{esc(e.get("kind", "Event"))}</span>{ph}</div><h3>{esc(e["title"])}</h3>'
            f'<div class="where">{when}{(" &middot; " + where) if where else ""}</div>{summ}{link}</div></article>')


def signup_form(variant="full"):
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
    common = f'action="{action}" method="{esc(f.get("method", "POST"))}" data-endpoint="{esc(f["endpoint"])}" data-mailto="{EMAIL}" novalidate=""'
    if variant == "inline":
        fields = (f'<input type="text" name="{esc(fl["first_name"])}" placeholder="First name" aria-label="First name" required autocomplete="given-name">'
                  f'<input type="text" name="{esc(fl["last_name"])}" placeholder="Last name" aria-label="Last name" required autocomplete="family-name">'
                  f'<input type="email" name="{esc(fl["email"])}" placeholder="Email" aria-label="Email" required autocomplete="email">'
                  f'<input type="text" name="{esc(fl["postal"])}" placeholder="Postal code or city" aria-label="Postal code or city" required autocomplete="postal-code">'
                  f'<button class="btn primary" type="submit">Sign up</button>')
        return f'<form class="signup inline" {common}><div class="fields">{fields}</div>{consent}{hp}{hidden}<p class="form-msg" hidden></p></form>'
    fields = (f'<label>First name<input type="text" name="{esc(fl["first_name"])}" required autocomplete="given-name"></label>'
              f'<label>Last name<input type="text" name="{esc(fl["last_name"])}" required autocomplete="family-name"></label>'
              f'<label class="wide">Email<input type="email" name="{esc(fl["email"])}" required autocomplete="email" placeholder="you@example.com"></label>'
              f'<label class="wide">Postal code or city<input type="text" name="{esc(fl["postal"])}" required autocomplete="postal-code" placeholder="M5V 1A1" title="Used only to understand where readers are and to invite you to nearby events"></label>')
    return (f'<form class="signup full" {common}><div class="fields">{fields}</div>{consent}{hp}{hidden}'
            f'<div class="actions" style="margin-top:.25rem"><button class="btn primary" type="submit">Sign up</button></div><p class="form-msg" hidden></p></form>')


def signup_bar():
    s = SITE["signup"]
    return (f'<section class="signup-bar" id="signup"><div class="wrap"><div>{label("Free updates")}<h2>{esc(s["title"])}</h2><p>{esc(s["text"])}</p></div>'
            f'{signup_form("inline")}</div></section>')


def x_feed_html():
    x = SITE.get("x_feed", {})
    if not x.get("enabled"):
        return ""
    h = esc(x.get("handle", SITE["x_handle"]))
    return f"""<section class="section tight"><div class="wrap">
  <div class="section-head row"><div>{label("On X")}<h2>Latest posts from @{h}</h2></div><a class="more" href="https://x.com/{h}" target="_blank" rel="noopener">Follow on X &rarr;</a></div>
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
    return f"""<section class="section band dark"><div class="wrap two-col">
  <div>{label("Get in touch")}<h2>Have a problem worth thinking through?</h2><p class="lede">Email is best. A sentence or two is enough to start, and I reply within a couple of days.</p></div>
  <div class="actions" style="margin:0;align-self:center"><a class="btn primary" href="mailto:{EMAIL}">{EMAIL}</a><a class="btn secondary" href="{u('/contact/')}">Contact page</a></div>
</div></section>"""


def policy_entry(it):
    img = it.get("card_image") or it.get("image")
    return (f'<article class="entry with-image"><a href="{u(it["url"])}" tabindex="-1" aria-hidden="true"><img src="{u(img)}" alt="" loading="lazy" width="1600" height="1000"></a>'
            f'<div class="meta"><span>{esc(it.get("dates", ""))}</span></div><h3><a href="{u(it["url"])}">{esc(it.get("card_title") or it["title"])}</a></h3>'
            f'<p>{esc(it.get("summary", ""))}</p><a class="more" href="{u(it["url"])}">Read more &rarr;</a></article>')


# --------------------------------------------------------------------------- pages
def build_home(posts, media, events, policy_items):
    hero = SITE["hero"]
    pillars = "".join(f'<div><h3>{esc(p["title"])}</h3><p>{esc(p["text"])}</p><a class="more" href="{u(p["href"])}">{esc(p.get("cta", "Explore"))} &rarr;</a></div>' for p in SITE["pillars"])
    latest = '<ul class="rule-list">' + "".join(post_entry(p) for p in posts[:3]) + "</ul>"
    recent_media = [m for m in media if m["kind"] in ("column", "interview")][:5]
    media_list = '<ul class="list compact">' + "".join(media_row(m, "home") for m in recent_media) + "</ul>"
    upcoming = [e for e in events if not e["past"]][:3]
    events_html = ""
    if upcoming:
        events_html = f"""<section class="section"><div class="wrap">
  <div class="section-head row"><div>{label("Where I'll be", rule=True)}<h2>Upcoming events</h2></div><a class="more" href="{u('/events/')}">All events &rarr;</a></div>
  {''.join(event_block(e) for e in upcoming)}
</div></section>"""
    civic = "".join(policy_entry(it) for it in policy_items)
    body = f"""<section class="hero"><div class="wrap hero-grid">
  <div class="hero-copy">
    {label(esc(hero['kicker']), rule=True)}
    <h1>{hero['headline']}</h1>
    <p class="lede">{hero['lede']}</p>
    <div class="actions"><a class="btn primary" href="{u('/consulting/')}">Work with me</a><a class="btn secondary" href="{u('/writing/')}">Read the writing</a><a class="textlink" href="mailto:{EMAIL}">Get in touch</a></div>
    <p class="hero-note">{hero['note']} <a href="{u('/about/')}">More about me</a>.</p>
  </div>
  <figure class="hero-photo frame"><img src="{u('/assets/img/eric-hero.jpg')}" alt="{esc(NAME)}" width="1600" height="900" fetchpriority="high"></figure>
</div></section>

{signup_bar()}

<section class="section"><div class="wrap">
  <div class="section-head">{label("What I do", rule=True)}<h2>Three kinds of work, one way of thinking.</h2></div>
  <div class="cols cols-3 divided">{pillars}</div>
</div></section>

<section class="section tight"><div class="wrap two-col">
  <div>
    <div class="section-head row"><div>{label("Latest writing")}<h2>Notes and essays</h2></div><a class="more" href="{u('/writing/')}">All writing &rarr;</a></div>
    {latest}
  </div>
  <aside>
    <div class="section-head row"><div>{label("Recent media")}<h2>Columns and interviews</h2></div></div>
    {media_list}
    <p style="margin-top:1rem"><a class="more" href="{u('/media/')}">All media &rarr;</a></p>
  </aside>
</div></section>

<section class="section"><div class="wrap">
  <div class="section-head row"><div>{label("Public policy", rule=True)}<h2>The civic work</h2></div><a class="more" href="{u('/policy/')}">Public policy &rarr;</a></div>
  <div class="cols cols-3">{civic}</div>
</div></section>

{events_html}

<section class="section band limestone"><div class="wrap feature">
  <div>{label("Support the work")}<h2>Help build a community around these ideas.</h2><p>Contributions fund events, travel and the community around a growth agenda for Ontario. None of it is personal income, and the support page says exactly how it is used.</p><div class="actions"><a class="btn primary" href="{u('/support/')}">Support the work</a></div></div>
  <img src="{u('/assets/img/topic-democracy.jpg')}" alt="" loading="lazy" width="1600" height="1000">
</div></section>

{contact_band()}"""
    render(f"{NAME}: strategy consultant, writer and advocate", SITE["description"], body, path="/", current="/", lastmod=TODAY)


def build_consulting():
    c = load_json("consulting.json")
    intro = "".join(f"<p>{inline(p)}</p>" for p in c["intro"])
    services = ""
    for s in c["services"]:
        bullets = "".join(f"<li>{esc(b)}</li>" for b in s["bullets"])
        services += (f'<article><h3>{esc(s["title"])}</h3><p><strong>{esc(s["summary"])}</strong></p><ul class="small">{bullets}</ul>'
                     f'<p class="small muted"><strong>For example:</strong> {esc(s["proof"])}</p></article>')
    steps = "".join(f'<div><div class="num">{i}</div><h3>{esc(st["title"])}</h3><p>{esc(st["text"])}</p></div>'
                    for i, st in enumerate(c["how"]["steps"], start=1))
    partner = c["partner"]
    ptext = "".join(f"<p>{inline(p)}</p>" for p in partner["text"])
    pserv = "".join(f'<span class="tag">{esc(s)}</span>' for s in partner["services"])
    work = "".join(f'<article class="work-item"><div class="meta"><span>{esc(w["dates"])}</span><span>&middot;</span><span>{esc(w["role"])}</span></div><h3>{esc(w["client"])}</h3><p>{esc(w["text"])}</p></article>'
                   for w in c["work"])
    sectors = "".join(f'<span class="tag">{esc(s)}</span>' for s in c["sectors"])
    body = f"""{page_hero(c['kicker'], esc(c['headline']), esc(c['lede']), cta_actions('Consulting enquiry'), image='/assets/img/eric-consulting.jpg', alt=NAME)}
<section class="section tight"><div class="wrap"><div class="prose">{intro}</div></div></section>
<section class="section band limestone"><div class="wrap">
  <div class="section-head">{label("What I do", rule=True)}<h2>Four kinds of problems.</h2></div>
  <div class="cols cols-2">{services}</div>
  <div style="margin-top:2rem">{label("Where I've done it")}<div class="tags">{sectors}</div></div>
</div></section>
<section class="section"><div class="wrap">
  <div class="section-head">{label("How I work", rule=True)}<h2>{esc(c['how']['headline'])}</h2><p class="lede">{esc(c['how']['text'])}</p></div>
  <div class="cols cols-3 divided">{steps}</div>
</div></section>
<section class="section tight" id="electric-mind"><div class="wrap two-col">
  <div>{label("Partners")}<h2>{esc(partner['headline'])}</h2>{ptext}<p><a class="more" href="{esc(partner['url'])}" target="_blank" rel="noopener">Visit {esc(partner['name'])} &#8599;</a></p></div>
  <div>{label("What the partnership brings")}<div class="tags">{pserv}</div></div>
</div></section>
<section class="section band limestone"><div class="wrap">
  <div class="section-head">{label("Selected work", rule=True)}<h2>Things I've actually done.</h2><p class="muted">Client names are shared where I'm able to. Others are described by type.</p></div>
  <div class="cols cols-2">{work}</div>
</div></section>
<section class="section band dark"><div class="wrap two-col">
  <div>{label("Next step")}<h2>{esc(c['cta']['headline'])}</h2><p class="lede">{esc(c['cta']['text'])}</p></div>
  <div class="actions" style="margin:0;align-self:center"><a class="btn primary" href="mailto:{EMAIL}?subject=Consulting%20enquiry">{EMAIL}</a>{f'<a class="btn secondary" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">Book a call</a>' if SITE.get('booking_url') else ''}</div>
</div></section>"""
    desc = "Eric Lombardi is a strategy consultant for financial services and technology companies: business cases, mergers and acquisitions, venture advisory and program delivery, independently and with partner firms like Electric Mind."
    ld = [{"@type": "ProfessionalService", "@id": DOMAIN + "/consulting/#service", "name": f"{NAME} Consulting", "url": absu("/consulting/"),
           "provider": {"@id": PERSON_ID}, "areaServed": ["Canada", "United States"], "description": desc,
           "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Services", "itemListElement": [
               {"@type": "Offer", "itemOffered": {"@type": "Service", "name": s["title"], "description": s["summary"]}} for s in c["services"]]}}]
    render(T("Consulting: strategy, M&A, ventures and delivery"), desc, body, path="/consulting/", current="/consulting/", image="/assets/img/eric-consulting.jpg", jsonld=ld)


def build_writing(posts):
    chips = '<div class="chips" data-filter-group="posts"><button class="chip" data-value="all" aria-pressed="true">All</button>'
    cats_used = []
    for cat, lab in SITE["categories"].items():
        if any(p["category"] == cat for p in posts):
            cats_used.append(cat)
            chips += f'<button class="chip" data-value="{cat}" aria-pressed="false">{esc(lab)}</button>'
    chips += "</div>"
    entries = '<ul class="rule-list">' + "".join(post_entry(p) for p in posts) + "</ul>"
    lede = f"Essays and notes on Ontario's economy, housing, infrastructure and the institutions that are supposed to deliver. Columns I write elsewhere are on the <a href=\"{u('/media/')}\">media page</a>."
    actions = f'<div class="actions"><a class="btn secondary small" href="{u("/feed.xml")}">RSS feed</a><a class="btn secondary small" href="{u("/support/#signup")}">New posts by email</a></div>'
    body = f"""{page_hero('Writing', 'Notes on growth, cities and how government works.', lede, actions)}
<section class="section tight"><div class="wrap">{chips}{entries}</div></section>"""
    render(T("Writing"), "Essays and notes by Eric Lombardi on Ontario's economy, housing, infrastructure and public institutions.", body, path="/writing/", current="/writing/",
           jsonld=[{"@type": "Blog", "@id": DOMAIN + "/writing/#blog", "name": f"{NAME}: writing", "url": absu("/writing/"), "author": {"@id": PERSON_ID},
                    "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": absu(p["url"]), "datePublished": p["date"].isoformat()} for p in posts[:20]]}],
           lastmod=posts[0]["date"] if posts else TODAY)
    for cat in cats_used:
        sub = [p for p in posts if p["category"] == cat]
        lab = SITE["categories"][cat]
        body = f"""{page_hero('Writing', esc(lab), f'{len(sub)} post{"s" if len(sub) != 1 else ""} in this category. <a href="{u("/writing/")}">All writing</a>.')}
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
        hero_img = f'<img class="ratio-16x9" src="{u(p["image"])}" alt="" style="max-width:54rem;margin-bottom:2rem" width="1600" height="900">' if p.get("image") else ""
        share_url = absu(p["url"])
        share = (f'<div class="share"><span class="muted">Share</span>'
                 f'<a href="https://x.com/intent/post?text={esc(p["title"])}&url={share_url}" target="_blank" rel="noopener">X</a>'
                 f'<a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener">LinkedIn</a>'
                 f'<a href="https://bsky.app/intent/compose?text={esc(p["title"])}%20{share_url}" target="_blank" rel="noopener">Bluesky</a>'
                 f'<a href="mailto:?subject={esc(p["title"])}&body={share_url}">Email</a></div>')
        body = f"""<section class="wrap"><header class="article-head">
  {label(f'<a href="{u("/writing/category/" + p["category"] + "/")}">{esc(p["category_label"])}</a>', rule=True)}
  <h1>{esc(p['title'])}</h1>
  <p class="article-meta"><span>{fmt_date(p['date'])}</span><span>&middot;</span><span>{reading_time(p['html'])} min read</span><span>&middot;</span><span>By <a href="{u('/about/')}">{esc(NAME)}</a></span></p>
</header>
{hero_img}{notice}
<article class="prose">{p['html']}</article>
{share}{pager}</section>
<section class="section band limestone" style="margin-top:var(--section)"><div class="wrap two-col"><div>{label("Free updates")}<h2>Get the next one by email.</h2><p>New writing, plus invitations to events near you.</p></div><div>{signup_form('inline')}</div></div></section>"""
        ld = [{"@type": "BlogPosting", "@id": absu(p["url"]) + "#article", "headline": p["title"], "description": p["summary"], "url": absu(p["url"]),
               "datePublished": p["date"].isoformat(), "dateModified": (p["updated"] or p["date"]).isoformat(),
               "author": {"@id": PERSON_ID}, "publisher": {"@id": PERSON_ID}, "mainEntityOfPage": absu(p["url"]),
               "image": absu(p["image"]) if p.get("image") else absu(SITE["og_image"]), "articleSection": p["category_label"],
               "keywords": ", ".join(p["tags"]), "wordCount": p["words"], "inLanguage": "en-CA", "isPartOf": {"@id": DOMAIN + "/writing/#blog"}}]
        render(T(p["title"]), p["summary"] or strip_tags(p["html"])[:155], body, path=p["url"], current="/writing/", image=p.get("image") or None,
               kind="article", jsonld=ld, lastmod=p["updated"] or p["date"], reading=True)


def build_media(media):
    columns = [m for m in media if m["kind"] == "column"]
    interviews = [m for m in media if m["kind"] == "interview"]
    coverage = [m for m in media if m["kind"] == "coverage" and not m.get("campaign")]
    formats = sorted({m.get("format", "") for m in interviews if m.get("format")})
    chips = '<div class="chips" data-filter-group="media"><button class="chip" data-value="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" data-value="{esc(f)}" aria-pressed="false">{esc(f.title())}</button>' for f in formats) + "</div>"
    lede = f"Columns in The Hub, the Toronto Star and elsewhere, and interviews on podcasts, radio and television. Coverage of the 2026 leadership campaign is archived <a href=\"{u('/policy/ontario-liberal-leadership-2026/#coverage')}\">on the campaign page</a>."
    actions = f'<div class="actions"><a class="btn primary small" href="mailto:{EMAIL}?subject=Media%20request">Media and speaking requests</a><a class="btn secondary small" href="#media-kit">Media kit</a></div>'
    news = ""
    if coverage:
        news = f"""<section class="section tight"><div class="wrap"><div class="section-head">{label("In the news")}<h2>Coverage of the work</h2></div>{media_by_year(coverage, 'news', limit=6, wide=True)}</div></section>"""
    body = f"""{page_hero('Media', 'Columns, interviews and appearances.', lede, actions)}
<section class="section tight"><div class="wrap two-col equal">
  <div>
    <div class="section-head">{label("Columns and essays", rule=True)}<h2>Published elsewhere</h2></div>
    {media_by_year(columns, 'columns', limit=8)}
  </div>
  <div>
    <div class="section-head">{label("Interviews and appearances", rule=True)}<h2>In the media</h2></div>
    {chips}
    {media_by_year(interviews, 'media', limit=8)}
  </div>
</div></section>
<section class="section band limestone" id="media-kit"><div class="wrap">
  <div class="section-head">{label("Media kit")}<h2>For producers, editors and organizers.</h2></div>
  <div class="cols cols-3 divided">
    <div><h3>Short bio</h3><p>{esc(SITE['description'])}</p></div>
    <div><h3>Headshot</h3><p>Square, 800 &times; 800, suitable for print and web. New photographs are coming, and this one is current.</p><div class="actions"><a class="btn secondary small" href="{u('/assets/img/eric-headshot.jpg')}" download>Download JPG</a></div></div>
    <div><h3>Requests</h3><p>Interviews, comment, columns and speaking invitations. I reply within a couple of days.</p><div class="actions"><a class="btn primary small" href="mailto:{EMAIL}?subject=Media%20request">{EMAIL}</a></div></div>
  </div>
</div></section>
{news}"""
    render(T("Media: columns, interviews and appearances"), f"Columns by {NAME} in The Hub, the Toronto Star and others, plus podcast, radio and television interviews.", body, path="/media/", current="/media/",
           lastmod=media[0]["d"] if media else TODAY)


def build_policy(policy, media):
    idx_meta, idx_html, items = policy
    entries = "".join(policy_entry(it) for it in items)
    body = f"""{page_hero(idx_meta.get('kicker', 'Public policy'), esc(idx_meta.get('headline', 'Public policy')), esc(idx_meta.get('lede', '')))}
<section class="section tight"><div class="wrap"><div class="cols cols-3">{entries}</div></div></section>
<section class="section band limestone"><div class="wrap two-col"><div class="prose">{idx_html}</div><aside><div class="panel accent">{label("The platform")}<h3>Ontario Can Still Win</h3><p class="small">The fully costed 2026 platform: thirteen policy areas, more than 190 commitments, reconciled to the provincial budget baseline.</p><div class="actions"><a class="btn primary small" href="{esc(SITE['platform_url'])}" target="_blank" rel="noopener">Read the platform &#8599;</a></div></div></aside></div></section>
{x_feed_html()}"""
    render(T("Public policy and advocacy"), f"{NAME}'s public policy work: the 2026 Ontario Liberal leadership campaign and platform, More Neighbours Toronto and Build Toronto.", body, path="/policy/", current="/policy/")
    campaign_items = [m for m in media if m.get("campaign")]
    for it in items:
        links = "".join(f'<a class="btn {"primary" if l["primary"] else "secondary"}" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} &#8599;</a>' for l in it["links"])
        facts = "".join(f'<div><dt>{k}</dt><dd>{esc(it[key])}</dd></div>' for k, key in (("Role", "role"), ("When", "dates")) if it.get(key))
        gallery = f'<div class="gallery" style="margin-top:2rem">{"".join(f"<img src=\"{u(g)}\" alt=\"\" loading=\"lazy\">" for g in it["gallery"])}</div>' if it["gallery"] else ""
        coverage = ""
        if truthy(it.get("coverage", "")) and campaign_items:
            coverage = f"""<section class="section" id="coverage"><div class="wrap">
  <div class="section-head">{label("Archive", rule=True)}<h2>Campaign coverage, columns and interviews</h2><p class="muted">{len(campaign_items)} items from the 2026 leadership campaign, kept separate from my other <a href="{u('/media/')}">media</a> and <a href="{u('/writing/')}">writing</a>.</p></div>
  <div class="chips" data-filter-group="coverage"><button class="chip" data-value="all" aria-pressed="true">All</button><button class="chip" data-value="column" aria-pressed="false">Columns by Eric</button><button class="chip" data-value="interview" aria-pressed="false">Interviews</button><button class="chip" data-value="coverage" aria-pressed="false">Coverage</button></div>
  {media_by_year(campaign_items, 'coverage', limit=12, wide=True)}
</div></section>"""
        feature = ""
        if it.get("feature_title"):
            feature = f"""<section class="section band limestone"><div class="wrap feature"><img src="{u(it.get('feature_image', it.get('image')))}" alt="" loading="lazy" width="1600" height="1000"><div>{label(esc(it.get('feature_kicker', '')))}<h2>{esc(it['feature_title'])}</h2><p>{esc(it.get('feature_text', ''))}</p><div class="actions"><a class="btn primary" href="{esc(it.get('feature_url', '#'))}" target="_blank" rel="noopener">{esc(it.get('feature_cta', 'Open'))} &#8599;</a></div></div></div></section>"""
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
    up_html = "".join(event_block(e) for e in upcoming) if upcoming else '<div class="empty">Nothing scheduled right now. Sign up and you\'ll hear first.</div>'
    past_html = ""
    if past:
        past_html = f'<details class="past" style="margin-top:2.5rem"><summary>Where I have been ({len(past)})</summary>{"".join(event_block(e) for e in past)}</details>'
    ics = absu("/events.ics")
    webcal = ics.replace("https://", "webcal://").replace("http://", "webcal://")
    body = f"""{page_hero('Events', "Where I'll be.", "Talks, panels, meetups and the occasional debate. Dates are added as they're confirmed, and third-party registration links open on the organizer's site.")}
<section class="section tight"><div class="wrap two-col">
  <div>
    <div class="section-head">{label("Upcoming", rule=True)}<h2>Coming up</h2></div>
    {up_html}
    {past_html}
  </div>
  <aside class="stack">
    <div class="panel quiet">{label("Calendar")}<h3>Subscribe to the calendar</h3><p class="small">New events appear in your calendar automatically.</p><div class="actions"><a class="btn primary small" href="{webcal}">Add to calendar</a><button class="btn secondary small" type="button" data-copy="{ics}">Copy feed URL</button></div><p class="fine" style="margin-top:.75rem">Or <a href="{u('/events.ics')}">download the .ics file</a>.</p></div>
    <div class="panel quiet">{label("Invitations")}<h3>Invite me to speak</h3><p class="small">I speak on Ontario's economy, housing, infrastructure delivery, government capability, and strategy in financial services and technology. Email a date, a place and an audience.</p><div class="actions"><a class="btn secondary small" href="mailto:{EMAIL}?subject=Speaking%20invitation">Email an invitation</a></div></div>
    <div class="panel quiet">{label("Updates")}<h3>Hear about events near you</h3><p class="small">Your postal code lets me tell you only about the ones nearby.</p><div class="actions"><a class="btn secondary small" href="{u('/support/#signup')}">Sign up</a></div></div>
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
    host = DOMAIN.split("//")[1]
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
        once = '<a class="btn secondary" href="#" aria-disabled="true">Give once</a><span class="note-inline">Payments open soon</span>'
    hero_actions = '<div class="actions"><a class="btn primary" href="#contribute">Contribute</a><a class="btn secondary" href="#signup">Sign up for free updates</a></div>'
    pledge = "".join(f"<p>{inline(p)}</p>" for p in s["pledge"]["paragraphs"])
    uses = "".join(f'<div><h3>{esc(x["title"])}</h3><p>{esc(x["text"])}</p></div>' for x in s["uses"])
    faq = "".join(f'<details class="faq"><summary>{esc(q["q"])}</summary><p>{esc(q["a"])}</p></details>' for q in s["faq"])
    c = s["contribute"]
    note = esc(c["note"]).replace("a third-party platform", platform)
    body = f"""{page_hero(s['kicker'], esc(s['headline']), esc(s['lede']), hero_actions)}
<section class="section tight" id="contribute"><div class="wrap two-col">
  <div class="panel quiet">{label("The pledge")}<h2>{esc(s['pledge']['title'])}</h2>{pledge}</div>
  <div class="panel accent">{label("Contribute")}<h2>{esc(c['title'])}</h2><p>{esc(c['text'])}</p><div class="actions">{monthly}{once}</div><p class="fine" style="margin-top:1rem">{note}</p></div>
</div></section>
<section class="section band limestone"><div class="wrap"><div class="section-head">{label("Where it goes", rule=True)}<h2>What contributions pay for.</h2></div><div class="cols cols-4 divided">{uses}</div></div></section>
<section class="section" id="signup"><div class="wrap two-col">
  <div>{label("Free updates", rule=True)}<h2>{esc(SITE['signup']['title'])}.</h2><p class="lede">{esc(SITE['signup']['text'])}</p><ul class="small"><li>New essays and notes, usually a few times a month</li><li>Invitations to events, matched to where you are</li><li>Occasional updates on the public policy work and how to help</li></ul><p class="small">Prefer a feed? Writing is on <a href="{u('/feed.xml')}">RSS</a>, and events on a <a href="{u('/events.ics')}">calendar feed</a>.</p></div>
  <div>{signup_form('full')}</div>
</div></section>
<section class="section band limestone"><div class="wrap"><div class="section-head">{label("Questions")}<h2>The fine print, in plain words.</h2></div>{faq}</div></section>"""
    render(T("Support the work"), "Support Eric Lombardi's public policy and advocacy work: sign up for free updates, or contribute what you want to fund community, events, research and travel across Ontario. None of it is personal income.", body, path="/support/", current="/support/")
    for old, anchor in (("subscribe", ""), ("signup", "#signup")):
        write(f"{old}/index.html", f"""<!DOCTYPE html><html lang="en-CA"><head><meta charset="utf-8"><title>Support | {esc(NAME)}</title>
<meta http-equiv="refresh" content="0; url={u('/support/')}{anchor}"><link rel="canonical" href="{absu('/support/')}"><meta name="robots" content="noindex"></head>
<body><p>This has moved to <a href="{u('/support/')}{anchor}">the support page</a>.</p></body></html>
""")


def build_about():
    meta, md = read_md(CONTENT / "pages" / "about.md")
    facts = """<dl class="facts"><div><dt>Based in</dt><dd>Toronto, Ontario</dd></div><div><dt>Education</dt><dd>BASc, Nanotechnology Engineering, University of Waterloo</dd></div><div><dt>Work</dt><dd>Strategy consultant, financial services and technology</dd></div><div><dt>Civic</dt><dd>Founder, More Neighbours Toronto. Chair, Build Toronto. 2026 Ontario Liberal leadership candidate</dd></div></dl>"""
    body = f"""{page_hero('About', esc(meta.get('headline', 'About')), esc(meta.get('lede', '')), cta_actions(), image=meta.get('image'), alt=NAME)}
<section class="section tight"><div class="wrap">{facts}<div class="prose">{md_to_html(md)}</div>
<p style="margin-top:2rem"><a class="more" href="{u('/assets/img/eric-headshot.jpg')}" download>Download headshot &darr;</a> &nbsp; <a class="more" href="{u('/media/#media-kit')}">Media kit &rarr;</a></p></div></section>"""
    render(T("About"), SITE["description"], body, path="/about/", current="", image=meta.get("image"), kind="profile", reading=True)


def build_contact():
    socials = "".join(f'<li><a href="{esc(s["url"])}" rel="me noopener" target="_blank">{esc(s["name"])}{(" " + esc(s["handle"])) if s.get("handle") else ""}</a></li>' for s in SITE["socials"] if s.get("show", True))
    booking = f'<a class="btn secondary small" href="{esc(SITE["booking_url"])}" target="_blank" rel="noopener">Book a call</a>' if SITE.get("booking_url") else ""
    addr = f'<p class="small muted" style="margin-top:.75rem">Mail: {esc(SITE["mailing_address"])}</p>' if SITE.get("mailing_address") else ""
    body = f"""{page_hero('Contact', 'Get in touch.', 'Email is best. I read everything and reply within a couple of days.', f'<div class="actions"><a class="btn primary" href="mailto:{EMAIL}">{EMAIL}</a>{booking}</div>')}
<section class="section tight"><div class="wrap cols cols-3 divided">
  <div>{label("Consulting")}<h3>Work with me</h3><p>A sentence or two about the problem is enough to start.</p><div class="actions"><a class="btn primary small" href="mailto:{EMAIL}?subject=Consulting%20enquiry">Email about a project</a></div></div>
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
def build_feeds(posts):
    items = []
    for p in posts[:30]:
        items.append(f"""<item>
<title>{esc(p['title'])}</title>
<link>{absu(p['url'])}</link>
<guid isPermaLink="true">{absu(p['url'])}</guid>
<pubDate>{rfc822(p['date'])}</pubDate>
<category>{esc(p['category_label'])}</category>
<description>{esc(p['summary'])}</description>
<content:encoded><![CDATA[{absolutize(p['html'])}]]></content:encoded>
</item>""")
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
          "authors": [{"name": NAME, "url": DOMAIN + "/"}],
          "items": [{"id": absu(p["url"]), "url": absu(p["url"]), "title": p["title"], "summary": p["summary"],
                     "content_html": absolutize(p["html"]), "date_published": p["date"].isoformat() + "T12:00:00Z",
                     "tags": [p["category_label"]] + p["tags"], **({"image": absu(p["image"])} if p.get("image") else {})} for p in posts[:30]]}
    write("feed.json", json.dumps(jf, ensure_ascii=False, indent=1))


def build_sitemap_robots():
    urls = "".join(f"<url><loc>{absu(p)}</loc><lastmod>{d.isoformat()}</lastmod></url>\n" for p, d in SITEMAP)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")


def build_llms(posts, media, events, policy_items):
    cols = [m for m in media if m["kind"] == "column"]
    ints = [m for m in media if m["kind"] == "interview"]
    up = [e for e in events if not e["past"]]
    lines = [f"# {NAME}", "", f"> {SITE['description']}", "",
             f"Email: {EMAIL}. Location: {SITE['location']['label']}. Socials: " + ", ".join(f"{s['name']} {s['url']}" for s in SITE["socials"] if s.get("show", True)), "",
             "## Pages", ""]
    for n in SITE["nav"] + [{"label": "About", "href": "/about/"}, {"label": "Privacy", "href": "/privacy/"}]:
        lines.append(f"- [{n['label']}]({absu(n['href'])})")
    lines += ["", "## Machine-readable", "", f"- RSS: {DOMAIN}/feed.xml", f"- JSON Feed: {DOMAIN}/feed.json", f"- Calendar (iCalendar): {DOMAIN}/events.ics",
              f"- Sitemap: {DOMAIN}/sitemap.xml", f"- JSON API: {DOMAIN}/api/site.json, /api/posts.json, /api/media.json, /api/events.json", "",
              "## Public policy work", ""]
    for it in policy_items:
        lines.append(f"- [{it['title']}]({absu(it['url'])}): {it.get('role', '')}. {it.get('summary', '')}")
    lines += ["", "## Writing (own site)", ""]
    for p in posts:
        lines.append(f"- [{p['title']}]({absu(p['url'])}) ({p['date'].isoformat()}, {p['category_label']}): {p['summary']}")
    lines += ["", "## Columns elsewhere", ""]
    for m in cols:
        lines.append(f"- {m['outlet']}: [{m['title']}]({m['url']}) ({m['date']})")
    lines += ["", "## Interviews and appearances", ""]
    for m in ints:
        lines.append(f"- {m['outlet']}: [{m['title']}]({m['url']}) ({m['date']}, {m.get('format', '')})")
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
    build_writing(posts)
    build_media(media)
    build_policy(policy, media)
    build_events(events)
    build_support()
    build_about()
    build_contact()
    build_privacy()
    build_404()
    build_feeds(posts)
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
