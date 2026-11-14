MODEL: Opus. Paste everything below the line into Claude Code after /clear.
---

Write the methodology report as a single self-contained HTML file, reports/report.html, designed to print to an
A4 PDF of 10–12 pages. I will print it to PDF from the browser myself.

## Read
CLAUDE.md (especially the brief's required report items), DECISIONS.md, section 6 of
docs/METHODOLOGY_SPEC.md (report plan), the final top-10 CSVs, and the outputs/ tables and figures.

## Rules
- Follow the outline in spec section 6. The report's headings must map clearly to the brief's five required
  items: pressure definition; performance measurement; fair comparisons; evidence for the top 10; reliability
  and limitations. Add a one-page executive summary first, and "How each pick strengthens RR" before the appendix.
- Every number must come from a file in outputs/. Don't type a number from memory. If a number you need doesn't
  exist, write a small script (src/9x_report_numbers.py) that produces it.
- Embed the figures as base64 images, so the HTML is one file. Use print CSS: A4, sensible margins, page breaks
  before main sections, no figure split across pages, page numbers if possible.
- Writing style: plain, confident, specific. Explain each metric in one sentence a cricket analyst would accept.
  No hype words. Use short paragraphs and tables wherever a table is clearer.
- Top-10 tables: rank, player, team(s), role, rating, rank interval, pressure balls, key pressure stats, and a
  one-line "why".
- Limitations section: honest and specific, including the time-split result, sample sizes, missing venue names,
  and DLS edge cases.
- Appendix: reproducibility (repo link placeholder {{REPO_URL}}, how to run), full eligibility rules, and the
  decision log summary.

Build it, then open it and check it page by page: layout, page breaks, figure readability, and that the numbers
match outputs/. List anything you could not verify.
