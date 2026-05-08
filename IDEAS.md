# Creative Brief Maker — Ideas & Insights

## Insights

- [Self] PDF hyperlinks silently broken — field() helper was XML-escaping pre-built anchor tags, so reference links and inspiration URLs never rendered as clickable links in output (high)
- [Self] No brief preview before generating — user must download the ZIP and open files to see what the output looks like (med)
- [Self] App cold-starts on Render free tier take ~30s — jarring for the first person to open it each morning (med)
- [Self] Draft auto-save stored to localStorage but had no restore prompt on reload — data survived but users couldn't get back to it (med)
- [Self] Script field was a single-line input — multiline scripts were unreadable and hard to edit in the original UI (high)
- [Code] /generate route called request.get_json() without silent=True — returns None on malformed body, causing an unhandled AttributeError in production (high)
- [Code] Brand field used in output filenames with only whitespace stripped — any special character could create path traversal or broken filenames (high)
- [Code] ReportLab Paragraph crashed on & < > characters in concept titles — no XML escaping applied before inserting user text into the PDF story (high)
- [Code] Inspiration URL passed unsanitized into XML href attribute — quotes or spaces in a URL would break the PDF and could inject markup (high)
- [Code] format_vibe field rendered twice in every brief — once as "Concept:" in Section 1 and again as the first performance bullet in Section 3 (med)
- [Code] Dead imports (tempfile, os) left in brief_parser.py; datetime imported inside a function instead of at module level (low)
- [Code] Long scripts overflow a single PDF page with no fallback — content gets clipped with no warning to the user (med)
- [Code] DOCX table content extracted after all paragraph content — loses in-document order for submissions that interleave tables and text (med)
- [User] Team had no way to access the tool — it only ran on localhost, blocking anyone who wasn't the developer (high)
- [User] GitHub auth via terminal password prompt blocked deployment — terminal hides input with no feedback, which looked broken to a non-technical user (med)
- [Market] Linear-style priority system (critical / important / optional) applied to every brief field so editors know what must be filled vs. what's nice-to-have (med)
- [Market] Notion-style contextual hints added as a ? toggle per field — surfaces guidance in context without cluttering the default view (med)
- [Market] Google Docs-style auto-save with timestamp indicator added — draft persists to localStorage every 5s so no work is lost on accidental close (low)
- [Market] Asana native integration instead of just file export — creates a task per concept directly in the Videos & GIFs board with PDF and DOCX attached (high)

## What I shipped

- **Fixed PDF hyperlink rendering** — rewrote reference link and inspiration URL output to bypass the field() helper and build Paragraph XML directly, so links are actually clickable in the PDF. Came from [Self] + [Code] insights.
- **Full React UI rewrite** — replaced the vanilla JS single-page app with a React component: 2-column field grid, script textarea with live word count and duration estimate, priority badges, contextual hints, orientation dropdown, functional global settings panel, and a real Step 3 done state. Came from [Self] insight.
- **Fixed all 10 production code issues from senior engineer review** — including the get_json() null check, path traversal in filenames, XML escaping throughout the PDF generator, URL sanitization, duplicate format_vibe field, and dead imports. Came from [Code] insights.
- **Asana task creation per concept** — added /create-asana-tasks endpoint that creates one task per script in the Videos & GIFs board, writes structured notes, and attaches both the PDF and DOCX brief. Toggle is on by default per card, with live connection status. Came from [Market] insight.
- **Deployed to Render with GitHub auto-deploy** — app is now live at a shared URL the whole team can use; any push to main redeploys automatically in ~2 minutes. Came from [User] insight.
