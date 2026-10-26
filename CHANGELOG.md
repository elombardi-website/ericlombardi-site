# Change log

## Revision 3 (26 October 2026)

Applies "Eric Lombardi — revision 3: alignment audit, unified writing, and a more consistent
identity". Captures were taken with `review.js` (real Chrome, real font files, fonts awaited,
failed requests logged) before and after the work, at 1440 × 1000 and 390 × 844 for Home,
Consulting, About, Writing, Media, Public policy, Contact and one article, plus 768 × 1024 and
320 × 900 for Home, Consulting, Writing and Contact, and the open mobile menu as a separate state.
Before: `build/review-before/`. After: `build/review-after/`. Each folder has clean and
guide-overlay screenshots, per-page metrics and a contact sheet (`index.html`).

### Confirmed defects and fixes (numbered)

1. **Consulting page overflowed the viewport at 390, 768 and 320 px** (document width 470 px
   at 390 px, 905 at 768, 463 at 320). Measured, not inferred. Cause: the "Example" links in the
   service columns were set `white-space: nowrap`, which forced each grid column past its track.
   Fix: `.more` wraps normally and grid children carry `min-width: 0`. After: document width
   equals the viewport at every width.
2. **Article page overflowed at 390 px** (document width 407 px). Cause: embedded Datawrapper
   charts carry inline `margin-right: 20px` on a 100 %-wide iframe. Fix: embeds are forced to
   `max-width: 100%` with no inline margin. After: 390 px.
3. **Three-area band headings were Manrope, and the three areas did not share rows.** Each
   column's description and action started at its own height. Fix: the band is a component whose
   areas are grid items on four shared rows (symbol, heading, description, action) using
   `grid-template-rows: subgrid`, with a flex fallback where subgrid is unsupported. Measured
   after at 1440 px: the three headings top at the same y, the three descriptions start together,
   and the three actions sit on one bottom row.
4. **Section titles with right-hand links** ("Latest writing / All writing", "In the media",
   "Public policy") now sit in a baseline-aligned row with the heading's bottom margin reset, so
   the link reads against the heading baseline. Measured text-box bottoms differ by the expected
   descender difference only (6 px at 43 px against 15 px type; 3 px at 32 px).
5. **Principal titles that had drifted to Manrope** (band headings, consulting service headings,
   project names, organization names in the record, the sign-up headings) are Canela again at
   the role sizes in the brief: inner-page titles 36–64 px, section headings 28–42 px, pillar and
   service headings 24–30 px, article-card titles 23–32 px. Utility headings (event titles,
   aside panels, media kit, form labels, navigation) stay Manrope.
6. **External authored pieces showed their source twice** in the metadata row after the merge
   (introduced during this revision, caught in the after-capture). Fix: the source appears once,
   as the label, followed by the date.
7. **Public-policy page left an empty column** beside the platform panel once the priorities
   moved into the band (introduced during this revision). Fix: the panel renders full width when
   there is no accompanying prose.

Shared text axis: on every captured page, all `.wrap` containers resolve to one text axis
(x = 140 at 1440 px), and the hero copy aligns to it while the hero image extends further right by
design. No double padding was found.

### Authorship reclassification

- **Writing** is now one collection: 6 local posts plus 31 externally published columns, all
  by Eric, sorted by original publication date, in one card family. External titles link to the
  canonical piece and the action reads "Read at The Hub" (or the outlet). The local note "Alto
  should be just the beginning" is a companion to the Toronto Star op-ed of the same day, so the
  Star piece is listed once with a "Companion note and map on this site" link, and the note is not
  listed twice. Filters are "All / On this site / Elsewhere" and refine the one feed.
- **In the media** (22 interviews and 20 coverage items, about Eric) is a secondary archive at
  `/media/`, reached from Writing, the footer and llms.txt. It left the primary navigation.
  The campaign-era archive stays on the leadership page.
- The home "Latest writing" feature is the newest authored item (currently a Hub column) unless
  a local post carries `featured: true`. The RSS and JSON feeds, `llms.txt` and a new
  `api/writing.json` use the same classification.
- **Needs editorial verification** (listed as authored on the campaign news page, byline not
  independently confirmed): The Bridge, "Ontario needs a new deal with its cities" (April 4,
  2026); Toronto Sun, "Premier Doug Ford's eighth budget another step in Ontario's decline"
  (March 28, 2026); Canada Real, "The housing crisis did not stay in housing" (July 28, 2026,
  article link not located). They carry a `verify` note in `media.json`.

### Band component

`band_areas()` renders the dark ink band with ivory text, bronze symbols or short rules, Canela
headings and shared rows. Used on Home (three work areas, unchanged categories), Consulting
(the four actual service areas, two columns at 1024, four at 1280 and up) and Public policy (the
five existing "What I argue for" priorities, three plus two columns). The writing archive and
article pages end with a compact dark sign-up band. About and Contact were left light.

### Inspected and not inspected

Inspected: the captures listed above, in-browser measurements of band rows and title/link
baselines at 1440 px, document widths at every captured size, Canela delivery
(`document.fonts.check` true and computed family Canela on every page), zero failed requests,
the open mobile menu. Not inspected: 1024 px and 600 px in this pass (covered in revision 2),
enlarged-text (200 %) reflow, and real submission of the sign-up form, which has no endpoint yet.

