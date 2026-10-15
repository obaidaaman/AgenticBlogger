from typing import List, Optional
import os
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from ..models.models import State, EvidencePack
from utils.llm_config import llm
from utils.const import RESEARCH_SYSTEM

load_dotenv()


def _get_tavily_tool() -> Optional[TavilySearchResults]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    try:
        return TavilySearchResults(max_results=6, api_key=api_key)
    except Exception:
        return None


async def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    tool = _get_tavily_tool()
    if tool is None:
        return []

    try:
        results = tool.invoke({"query": query})
    except Exception as exc:
        print(f"Warning: Tavily search failed for '{query}': {exc}")
        return []

    normalized: List[dict] = []
    for r in results or []:
        normalized.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or r.get("snippet") or "",
                "published_at": r.get("published_date") or r.get("published_at"),
                "source": r.get("source"),
            }
        )
    return normalized


async def research_node(state: State) -> dict:
    queries = state.get("queries", [])
    raw_results: List[dict] = []

    for q in queries:
        raw_results.extend(await _tavily_search(q, max_results=6))

    if not raw_results:
        return {"evidence": []}

    pack = await llm.with_structured_output(EvidencePack).ainvoke([
        SystemMessage(content=RESEARCH_SYSTEM),
        HumanMessage(content=f"Raw results: \n{raw_results}"),
    ])

    dedup = {}
    for e in pack.evidence:
        if e.url:
            dedup[e.url] = e

    return {"evidence": list(dedup.values())}
