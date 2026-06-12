# Webinar microsite — *The F1 Playbook for AI-Assisted Engineering*

A self-paced, single-page masterclass site modelled on the Desteia structure
(module sidebar + per-module video, takeaways, results, FAQ, CTA) and styled in
the Quix brand system (orange `#FF8400`, near-black, Geist / Geist Mono, corner
brackets, tram lines).

Everything is in one self-contained [index.html](index.html) — no build step.
Open it directly or visit the deployed copy.

## Deploy

Published via GitHub Pages by [`.github/workflows/pages.yml`](../../.github/workflows/pages.yml),
which stages this folder at **`/masterclass/`**:

> `https://quixio.github.io/webinar-AI/masterclass/`

The slide deck stays at the site root; this microsite lives under `/masterclass/`.
A push to `main` touching `webinar-offline/site/**` redeploys automatically. To
promote the microsite to the site root instead, change the workflow's copy step.

## What to fill in before going live

Open the `<script>` config block at the bottom of `index.html`:

1. **`VIDEOS`** — one YouTube video ID per module (playlist style, one video each).
   Leave `''` to show the "coming soon" placeholder.
   ```js
   const VIDEOS = { 1:'abc123', 2:'…', 3:'…', 4:'…', 5:'…', 6:'…', 7:'…' };
   ```

That's the only required edit. Everything else is wired.

## Forms — Google Form integration

All lead capture feeds one Google Form
(`https://forms.gle/HvGYNvjH4Shv5Gsc7`):

- **Module 7** embeds the form as an `<iframe>`. Google stores responses and shows
  its own confirmation, which hands the user the repo:
  `https://github.com/quixio/webinar-AI`.
- The per-module **"Ask a question"** links (rungs 3–6) open the same form in a
  new tab.
- All **"Book a demo"** / **"Get the code"** buttons route to module 7 (the form).
  There's no separate demo-booking URL yet — point them at a real Calendly later
  if you want a distinct demo flow.

If you ever change the Google Form's questions, the embed keeps working (it loads
the live form); no field mapping is hard-coded here.

## Content

All copy is drawn from the real webinar transcript
(`../recording/…transcript.vtt`, kept local — the `recording/` folder is
gitignored). The seven modules follow the five-rung ladder: chatbot → agentic →
skills → domain knowledge → AI harness, plus an intro, the sim-to-real challenge,
and a Q&A/form close. FAQs are seeded from the live Q&A.

The three results scatter plots (Rungs 1/2/3) are reused verbatim from
`../../webinar-presentation/modules-results/progressive.html`.

## Design notes

- **CTAs:** modules 1–2 carry a slim "Book a demo" card; rungs 3–6 add an "Ask a
  question" link to the form; module 7 is the embedded form.
- Navigation is one-module-at-a-time with a sticky sidebar, prev/next, keyboard
  arrows, deep-linkable hashes (`#module-3`), and a progress bar.
- Videos lazy-load per module (no 7 iframes at once).