## Revision 2 (26 October 2026)

Applies "Eric Lombardi website — revision brief, version 2". Routes, content model, feeds,
structured data and the sign-up function are unchanged.

### Design changes

- Header: the name is set in Canela at 22–30 px (20 px at 320 px) with restrained tracking;
  header height 68–84 px; navigation in Manrope Medium 14 px with an underline for the
  current page; Support is an outline button. The full navigation now collapses below 1056 px.
- Home opening: a wider shell (90 rem) with the text aligned to the 80 rem content grid and the
  portrait extending further right, in a 7:5 split. The statement is 44–100 px Canela with a
  controlled two-line break on wide screens and natural wrapping elsewhere. Two actions only.
  The biography paragraph became a quiet record line.
- Decal family (inline SVG, bronze 1.25 px, aria-hidden, no pointer events): a stepped portal
  outline with an open arc on the portrait's outer corner (240 px on desktop, 96 px on phones);
  three 44 px line symbols for the work categories (structural grid, editorial lines, open
  portal); a large cropped arc with one rule at the edge of the contact band. The old
  `.frame::after` with negative z-index is gone; the portrait wrapper is its own stacking context.
- Hierarchy: Canela only for display statements, page titles, the featured essay (36–44 px) and
  secondary editorial titles (26–32 px). Work categories, event titles, project names and other
  utility headings are Manrope Semibold 20–24 px; compact media titles are Manrope Medium
  17–19 px; descriptive paragraphs moved from 15 px to 17–18 px.
- Sections: the three work categories are a full-width Midnight Ink band with ivory text,
  symbols and vertical separators (rows with horizontal dividers on phones). The writing section
  features one essay (a `featured: true` post, otherwise the latest) with two secondary entries
  alongside. Media is a compact sans-serif list in two columns. The public-policy record is a
  dated list with a date rail, role label and organization name. The sign-up is a compact
  invitation with visible labels; it spreads into one row only above 1280 px. Limestone is now
  used only for the media kit, the support page's uses, and the platform feature.
- Spacing: hero 48–72 px, work band 32–48 px, editorial sections 64–88 px, compact lists
  40–56 px.
- Mobile: statement 45 px at 390 px, intro 18 px, gutters 20 px (16 px at 320 px); the hero
  stacks statement, introduction, actions, then a 4:3 portrait crop with a 96 px decal corner;
  no page-level `overflow-x: hidden`. Verified at 1440, 1200, 1024, 900, 768, 600, 390 and 320.

### Copy replacements

- Home: eyebrow "Finance, technology and public life"; introduction and record line per the
  brief; "Latest writing"; "Get in touch." with the brief's contact sentence; sign-up heading
  "New writing and upcoming events." with the brief's two sentences. The slogan above the three
  categories is gone.
- Consulting: "Consulting in financial services and technology." with the brief's introduction;
  service headings "Strategy and investment decisions", "Mergers, acquisitions and
  divestitures", "Ventures, startups and advisory", "Program delivery", each with one linked
  example instead of a repeated portfolio; "Selected projects"; the Capco entry's broken final
  sentence repaired; Cut+Dry and the bank entry tightened.
- About: "About Eric." with the brief's introduction; facts now read "Founder and former
  president, More Neighbours Toronto (2021 to 2026). Former chair, Build Toronto (2025 to
  2026). Ontario Liberal leadership candidate, 2026."
- Public policy: "Public policy and civic work." with the brief's introduction.
- Writing: "Writing on politics, prosperity and technology."
- Response-time promises ("I reply within a couple of days") removed everywhere.
- Support FAQ: the election-finance assurance and the future-office commitment were removed
  pending review; "no questions asked" removed.
- Events: the June 9 record is "Formal entry into the Ontario Liberal leadership race", with a
  note that the exploratory period began in January 2026, matching the campaign chronology.

### Cleanup and launch checks

- Sample events are excluded from every build unless `--placeholders` is passed; the events
  page shows its empty state and the calendar feed carries only the real record.
- Sign-up: the form has visible labels, required fields and native validation. With no list
  endpoint configured, submitting opens an email draft and the message says plainly that the
  list is not connected yet. No success message claims a subscription.
- Footer: the tracking statement is generated from configuration. Analytics are off and the X
  embed is on, so it reads "No advertising trackers. This site uses embedded posts from X on
  the public-policy page, which may set their own cookies." The privacy page says analytics
  apply only if enabled.
- Fonts: Canela confirmed rendering in-browser (`document.fonts.check` true, computed family
  Canela on the statement). No new families added.

### Still awaiting approved content or configuration

- Electric Mind wording and the partnership description (`consulting.json`, `_review`).
- The pledge's reporting commitment and the "not a political contribution" wording
  (`support.json`, `_review`); legal review before launch.
- Payment platform and links for the contribution buttons.
- Email tool endpoint for the sign-up form; the location-based invitation sentence assumes
  segmentation by postal code or city once the list is connected.
- Replacement portraits; the current images are campaign-era placeholders with focal points set.
- "Chair and co-founder" of Build Toronto (public sources say chair); LinkedIn URL; the Canada
  Real column link; the Canela web-licence receipt naming ericlombardi.ca.
