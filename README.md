# EarningsDecoder

A small stock & earnings **RAG** app: ask a question, retrieve the top 5 matching headlines from a local FAISS index, get a Grok answer from **titles only**, then fetch those pages and get a second answer from the **page content** — shown side by side.

Built as a homework prototype (not a notebook). Repo: public demo you can clone and run.

## What it does

1. Loads 400+ title+URL records (Yahoo Finance news + company IR pages)
2. Embeds titles with local `all-MiniLM-L6-v2` into FAISS
3. On each query: top-5 retrieve → Grok (titles) → download/clean HTML → Grok (content)
4. UI marks which of the 5 were relevant vs not, with clickable links

## Homework checklist

| Step | Covered by |
|------|------------|
| 1. ≥100 online records (title + URL) | `api/data/records.json` + `api/scripts/collect_records.py` |
| 2. Vector store, top 5 | LangChain + FAISS (`api/app/rag.py`) |
| 3–4. Query → top 5 → LLM on titles; relevance + links | `/query` + left column |
| 5. Fetch + strip HTML for each top-5 URL | `api/app/content.py` |
| 6. LLM on content (truncated); length limited in prompt | right column |
| 7. Side-by-side titles vs content | Next.js UI |

## Quick start

**Needs:** Python 3.11+, Node 20+, an [xAI API key](https://console.x.ai/)

```bash
git clone https://github.com/Cael-Pairrett/EarningsDecoder.git
cd EarningsDecoder
cp .env.example .env
# edit .env and paste XAI_API_KEY=...
```

**API**

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Index is already committed; rebuild with: python scripts/build_index.py
uvicorn app.main:app --reload --port 8000
```

**Web** (second terminal)

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Sample queries are buttons under the search box.

## Env vars

| Var | Required | Notes |
|-----|----------|--------|
| `XAI_API_KEY` | yes | Also accepts `GROK_API_KEY` |
| `GROK_MODEL` | no | Default `grok-4-latest` (change if your key lists something else) |
| `NEXT_PUBLIC_API_BASE` | no | Default `http://127.0.0.1:8000` |

Embeddings are **local** — no second paid key.

## Project layout

```
api/          FastAPI, FAISS, collect + build scripts
web/          Next.js App Router UI
.env.example  keys / model
```

## Notes

- Titles work offline from the committed JSON + FAISS index. Page content is fetched live, so some sites may block or return thin text — the answer will say so.
- Collector skips Hacker News and WSJ US Business links.
- Don’t commit `.env`.

## License

MIT — school project, use freely.
