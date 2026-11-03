"""Web search integration for LocalGPT (optional).
Uses free search mechanisms. No paid APIs, no API keys required.
Falls back gracefully if unavailable.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import quote_plus


class WebSearchError(Exception):
    """Web search failure."""
    pass


class WebSearch:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._available = False
        self._check_availability()

    def _check_availability(self):
        """Check if web search is available."""
        try:
            # Try duckduckgo
            import duckduckgo_search  # type: ignore
            self._available = True
        except ImportError:
            try:
                # Try other free options
                import requests  # noqa
                self._available = True  # basic availability
            except Exception:
                self._available = False

    def is_available(self) -> bool:
        return self.enabled and self._available

    def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Perform web search. Returns results with sources."""
        if not self.enabled:
            raise WebSearchError("Web search is disabled. Enable it in configuration.")
        if not query or not query.strip():
            raise WebSearchError("Empty search query.")

        # Try duckduckgo_search first (free, no API key)
        try:
            try:
                from duckduckgo_search import DDGS  # type: ignore

                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.text(query, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "href": r.get("href", ""),
                            "body": r.get("body", ""),
                        })
                    if results:
                        return {
                            "query": query,
                            "results": results,
                            "source": "duckduckgo",
                            "count": len(results),
                        }
            except ImportError:
                pass
        except Exception as e:
            pass

        # Fallback: try requests to search engines (basic)
        try:
            import requests
            from bs4 import BeautifulSoup  # type: ignore

            # Using DuckDuckGo HTML (no JS)
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for result in soup.select(".result__body")[:max_results]:
                    title_elem = result.select_one(".result__title a")
                    snippet_elem = result.select_one(".result__snippet")
                    if title_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "href": title_elem.get("href", ""),
                            "body": snippet_elem.get_text(strip=True) if snippet_elem else "",
                        })
                if results:
                    return {
                        "query": query,
                        "results": results,
                        "source": "duckduckgo_html",
                        "count": len(results),
                    }
        except Exception as e:
            pass

        raise WebSearchError(
            "Live external information cannot currently be retrieved. "
            "Web search libraries may not be installed or the service is unavailable."
        )

    def format_results_for_llm(self, search_result: dict[str, Any]) -> str:
        """Format search results as context for LLM."""
        if not search_result or not search_result.get("results"):
            return ""
        lines = [f"WEB SEARCH RESULTS (for query: {search_result['query']}):"]
        for i, r in enumerate(search_result["results"], 1):
            lines.append(f"\n{i}. {r['title']}")
            if r.get("body"):
                lines.append(f"   {r['body']}")
            if r.get("href"):
                lines.append(f"   Source: {r['href']}")
        lines.append("\nUse these results to provide up-to-date information. Cite sources when relevant.")
        return "\n".join(lines)
