# EarningsDecoder — agent notes

## Run locally

```bash
# 1) API
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# first time only if index missing:
python scripts/build_index.py
uvicorn app.main:app --reload --port 8000

# 2) Web (other terminal)
cd web
npm install
npm run dev
```

Open http://localhost:3000. Put `XAI_API_KEY` in a root `.env` (see `.env.example`).

## Rebuild data / index

```bash
python api/scripts/collect_records.py
python api/scripts/build_index.py
```

## Stack

- FastAPI + LangChain + FAISS + sentence-transformers MiniLM
- Next.js App Router UI
- Grok via `https://api.x.ai/v1`
