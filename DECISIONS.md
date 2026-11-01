# Decisions for Eric (from the 1 November 2026 review)

The site ships the **default** in each item until you choose otherwise. Mark each line
"keep", "option" or a note, and I'll apply it.

## Design values

1. **Header marks.** Default: the mark is a square drawing that fills the shorter side of its
   zone, bottom-right, so every page's title starts at the same height and sits the same distance
   above the entablature. On short headers (category pages, Contact, Privacy) the mark is smaller.
   Option: redraw each mark so it stretches to fill the whole zone.
2. **Phone entablature.** Default: thirteen evenly spaced ticks, as approved. Options: five ticks
   on the phone's four-column grid, or the two rules with no ticks.
3. **Panels.** Default (new): the last two boxed panels (Support's pledge and contribution, the
   platform panel on Public policy) are rule-topped like everything else, the accent one with the
   heavy bronze rule. Option: put the borders back, which takes their text off the column lines.
4. **Menu breakpoint.** Default: the full menu appears from 1056px (your brief v2). Option:
   1024px, so it switches together with the twelve-column layout.
5. **Section headings on inner pages.** Default: full-width sections use the large size and
   headings inside columns use the smaller one. Option: one smaller size for every inner page.
6. **Compact work band on Home.** Default: kept slightly tighter than other dark bands. Option:
   one band size everywhere.
7. **404 page.** Default: one arch, in the body, with a pedestal mark in the header. Option: the
   arch moves into the header and the body keeps only the links.
8. **Media lists.** Shipped: outlet and date on the left (columns 1 to 4), title on the right
   (5 to 12). Option: drop the format word ("Video", "Print"), since the filters already cover it.
9. **Home events.** Shipped for when dates exist: a compact row (date · time · city, title, link),
   no summary. /events/ keeps the full entry.

## Organization

10. **Where media items live.** Suggested: campaign interviews and coverage only in the
    leadership archive; campaign columns in Writing; /media/ for everything else.
11. **/media/ headings.** Drop the eyebrow and heading that repeat the page title, and label the
    list "Interviews and coverage".
12. **Support order while payments are closed.** Put the sign-up form directly under the
    header, then the pledge, where the money goes, and the questions.
13. **Topics.** One topic list for all writing, suggested the six advocacy areas, with topic
    pages; "Campaign notes" becomes a label, not a topic.
14. **Home composition.** Options: a shorter public-policy summary, a consulting row, the
    feature image shown once across Home and Writing.
15. **One name per section.** For example "Public policy" everywhere (nav, kicker, links)
    instead of "Public policy" / "The civic work" / "Public policy and advocacy".
16. **One label per destination.** For example the closing band's button becomes "Send a
    message" under "Get in touch.", instead of repeating "Get in touch".
17. **About in the menu.** Join the desktop menu, or leave the phone menu.
18. **How policy pages end.** They now end with "More public work". Option: add the sign-up
    band, as articles have.
19. **The platform's home.** The leadership page header's buttons jump to the capsule
    ("The platform ↓") instead of repeating the capsule's own links.
20. **Events in the menu** while there are no dates, and whether the campaign-entry
    milestone stays in the events list.
21. **Contact rail.** One entry per contact topic; drop the Follow block, which repeats the footer.
22. **About facts.** Generate the civic fact from the policy pages; review the education fact
    and the closing line.
23. **Consulting.** Fold the sectors into the dark services band as its closing row, and style
    the Electric Mind capabilities differently from your sectors.
24. **Campaign archive order.** Newest first (now), oldest first, or "Columns by Eric" first.
25. **/writing/ columns.** Kept at 7 and 5 columns (28 Oct). Option: 8 and 3, the rail width.
26. **Long archives.** Cap "Show more" at two batches, then link to a full archive page.

## Content corrections (your words, so not changed)

27. **Leadership timeline.** The "August 10 and September 17" debates entry sits before
    "September 2"; suggested: chronological order, the debates as two entries.
28. **More Neighbours Toronto dates.** The page says "2021 to January 2026" and the text says
    you founded it in June 2021; suggested "June 2021 to January 2026".
29. **Alto companion note.** The title and summary could say it is a note on the Toronto Star
    column; the first paragraph repeats the link that the header now carries.
30. **Copy conventions.** One rule for full stops on section headings; sentence case for post
    titles.

## Not done in this pass (follow-ups)

- Build pipeline: atomic builds, a build manifest, versioned asset URLs, dates from content.
- Copy workbook: schema that survives content changes; the workbook was not regenerated, so
  rows for strings added on 1 November are not in it yet.
- Machine outputs (feeds, API, llms.txt, calendar) from one content registry; calendar time zones.
- A print stylesheet.
