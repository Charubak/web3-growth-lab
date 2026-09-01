# CLAUDE.md

This file is the repo-specific handoff for future Claude or Codex work on `web3-growth-lab`.
Update it after each meaningful iteration so the website keeps moving in one direction.

## What This Site Is

This is not a generic personal site.
It is Charubak Chakrabarti's portfolio and hiring surface.

Primary goal (updated 2026-09-01):
- present Charubak as Growth Lead at Monorail (swap aggregator on Monad) and document what he ships there
- keep him credible for future senior growth roles without reading as job-seeking

Secondary goal:
- show that he is not just a marketer, but a marketer who builds useful AI systems for marketing work

Important positioning rule:
- lead with `Web3 growth lead` / `marketing lead`
- support that with `operator who builds` and `marketer who ships tools`
- do not accidentally reposition him into "AI engineer looking for engineering roles"
- audience is technically literate founders, hiring managers, and early-stage operators who respect real work and real numbers
- builder angle should feel like operating leverage, not a career pivot away from marketing

## Tone And Aesthetic

- dark editorial aesthetic
- warm amber / orange acceptable, avoid generic purple-cyan Web3 look
- direct, sharp, useful copy
- no padded corporate AI language
- no em dashes in user-facing writing

## Portfolio Narrative

The site should communicate:
- strong Web3 / DeFi domain depth
- measurable growth outcomes
- systems thinking
- technical leverage through tools

The tools are not random side projects.
They should read as operating leverage that makes Charubak better at marketing.

## Source Of Truth For Writing Links

Published writing should point to real public URLs, not placeholders.

Current Medium profile:
- https://medium.com/@onchaineconomist

## Recent Iteration Notes

### 2026-04-22

Implemented by Codex in response to a portfolio audit and follow-up direction from Charubak.

Changes made:
- fixed homepage metadata to use `web3growthlab.com` instead of GitHub Pages URLs
- added canonical tags on homepage, CV, and cover letter
- added `robots.txt`
- added `sitemap.xml`
- replaced placeholder writing links with real Medium article URLs from `@onchaineconomist`
- made homepage tool cards clickable
- added direct repo links for each tool
- deep-linked demo tools into exact Tool Studio states using URL hashes
- changed `AI Content Machine` card to open the actual app directly
- added hash-aware Tool Studio state so links like `tool-studio.html#positioning` open the correct tool
- tightened tool section copy so it reads more like employer-facing proof than a feature dump
- removed em dashes and en dashes from user-facing website copy, including shipped app bundles, to match Charubak's writing preference
- rewrote homepage, studio, CV, and cover-letter copy using the principles from `ai-content-machine/README.md` and `voices/charubak/voice_v1.md`
- sharpened the narrative around "senior Web3 growth marketer with receipts" and used the builder layer as the differentiator
- pushed the writing toward specific outcomes, founder-facing clarity, and less generic marketing language
- upgraded homepage tool-card headlines to focus more on business outcome than project name
- added mini case-study strips to Autonity and RFX so the experience section shows challenge, move, and result instead of only role summaries
- reframed the writing section as point of view plus proof, with short "why this matters" context beneath each featured article
- moved `AI Content Machine` and `Ad Creative Machine` to the top of the homepage tools section so the flagship AI products lead the portfolio story
- added a homepage card and repo link for `Ad Creative Machine`
- expanded the homepage bio to focus more on Web3 depth, AI tool-building vision, and personal texture, with less emphasis on edtech history
- updated Tool Studio so `AI Content Machine` is the default first tool, `Ad Creative Machine` is second, and both hosted tools expose direct repo links from the launch view

### 2026-09-01

Implemented by Claude (Cowork) after Charubak joined Monorail as Growth Lead (mid-July 2026).

Changes made:
- replaced OPEN_TO_ROLES status and job-seeking copy sitewide with current Growth Lead @ Monorail positioning
- updated head metadata, OG, and Twitter cards to the Monorail role
- rewrote hero subtitle to lead with Monorail and Monad
- added Monorail as role_01 in experience (Journey campaign, Monad Open trading comp), closed Autonity as 2024 to 26, renumbered roles to 5
- added agent-skills tool card (01/) for the Claude skills suite; renumbered tool cards to 10
- refreshed ticker, stats (10+ AI systems and skills), story bio column, and third pillar (current seat)
- rewrote contact section: no longer looking, added monorail.xyz link, changed hire-me CTAs to connect
- added Claude Agent Skills, Dune Pipelines, DEX Aggregation, Monad Ecosystem to skills grid
- removed remaining em dashes in tool copy (perp-pulse)
- campaign facts kept to publicly visible ones; no internal funnel or baseline numbers published

## Next Likely Improvements

- keep improving tool card copy toward business outcome and operator leverage
- consider whether Tool Studio should remain key-gated in-browser or be reframed as a safer showcase
- add more public proof artifacts such as case studies or project walkthroughs
- keep future copy close to the voice document rules: specific numbers, direct claims, minimal fluff, no generic AI-marketer language
- keep this file updated after every meaningful site iteration
