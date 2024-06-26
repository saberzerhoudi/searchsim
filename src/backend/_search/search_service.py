import json
import os

import redis
from dotenv import load_dotenv
from fastapi import HTTPException

from backend.schemas import SearchResponse
from backend._search.interfaces.base import SearchProvider
from backend._search.interfaces.bing import BingSearchProvider
from backend._search.interfaces.tavily import TavilySearchProvider

load_dotenv()


redis_url = os.getenv("REDIS_URL")
redis_client = redis.Redis.from_url(redis_url) if redis_url else None


def get_tavily_api_key():
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        raise HTTPException(
            status_code=500,
            detail="Tavily API key is not set in the environment variables. Please set the TAVILY_API_KEY environment variable.",
        )
    return tavily_api_key


def get_bing_api_key():
    bing_api_key = os.getenv("BING_API_KEY")
    if not bing_api_key:
        raise HTTPException(
            status_code=500,
            detail="Bing API key is not set in the environment variables. Please set the BING_API_KEY environment variable or set SEARCH_PROVIDER to 'tavily'.",
        )
    return bing_api_key


def get_search_provider() -> SearchProvider:
    search_provider = os.getenv("SEARCH_PROVIDER", "tavily")

    match search_provider:
        
        case "tavily":
            tavily_api_key = get_tavily_api_key()
            return TavilySearchProvider(tavily_api_key)
        case "bing":
            bing_api_key = get_bing_api_key()
            return BingSearchProvider(bing_api_key)
        case _:
            raise HTTPException(
                status_code=500,
                detail="Invalid search provider. Please set the SEARCH_PROVIDER environment variable to either 'tavily', or 'bing'.",
            )


async def perform_search(query: str) -> SearchResponse:
    search_provider = get_search_provider()

    try:
        cache_key = f"search:{query}"
        if redis_client and (cached_results := redis_client.get(cache_key)):
            cached_json = json.loads(json.loads(cached_results.decode("utf-8")))  # type: ignore
            return SearchResponse(**cached_json)

        results = await search_provider.search(query)

        if redis_client:
            redis_client.set(cache_key, json.dumps(results.model_dump_json()), ex=7200)

        return results
    except Exception:
        raise HTTPException(
            status_code=500, detail="There was an error while searching."
        )
