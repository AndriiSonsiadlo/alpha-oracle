"""Fetch recent news headlines for a market question.

Uses Google News RSS, which is public and requires no API key. Headlines are
fed to the LLM as grounding context so probability estimates reflect recent
events rather than the model's stale training data.

Best-effort: any network/parse failure returns an empty list so the agent
tick degrades gracefully to pure-LLM reasoning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


@dataclass
class NewsItem:
    title: str
    source: str
    published: str
    link: str


async def fetch_news(query: str, limit: int = 5, timeout: float = 10.0) -> list[NewsItem]:
    """Return up to `limit` recent headlines for `query`.

    Never raises — returns [] on any error.
    """
    if not query or not query.strip():
        return []

    url = (
        f"{GOOGLE_NEWS_RSS}?q={quote_plus(query.strip())}"
        "&hl=en-US&gl=US&ceid=US:en"
    )

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AlphaOracle/0.1"})
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        logger.warning("News fetch failed for %r: %s", query, exc)
        return []

    items: list[NewsItem] = []
    for item in root.iterfind(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        items.append(
            NewsItem(
                title=title,
                source=source,
                published=(item.findtext("pubDate") or "").strip(),
                link=(item.findtext("link") or "").strip(),
            )
        )
        if len(items) >= limit:
            break

    logger.info("Fetched %d news headlines for %r", len(items), query[:60])
    return items


def format_news_block(items: list[NewsItem]) -> str:
    """Render headlines as a compact text block for an LLM prompt."""
    if not items:
        return "No recent news headlines found."
    lines = []
    for n in items:
        src = f" ({n.source})" if n.source else ""
        lines.append(f"- {n.title}{src}")
    return "\n".join(lines)
