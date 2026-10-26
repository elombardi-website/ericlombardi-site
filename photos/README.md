# Photos of Eric — drop folder

Put photographs here with exactly these filenames. The build picks them up automatically,
resizes them for the web and uses them in place of the current placeholders. Originals stay
here (this folder is not published; only the resized copies in `assets/img/` are).

| File | Where it appears | Shape and crop advice |
|---|---|---|
| `hero.jpg` | Home page opening, beside "A future worth building." | Portrait orientation, at least 1600 px tall. Shown 4:5 on desktop and 4:3 on phones, so keep the face in the upper third and leave room on both sides. |
| `consulting.jpg` | Consulting page header | Landscape or square, at least 1600 px wide. Shown 4:3. Business setting, natural light. |
| `about.jpg` | About page header | Square or 4:3, at least 1200 px. |
| `headshot.jpg` | Media kit download, structured data for search engines | Square, 800 to 1600 px, plain background. |
| `share.jpg` | Default preview image when a page is shared on LinkedIn, X or in messages | Exactly 1200 × 630, or any landscape image (it will be cropped to that). |
| `support.jpg` | "Support the work" block on the home page | Landscape, at least 1600 px wide. A place or an event, not a portrait. |
| `campaign.jpg` | Ontario Liberal leadership page header and card | Landscape, at least 1600 px wide. |
| `more-neighbours.jpg` | More Neighbours Toronto page header | Landscape, at least 1600 px wide. |
| `build-toronto.jpg` | Build Toronto page header | Landscape, at least 1600 px wide. |
| `article-placeholder.jpg` | Thumbnail for any piece of writing that has no image of its own | Landscape, at least 1200 px wide. Something neutral and non-portrait. |
| `writing/<slug>.jpg` | Image for one specific piece of writing, where `<slug>` is the post's file name (for posts on this site) or the `id` field in `content/media.json` (for columns elsewhere) | Landscape, at least 1200 px wide. Shown large when the piece is featured, as a small 4:3 thumbnail elsewhere. |

JPEG or PNG. HEIC from an iPhone also works (the build converts it). Then run `python3 build.py`.
