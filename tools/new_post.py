#!/usr/bin/env python3
"""Scaffold a new post: python3 tools/new_post.py "Title of the post" [category]

Creates content/posts/<slug>.md with today's date and the frontmatter filled in.
Then write the body in Markdown and run: python3 build.py
"""
import sys, re, pathlib, datetime as dt, json
HERE = pathlib.Path(__file__).resolve().parent.parent
if len(sys.argv) < 2: sys.exit(__doc__)
title = sys.argv[1]; cat = sys.argv[2] if len(sys.argv) > 2 else "economy"
cats = json.load(open(HERE / "content" / "site.json"))["categories"]
if cat not in cats: sys.exit(f"Unknown category '{cat}'. Choose from: {', '.join(cats)}")
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
path = HERE / "content" / "posts" / f"{slug}.md"
if path.exists(): sys.exit(f"{path} already exists")
path.write_text(f"""---
title: {title}
date: {dt.date.today().isoformat()}
category: {cat}
summary: One or two sentences shown on cards, in search results and in the RSS feed.
tags:
image:
draft: true
---

Write the post here in Markdown. Delete the draft line when it is ready to publish.
""", encoding="utf-8")
print("created", path.relative_to(HERE))
