#!/usr/bin/env python3
"""Collect ≥100 stock/earnings title+URL records for EarningsDecoder.

Sources: Yahoo Finance news (per ticker) + SEC EDGAR filing landing pages.
Avoids Hacker News and WSJ US Business.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "records.json"

# Diversified large-cap + popular names for earnings coverage
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX",
    "AMD", "INTC", "CRM", "ORCL", "ADBE", "CSCO", "AVGO", "QCOM",
    "JPM", "BAC", "GS", "V", "MA", "WFC", "C",
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY",
    "XOM", "CVX", "COP",
    "WMT", "COST", "TGT", "HD", "NKE", "SBUX", "MCD",
    "DIS", "CMCSA", "T", "VZ",
    "BA", "CAT", "GE", "UPS", "F", "GM",
    "KO", "PEP", "PG", "CL",
]

UA = "EarningsDecoder/1.0 (educational RAG prototype; contact: github.com/Cael-Pairrett/EarningsDecoder)"


def fetch_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def yahoo_news(ticker: str) -> list[dict]:
    """Yahoo Finance quote news endpoint — title + link."""
    url = (
        "https://query2.finance.yahoo.com/v1/finance/search"
        f"?q={urllib.parse.quote(ticker)}&quotesCount=0&newsCount=10&listsCount=0"
    )
    # Prefer the dedicated news crumb-free endpoint when available
    news_url = (
        "https://query1.finance.yahoo.com/v2/finance/news"
        f"?symbols={urllib.parse.quote(ticker)}&count=12"
    )
    records = []
    for endpoint in (news_url, url):
        try:
            data = fetch_json(endpoint)
        except Exception:
            continue
        items = []
        if isinstance(data, dict):
            items = (
                data.get("items")
                or data.get("Content", {}).get("result")
                or data.get("news")
                or data.get("finance", {}).get("result", [{}])[0].get("news", [])
                or []
            )
            if not items and "quotes" in data:
                items = data.get("news", [])
        for item in items:
            title = (item.get("title") or item.get("headline") or "").strip()
            link = (
                item.get("link")
                or item.get("url")
                or item.get("clickThroughUrl", {}).get("url")
                or ""
            )
            if isinstance(link, dict):
                link = link.get("url") or ""
            if not title or not link:
                continue
            # Skip blocked sources from the assignment list
            low = link.lower()
            if "news.ycombinator.com" in low or "wsj.com" in low:
                continue
            records.append(
                {
                    "title": title,
                    "url": link,
                    "ticker": ticker,
                    "source": "yahoo_finance",
                }
            )
        if records:
            break
    return records


def yahoo_search_news(ticker: str) -> list[dict]:
    """Fallback: Yahoo search API news results."""
    url = (
        "https://query2.finance.yahoo.com/v1/finance/search"
        f"?q={urllib.parse.quote(ticker + ' earnings')}"
        "&quotesCount=1&newsCount=15&listsCount=0"
    )
    try:
        data = fetch_json(url)
    except Exception:
        return []
    records = []
    for item in data.get("news", []) or []:
        title = (item.get("title") or "").strip()
        link = item.get("link") or ""
        if not title or not link:
            continue
        low = link.lower()
        if "news.ycombinator.com" in low or "wsj.com" in low:
            continue
        records.append(
            {
                "title": title,
                "url": link,
                "ticker": ticker,
                "source": "yahoo_search",
            }
        )
    return records


def sec_company_tickers() -> dict[str, str]:
    """Map ticker -> CIK (zero-padded)."""
    url = "https://www.sec.gov/files/company_tickers.json"
    data = fetch_json(url)
    out = {}
    for row in data.values():
        t = str(row.get("ticker", "")).upper()
        cik = str(row.get("cik_str", "")).zfill(10)
        if t and cik:
            out[t] = cik
    return out


def sec_recent_filings(cik: str, ticker: str, limit: int = 4) -> list[dict]:
    """Recent 10-K / 10-Q / 8-K filing document URLs from EDGAR submissions."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        data = fetch_json(url)
    except Exception:
        return []
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primaries = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])
    descriptions = recent.get("primaryDocDescription", [])
    records = []
    wanted = {"10-K", "10-Q", "8-K", "6-K", "20-F"}
    for i, form in enumerate(forms):
        if form not in wanted:
            continue
        if len(records) >= limit:
            break
        acc = accessions[i].replace("-", "")
        primary = primaries[i]
        date = dates[i] if i < len(dates) else ""
        desc = descriptions[i] if i < len(descriptions) else form
        file_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{primary}"
        title = f"{ticker} {form} filed {date}: {desc}".strip()
        records.append(
            {
                "title": title,
                "url": file_url,
                "ticker": ticker,
                "source": "sec_edgar",
                "form": form,
                "filing_date": date,
            }
        )
    return records


