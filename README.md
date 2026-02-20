# Web3 Growth Lab

Personal brand + product demo site for **Charubak Chakrabarti**.

This repo combines:
- A storytelling-first portfolio website
- Resume and cover letter pages
- A live **Tool Studio** UI to run selected Web3 marketing AI tools directly from browser

## What Is Included

- `index.html`: Main portfolio homepage (story, experience, skills, tool showcase, contact)
- `resume.html`: Web CV page
- `cover-letter.html`: Cover letter page
- `tool-studio.html`: Interactive UI for running tools from browser
- `tool_studio_server.py`: HTTPS API + static server for Tool Studio execution
- `serve.py`: HTTPS static server for main portfolio site
- `css/`: Site styles (`style.css`, `resume.css`, `tool-studio.css`)
- `js/`: Frontend interactions (`main.js`, `tool-studio.js`)
- `assets/`: Media assets (portrait, etc.)

## Product Direction

This project is positioned as a **Web3 Growth Lab**:
- Data-driven marketing credibility
- Narrative strategy + storytelling depth
- AI-powered execution
- Live demonstrations for prospects, hiring managers, and partners

The portfolio is designed to be both:
1. A personal website
2. A demo surface for real automation products

## Live Tool Studio (Plan B Frontend)

Tool Studio exposes browser forms that run local CLI tools in the background and return:
- Live run logs
- Job status polling
- Downloadable output artifacts (Markdown, DOCX, JSON)

Currently wired tools:
- `competitive-deep-dive`
- `protocol-positioning`

Telegram-first tools can stay Telegram-native and be added to web controls later.

## Local Setup

### Requirements

- macOS / Linux shell
- Python 3.9+ (3.12 recommended for tool repos)
- `mkcert` (optional, for trusted local HTTPS certs)

### 1) Run portfolio site

```bash
cd /Users/charubakchakrabarti/dev/portfolio
python3 serve.py
```

Open:
- `https://localhost:8443`

### 2) Run Tool Studio backend

```bash
cd /Users/charubakchakrabarti/dev/portfolio
python3 tool_studio_server.py
```

Open:
- `https://localhost:8450/tool-studio.html`

## Tool Studio API

- `GET /api/health`
- `POST /api/run/<tool>`
- `GET /api/jobs/<job_id>`
- `GET /api/jobs/<job_id>/artifacts/<artifact_id>`

Execution model:
- Each run gets a job ID
- Tool is executed with prefilled stdin mapping
- Stdout is captured as live logs
- Artifact file paths are detected and exposed for download

## Frontend UX Notes

- Scroll reveal and parallax motion are built in (`js/main.js`)
- Responsive layout for mobile + desktop
- Storytelling and data-driven positioning are emphasized above tool showcase
- Hero statistics highlight:
  - users onboarded
  - community built
  - partnerships closed
  - AI tools built

## Deployment Notes

For production hosting:
- Serve static files behind HTTPS
- Run Tool Studio API behind a secure backend host
- Add auth/rate limits before public exposure of execution endpoints
- Configure CORS explicitly for production domains

## Live Domain Deployment (web3growthlab.com)

This repo is configured for GitHub Pages deployment:
- Workflow: `.github/workflows/deploy-pages.yml`
- Custom domain file: `CNAME`
- Jekyll disabled: `.nojekyll`

How it goes live:
1. Push to `main`
2. GitHub Actions deploys to Pages
3. DNS for `web3growthlab.com` points to GitHub Pages

DNS records to add at your registrar:
- `A` record `@` -> `185.199.108.153`
- `A` record `@` -> `185.199.109.153`
- `A` record `@` -> `185.199.110.153`
- `A` record `@` -> `185.199.111.153`
- `CNAME` record `www` -> `charubak.github.io`

After DNS propagates, both of these should work:
- `https://web3growthlab.com`
- `https://www.web3growthlab.com`

## How To Make Future Website Changes

1. Edit files locally in this repo.
2. Preview locally:
   - `python3 serve.py`
   - open `https://localhost:8443`
3. Commit and push to `main`.
4. GitHub Actions auto-deploys the update.

## Suggested Next Steps

- Add authentication to Tool Studio runs
- Add execution queue limits and cancel support
- Add usage analytics dashboard
- Add Telegram bot control panels
- Add one-click report sharing links

## License

Personal project. Rights reserved by owner unless explicitly open-sourced per component.
