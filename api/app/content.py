"""Download and clean page text for Step 5."""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

UA = (
    "EarningsDecoder/1.0 (+https://github.com/Cael-Pairrett/EarningsDecoder; "
    "educational homework prototype)"
)


def strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_page_text(url: str, max_chars: int = 6000, timeout: float = 12.0) -> str:
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text" not in ctype and "xml" not in ctype:
                return f"[Skipped non-text content: {ctype or 'unknown'}]"
            text = strip_html(resp.text)
            if not text:
                return "[No readable text extracted from page]"
            if len(text) > max_chars:
                return text[:max_chars] + "\n\n[…truncated for length…]"
            return text
    except Exception as e:
        return f"[Failed to fetch content: {type(e).__name__}: {e}]"