def company_ir_pages() -> list[dict]:
    """Static IR / earnings pages for major companies (title + URL)."""
    pages = [
        ("Apple Investor Relations", "https://investor.apple.com/investor-relations/default.aspx", "AAPL"),
        ("Apple Press Releases", "https://www.apple.com/newsroom/", "AAPL"),
        ("Microsoft Investor Relations", "https://www.microsoft.com/en-us/investor", "MSFT"),
        ("Microsoft Earnings Releases", "https://www.microsoft.com/en-us/investor/earnings/fy-2025-q4/press-release-webcast", "MSFT"),
        ("Alphabet Investor Relations", "https://abc.xyz/investor/", "GOOGL"),
        ("Amazon Investor Relations", "https://ir.aboutamazon.com/", "AMZN"),
        ("Meta Investor Relations", "https://investor.atmeta.com/", "META"),
        ("NVIDIA Investor Relations", "https://investor.nvidia.com/home/default.aspx", "NVDA"),
        ("Tesla Investor Relations", "https://ir.tesla.com/", "TSLA"),
        ("Netflix Investor Relations", "https://ir.netflix.net/ir-overview/profile/default.aspx", "NFLX"),
        ("AMD Investor Relations", "https://ir.amd.com/", "AMD"),
        ("Intel Investor Relations", "https://www.intc.com/", "INTC"),
        ("Salesforce Investor Relations", "https://investor.salesforce.com/", "CRM"),
        ("Oracle Investor Relations", "https://investor.oracle.com/", "ORCL"),
        ("Adobe Investor Relations", "https://www.adobe.com/investor-relations.html", "ADBE"),
        ("JPMorgan Investor Relations", "https://www.jpmorganchase.com/ir", "JPM"),
        ("Bank of America Investor Relations", "https://investor.bankofamerica.com/", "BAC"),
        ("Goldman Sachs Investor Relations", "https://www.goldmansachs.com/investor-relations/", "GS"),
        ("Visa Investor Relations", "https://investor.visa.com/", "V"),
        ("Mastercard Investor Relations", "https://investor.mastercard.com/", "MA"),
        ("Johnson & Johnson Investor Relations", "https://www.investor.jnj.com/", "JNJ"),
        ("UnitedHealth Investor Relations", "https://www.unitedhealthgroup.com/investors.html", "UNH"),
        ("Pfizer Investor Relations", "https://investors.pfizer.com/", "PFE"),
        ("ExxonMobil Investor Relations", "https://investor.exxonmobil.com/", "XOM"),
        ("Chevron Investor Relations", "https://www.chevron.com/investors", "CVX"),
        ("Walmart Investor Relations", "https://stock.walmart.com/", "WMT"),
        ("Costco Investor Relations", "https://investor.costco.com/", "COST"),
        ("Home Depot Investor Relations", "https://ir.homedepot.com/", "HD"),
        ("Nike Investor Relations", "https://investors.nike.com/", "NKE"),
        ("Starbucks Investor Relations", "https://investor.starbucks.com/", "SBUX"),
        ("McDonald's Investor Relations", "https://corporate.mcdonalds.com/corpmcd/investors.html", "MCD"),
        ("Disney Investor Relations", "https://thewaltdisneycompany.com/investor-relations/", "DIS"),
        ("Boeing Investor Relations", "https://investors.boeing.com/", "BA"),
        ("Coca-Cola Investor Relations", "https://investors.coca-colacompany.com/", "KO"),
        ("PepsiCo Investor Relations", "https://www.pepsico.com/investors", "PEP"),
        ("Procter & Gamble Investor Relations", "https://www.pginvestor.com/", "PG"),
        ("Broadcom Investor Relations", "https://investors.broadcom.com/", "AVGO"),
        ("Cisco Investor Relations", "https://investor.cisco.com/", "CSCO"),
        ("Qualcomm Investor Relations", "https://investor.qualcomm.com/", "QCOM"),
        ("Berkshire Hathaway Reports", "https://www.berkshirehathaway.com/reports.html", "BRK.B"),
    ]
    return [
        {"title": title, "url": url, "ticker": ticker, "source": "investor_relations"}
        for title, url, ticker in pages
    ]


def dedupe(records: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in records:
        key = (r["url"].rstrip("/").lower(), r["title"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_records: list[dict] = []
    all_records.extend(company_ir_pages())

    print("Fetching SEC company tickers…")
    try:
        cik_map = sec_company_tickers()
    except Exception as e:
        print(f"  SEC tickers failed: {e}")
        cik_map = {}

    for i, ticker in enumerate(TICKERS):
        print(f"[{i+1}/{len(TICKERS)}] {ticker}")
        # Yahoo news
        got = yahoo_news(ticker)
        if len(got) < 3:
            got.extend(yahoo_search_news(ticker))
        all_records.extend(got)
        # SEC filings
        cik = cik_map.get(ticker)
        if cik:
            try:
                all_records.extend(sec_recent_filings(cik, ticker, limit=3))
                time.sleep(0.15)  # be polite to SEC
            except Exception as e:
                print(f"  SEC {ticker}: {e}")
        time.sleep(0.08)

    # Extra earnings-focused search queries for diversity
    extra_queries = [
        "S&P 500 earnings season",
        "Federal Reserve interest rates stocks",
        "semiconductor chip demand earnings",
        "AI data center capital expenditure",
        "oil prices energy stocks earnings",
        "retail same store sales earnings",
        "bank net interest margin earnings",
        "EV deliveries Tesla Rivian",
        "cloud computing revenue growth",
        "pharmaceutical drug pipeline FDA",
    ]
    for q in extra_queries:
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={urllib.parse.quote(q)}&quotesCount=0&newsCount=12&listsCount=0"
        )
        try:
            data = fetch_json(url)
            for item in data.get("news", []) or []:
                title = (item.get("title") or "").strip()
                link = item.get("link") or ""
                if not title or not link:
                    continue
                low = link.lower()
                if "news.ycombinator.com" in low or "wsj.com" in low:
                    continue
                all_records.append(
                    {
                        "title": title,
                        "url": link,
                        "ticker": None,
                        "source": "yahoo_topic",
                        "topic": q,
                    }
                )
        except Exception as e:
            print(f"  topic '{q}': {e}")
        time.sleep(0.1)

    records = dedupe(all_records)
    # Assign stable ids
    for idx, r in enumerate(records):
        r["id"] = idx

    OUT.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\nWrote {len(records)} records → {OUT}")
    by_source = {}
    for r in records:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    print("By source:", by_source)
    if len(records) < 100:
        raise SystemExit(f"Need ≥100 records, got {len(records)}")


if __name__ == "__main__":
    main()
