#!/usr/bin/env python3
"""One-time migration: campaign blog posts (Website/blog/*.html) -> content/posts/*.md

Reads the article body of each campaign post, converts it to Markdown, pulls the
date/summary from the old blog index, and writes a frontmatter'd markdown file.
Images are expected in assets/img/posts/ (copied separately).
"""
import html as hm, pathlib, re, json, datetime as dt
from html.parser import HTMLParser

HERE = pathlib.Path(__file__).resolve().parent.parent
OLD = HERE.parent / "Website"
POSTS = HERE / "content" / "posts"
IMGDIR = HERE / "assets" / "img" / "posts"
LEAD = "/policy/ontario-liberal-leadership-2026/"

CATEGORY = {
    "what-my-policy-survey-says-about-ontario-right-now": "campaign-notes",
    "alto-should-be-just-the-beginning-of-ontarios-high-speed-rail-network": "infrastructure",
    "an-ontario-budget-for-decline-war-in-iran": "economy",
    "a-billion-here-a-billion-there": "economy",
    "poorer-than-alabama----what-the-gdp-per-capita-debate-is-really-about": "economy",
    "hamilton-speech-university-funding-changes-and-other-thoughts": "campaign-notes",
    "liberal-leadership-timelines-are-out": "campaign-notes",
}
NEW_SLUG = {  # tidy a couple of ugly slugs
    "poorer-than-alabama----what-the-gdp-per-capita-debate-is-really-about": "poorer-than-alabama-gdp-per-capita-debate",
    "alto-should-be-just-the-beginning-of-ontarios-high-speed-rail-network": "alto-should-be-just-the-beginning",
}

def fix_href(h):
    if not h: return h
    if h.startswith("../index.html") or re.match(r"https?://(www\.)?ericforolp\.ca/?$", h): return LEAD
    if "ericforolp.ca/tell-me-what-you-think" in h: return LEAD
    if h.startswith("../platform/"): return "https://platform.ericforolp.ca/" + h.split("/")[-1].replace("index.html", "")
    if h.startswith("../blog.html"): return "/writing/"
    return h

def fix_src(s):
    name = s.split("/")[-1]
    jpg = name.rsplit(".", 1)[0] + ".jpg"
    if (IMGDIR / jpg).exists(): name = jpg          # large PNGs were re-encoded as JPG
    return "/assets/img/posts/" + name

class MD(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []; self.stack = []; self.list_stack = []; self.href = None
        self.in_fig = False; self.fig_img = None; self.fig_cap = []; self.fig_href = None
        self.raw = None
    def text(self, s): self.out.append(s)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.raw is not None:
            self.raw.append(self.get_starttag_text()); return
        if tag in ("iframe", "script"):
            self.raw = [self.get_starttag_text()]; return
        if tag in ("p",): self.out.append("\n\n")
        elif tag == "h2": self.out.append("\n\n## ")
        elif tag == "h3": self.out.append("\n\n### ")
        elif tag == "h4": self.out.append("\n\n#### ")
        elif tag in ("ul", "ol"): self.list_stack.append([tag, 0]); self.out.append("\n")
        elif tag == "li":
            if not self.list_stack: self.list_stack.append(["ul", 0])
            self.list_stack[-1][1] += 1
            ind = "  " * (len(self.list_stack) - 1)
            mark = "-" if self.list_stack[-1][0] == "ul" else f"{self.list_stack[-1][1]}."
            self.out.append(f"\n{ind}{mark} ")
        elif tag in ("strong", "b"): self.out.append("**")
        elif tag in ("em", "i"): self.out.append("*")
        elif tag == "br": self.out.append("  \n")
        elif tag == "a":
            self.href = fix_href(a.get("href", ""))
            if self.in_fig: self.fig_href = self.href
            else: self.out.append("[")
        elif tag == "figure": self.in_fig = True; self.fig_img = None; self.fig_cap = []; self.fig_href = None
        elif tag == "img":
            if self.in_fig: self.fig_img = (fix_src(a.get("src", "")), a.get("alt", ""))
            else: self.out.append(f'\n\n![{a.get("alt","")}]({fix_src(a.get("src",""))})\n\n')
        elif tag == "figcaption": self.stack.append("cap")
        elif tag == "blockquote": self.out.append("\n\n> ")
    def handle_endtag(self, tag):
        if self.raw is not None:
            self.raw.append(f"</{tag}>")
            if tag in ("iframe", "script"):
                self.out.append("\n\n" + "".join(self.raw) + "\n\n"); self.raw = None
            return
        if tag in ("strong", "b"): self.out.append("**")
        elif tag in ("em", "i"): self.out.append("*")
        elif tag == "a" and not self.in_fig: self.out.append(f"]({self.href})")
        elif tag in ("ul", "ol"):
            if self.list_stack: self.list_stack.pop()
            self.out.append("\n")
        elif tag == "figcaption": self.stack.pop()
        elif tag == "figure":
            self.in_fig = False
            if self.fig_img:
                src, alt = self.fig_img; cap = "".join(self.fig_cap).strip()
                line = f'![{alt}]({src}' + (f' "{cap}"' if cap else "") + ")"
                if self.fig_href: line = f"[{line}]({self.fig_href})"
                self.out.append("\n\n" + line + "\n\n")
        elif tag in ("p", "h2", "h3", "h4", "blockquote"): self.out.append("\n")
    def handle_data(self, data):
        if self.raw is not None: self.raw.append(data); return
        if self.stack and self.stack[-1] == "cap": self.fig_cap.append(data); return
        if self.in_fig: return
        self.out.append(re.sub(r"\s+", " ", data.replace("\u200d", "").replace("\u200b", "")))
    def result(self):
        s = "".join(self.out)
        s = re.sub(r"[ \t]+\n", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip() + "\n"

def main():
    POSTS.mkdir(parents=True, exist_ok=True)
    index = (OLD / "blog.html").read_text(encoding="utf-8")
    cards = {}
    for m in re.finditer(r'<a class="blogcard" href="blog/([^"]+)\.html">\s*<div class="bd">(.*?)</div><h3>(.*?)</h3>\s*<p>(.*?)</p>', index, re.S):
        cards[m.group(1)] = (hm.unescape(m.group(2)), hm.unescape(m.group(3)), hm.unescape(m.group(4)))
    for f in sorted((OLD / "blog").glob("*.html")):
        slug = f.stem
        src = f.read_text(encoding="utf-8")
        art = re.search(r'<article class="post">(.*?)</article>', src, re.S).group(1)
        kicker = re.search(r'class="kicker">([^<]*)', src).group(1)
        date_s, title, desc = cards[slug]
        d = dt.datetime.strptime(date_s, "%b %d, %Y").date()
        p = MD(); p.feed(art); body = p.result()
        # pull a hero image: first image in the body
        img = re.search(r"!\[[^\]]*\]\((/assets/img/posts/[^)\s]+)", body)
        new = NEW_SLUG.get(slug, slug)
        fm = [
            f"title: {title}",
            f"date: {d.isoformat()}",
            f"category: {CATEGORY.get(slug, 'campaign-notes')}",
            f"summary: {desc}",
            f"tags: {kicker}",
            "origin: campaign",
        ]
        if img: fm.append(f"image: {img.group(1)}")
        (POSTS / f"{new}.md").write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body, encoding="utf-8")
        print("wrote", new + ".md", f"({len(body.split())} words)")

if __name__ == "__main__":
    main()
