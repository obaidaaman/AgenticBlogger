from ..models.models import State, EvidencePack
from utils.llm_config import llm
from typing import List
from utils.const import RESEARCH_SYSTEM
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv
import os
load_dotenv()
tool = TavilySearchResults(max_results=6,api_key = os.getenv("TAVILY_API_KEY")) 


async def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    

    results = tool.invoke({"query": query})

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
        # normalized is list of results dictionary by tavily searches, this will be added to results in reserrch node
        # [{"title":..., "url":..., "snippet":..., "published_at":..., "source":...},{"title":..., "url":..., "snippet":..., "published_at":..., "source":...},...]
    return normalized

async def research_node(state: State) -> dict:

    queries = state['queries']

    raw_results : List[dict] = []

    for q in queries:
        raw_results.extend( await _tavily_search(q,max_results=6))

    if not raw_results:
        return {"evidence": []}
    
    pack =  await llm.with_structured_output(EvidencePack).ainvoke([
        SystemMessage(content=RESEARCH_SYSTEM),
        HumanMessage(content=f"Raw results: \n{raw_results}")

    ])
    dedup = {}
    for e in pack.evidence:
        if e.url:
            dedup[e.url] = e

    return {"evidence": list(dedup.values())}
    



