"""FAISS + LangChain retrieval and dual Grok answering."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from openai import OpenAI

from .config import Settings, get_settings
from .content import fetch_page_text

_embeddings: HuggingFaceEmbeddings | None = None
_store: FAISS | None = None


def get_embeddings(settings: Settings | None = None) -> HuggingFaceEmbeddings:
    global _embeddings
    settings = settings or get_settings()
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def load_records(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def records_to_documents(records: list[dict[str, Any]]) -> list[Document]:
    docs = []
    for r in records:
        meta = {
            "id": r.get("id"),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "ticker": r.get("ticker"),
            "source": r.get("source"),
        }
        # Embed title (+ ticker) so retrieval works offline from titles alone
        page = r.get("title", "")
        if r.get("ticker"):
            page = f"{page} | ticker:{r['ticker']}"
        docs.append(Document(page_content=page, metadata=meta))
    return docs


def build_index(settings: Settings | None = None, force: bool = False) -> FAISS:
    global _store
    settings = settings or get_settings()
    settings.faiss_dir.mkdir(parents=True, exist_ok=True)
    index_file = settings.faiss_dir / "index.faiss"
    if index_file.exists() and not force:
        _store = FAISS.load_local(
            str(settings.faiss_dir),
            get_embeddings(settings),
            allow_dangerous_deserialization=True,
        )
        return _store

    records = load_records(settings.records_path)
    docs = records_to_documents(records)
    store = FAISS.from_documents(docs, get_embeddings(settings))
    store.save_local(str(settings.faiss_dir))
    _store = store
    return store


def get_store(settings: Settings | None = None) -> FAISS:
    global _store
    if _store is None:
        return build_index(settings)
    return _store


def retrieve_top_k(query: str, k: int = 5, settings: Settings | None = None) -> list[Document]:
    store = get_store(settings)
    return store.similarity_search(query, k=k)


def make_llm(settings: Settings | None = None) -> ChatOpenAI:
    settings = settings or get_settings()
    if not settings.api_key:
        raise RuntimeError(
            "Missing XAI_API_KEY (or GROK_API_KEY). Put it in the project .env file."
        )
    return ChatOpenAI(
        model=settings.grok_model,
        api_key=settings.api_key,
        base_url=settings.xai_base_url,
        temperature=0.2,
        max_tokens=900,
    )


TITLES_PROMPT = """You are EarningsDecoder, a stock/earnings research assistant.

You are given a user question and exactly 5 candidate documents. Each document has an id, title, and url.
You may ONLY use the titles and urls as context (no article body).

Tasks:
1. Decide which documents are relevant to answering the question and which are not.
2. Write a concise answer (max ~180 words) based only on relevant titles/urls.
3. Include at least one markdown link [title](url) for every relevant document you used.
4. If titles alone are too thin to answer, say what is unclear and still list relevance.

Return JSON with this exact shape:
{{
  "answer_markdown": "string with markdown links",
  "relevant_ids": [int, ...],
  "not_relevant_ids": [int, ...]
}}

Question: {question}

Documents:
{docs_block}
"""

CONTENT_PROMPT = """You are EarningsDecoder, a stock/earnings research assistant.

You are given a user question and exactly 5 candidate documents. Each has id, title, url, and extracted page content (may be truncated or a fetch-error note).

Tasks:
1. Decide which documents are relevant vs not.
2. Write a concise answer (max ~220 words) using the page content of relevant docs.
3. Include markdown link(s) [title](url) to every relevant document you relied on.
4. Do not invent facts that are not supported by the provided content. If content failed to fetch, say so.

Return JSON with this exact shape:
{{
  "answer_markdown": "string with markdown links",
  "relevant_ids": [int, ...],
  "not_relevant_ids": [int, ...]
}}

Question: {question}

Documents:
{docs_block}
"""


def _docs_block_titles(docs: list[Document]) -> str:
    parts = []
    for d in docs:
        parts.append(
            f"- id={d.metadata.get('id')}\n"
            f"  title: {d.metadata.get('title')}\n"
            f"  url: {d.metadata.get('url')}"
        )
    return "\n".join(parts)


def _docs_block_content(docs: list[Document], contents: dict[int, str]) -> str:
    parts = []
    for d in docs:
        did = d.metadata.get("id")
        parts.append(
            f"- id={did}\n"
            f"  title: {d.metadata.get('title')}\n"
            f"  url: {d.metadata.get('url')}\n"
            f"  content:\n{contents.get(did, '[no content]')}"
        )
    return "\n\n".join(parts)


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip markdown fences if present
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Best-effort: find first {...}
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {
            "answer_markdown": text,
            "relevant_ids": [],
            "not_relevant_ids": [],
        }


def _call_llm_json(llm: ChatOpenAI, prompt: str) -> dict[str, Any]:
    msg = llm.invoke(prompt)
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    return _parse_llm_json(content)


def run_query(question: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    docs = retrieve_top_k(question, k=5, settings=settings)
    llm = make_llm(settings)

    titles_raw = _call_llm_json(
        llm,
        TITLES_PROMPT.format(question=question, docs_block=_docs_block_titles(docs)),
    )

    # Step 5: fetch content for each of the top 5
    contents: dict[int, str] = {}
    top5_payload = []
    for d in docs:
        did = int(d.metadata.get("id"))
        url = d.metadata.get("url") or ""
        text = fetch_page_text(url, max_chars=settings.max_content_chars)
        contents[did] = text
        top5_payload.append(
            {
                "id": did,
                "title": d.metadata.get("title"),
                "url": url,
                "ticker": d.metadata.get("ticker"),
                "source": d.metadata.get("source"),
                "content_preview": text[:400],
                "content_chars": len(text),
            }
        )

    content_raw = _call_llm_json(
        llm,
        CONTENT_PROMPT.format(
            question=question,
            docs_block=_docs_block_content(docs, contents),
        ),
    )

    titles_relevant = set(titles_raw.get("relevant_ids") or [])
    content_relevant = set(content_raw.get("relevant_ids") or [])

    for item in top5_payload:
        item["relevant_titles_only"] = item["id"] in titles_relevant
        item["relevant_with_content"] = item["id"] in content_relevant

    return {
        "query": question,
        "top5": top5_payload,
        "titles_only": {
            "answer_markdown": titles_raw.get("answer_markdown", ""),
            "relevant_ids": list(titles_relevant),
            "not_relevant_ids": list(titles_raw.get("not_relevant_ids") or []),
        },
        "with_content": {
            "answer_markdown": content_raw.get("answer_markdown", ""),
            "relevant_ids": list(content_relevant),
            "not_relevant_ids": list(content_raw.get("not_relevant_ids") or []),
        },
    }
