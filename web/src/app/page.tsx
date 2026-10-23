"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type DocHit = {
  id: number;
  title: string;
  url: string;
  ticker?: string | null;
  source?: string;
  content_preview?: string;
  content_chars?: number;
  relevant_titles_only?: boolean;
  relevant_with_content?: boolean;
};

type AnswerBlock = {
  answer_markdown: string;
  relevant_ids: number[];
  not_relevant_ids: number[];
};

type QueryResult = {
  query: string;
  top5: DocHit[];
  titles_only: AnswerBlock;
  with_content: AnswerBlock;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

const FALLBACK_SAMPLES = [
  "How is Apple's services revenue growing?",
  "What did NVIDIA say about data center demand?",
  "Summarize recent bank earnings and net interest margin trends",
];

function renderMarkdownLite(md: string) {
  // Tiny markdown: paragraphs + [text](url) links only
  const escaped = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const withLinks = escaped.replace(
    /\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
  );
  return withLinks
    .split(/\n{2,}/)
    .map((p) => `<p class="mb-3 leading-relaxed">${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");
}

function Badge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        ok
          ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
          : "bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/30"
      }`}
    >
      {label}
    </span>
  );
}

function DocCard({
  doc,
  mode,
}: {
  doc: DocHit;
  mode: "titles" | "content";
}) {
  const relevant =
    mode === "titles" ? doc.relevant_titles_only : doc.relevant_with_content;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--panel-2)] p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge
          ok={!!relevant}
          label={relevant ? "relevant" : "not relevant"}
        />
        {doc.ticker ? (
          <span className="rounded bg-white/5 px-1.5 py-0.5 text-xs text-[var(--muted)]">
            {doc.ticker}
          </span>
        ) : null}
        <span className="text-xs text-[var(--muted)]">{doc.source}</span>
      </div>
      <a
        href={doc.url}
        target="_blank"
        rel="noreferrer"
        className="text-sm font-medium text-[var(--accent-2)] hover:text-[var(--accent)]"
      >
        {doc.title}
      </a>
    </div>
  );
}

export default function Home() {
  const [query, setQuery] = useState(FALLBACK_SAMPLES[0]);
  const [samples, setSamples] = useState<string[]>(FALLBACK_SAMPLES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [health, setHealth] = useState<{
    ok: boolean;
    records?: number;
    model?: string;
    has_api_key?: boolean;
  } | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ ok: false }));
    fetch(`${API_BASE}/samples`)
      .then((r) => r.json())
      .then((d) => {
        if (Array.isArray(d.queries) && d.queries.length) setSamples(d.queries);
      })
      .catch(() => undefined);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || res.statusText || "Query failed");
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const statusLine = useMemo(() => {
    if (!health) return "Checking API…";
    if (!health.ok) return "API offline — start uvicorn on :8000";
    const key = health.has_api_key ? "key ok" : "missing API key";
    return `${health.records ?? "?"} records · ${health.model ?? "model?"} · ${key}`;
  }, [health]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <header className="mb-8">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--accent)]">
              RAG prototype
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">
              EarningsDecoder
            </h1>
          </div>
          <p className="rounded-full border border-[var(--border)] bg-[var(--panel)] px-3 py-1 text-xs text-[var(--muted)]">
            {statusLine}
          </p>
        </div>
        <p className="max-w-2xl text-sm text-[var(--muted)]">
          Ask about stocks and earnings. The app retrieves the top 5 matching
          headlines, answers from titles only, then fetches each page and
          answers again from the content — side by side.
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-4 shadow-xl shadow-black/20"
      >
        <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Query
        </label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          className="w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none ring-[var(--accent)] focus:ring-1"
          placeholder="e.g. What are analysts saying about NVIDIA data center growth?"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {samples.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setQuery(s)}
              className="rounded-full border border-[var(--border)] bg-white/5 px-3 py-1 text-xs text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--text)]"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading || query.trim().length < 3}
            className="rounded-xl bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Retrieving + answering…" : "Run comparison"}
          </button>
          <span className="text-xs text-[var(--muted)]">
            Uses Grok via xAI · embeddings are local MiniLM
          </span>
        </div>
      </form>

      {error ? (
        <div className="mb-6 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-8 text-center text-sm text-[var(--muted)]">
          Searching FAISS → calling Grok on titles → fetching 5 pages → calling
          Grok on content. Usually 15–40 seconds.
        </div>
      ) : null}

      {result ? (
        <section className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-2">
            <article className="rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-5">
              <h2 className="mb-1 text-lg font-semibold text-sky-300">
                Titles only
              </h2>
              <p className="mb-4 text-xs text-[var(--muted)]">
                Context = title + URL for each of the top 5 (homework steps 3–4)
              </p>
              <div
                className="prose-answer mb-5 text-sm"
                dangerouslySetInnerHTML={{
                  __html: renderMarkdownLite(
                    result.titles_only.answer_markdown || "_No answer_"
                  ),
                }}
              />
              <div className="space-y-2">
                {result.top5.map((d) => (
                  <DocCard key={`t-${d.id}`} doc={d} mode="titles" />
                ))}
              </div>
            </article>

            <article className="rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-5">
              <h2 className="mb-1 text-lg font-semibold text-teal-300">
                With page content
              </h2>
              <p className="mb-4 text-xs text-[var(--muted)]">
                Same top 5, after HTML strip / truncate (homework steps 5–7)
              </p>
              <div
                className="prose-answer mb-5 text-sm"
                dangerouslySetInnerHTML={{
                  __html: renderMarkdownLite(
                    result.with_content.answer_markdown || "_No answer_"
                  ),
                }}
              />
              <div className="space-y-2">
                {result.top5.map((d) => (
                  <DocCard key={`c-${d.id}`} doc={d} mode="content" />
                ))}
              </div>
            </article>
          </div>
        </section>
      ) : null}

      <footer className="mt-12 border-t border-[var(--border)] pt-4 text-xs text-[var(--muted)]">
        EarningsDecoder · local demo for AI class homework ·{" "}
        <a
          className="text-[var(--accent-2)] hover:underline"
          href="https://github.com/Cael-Pairrett/EarningsDecoder"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </footer>
    </main>
  );
}
