# Change log

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
