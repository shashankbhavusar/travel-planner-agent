import os
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TAVILY_API_KEY")
client = TavilyClient(api_key=API_KEY) if API_KEY else None


def _sample_hotels(destination: str) -> list[dict]:
    if not destination:
        destination = "the requested destination"
    return [
        {
            "name": "Grandview Hotel",
            "address": f"123 Main Street, {destination}",
            "rating": "4.7/5",
            "price": "$180/night",
            "url": "https://example.com/grandview",
            "summary": "Comfortable city-center hotel with breakfast included and easy access to transportation.",
        },
        {
            "name": "Seaside Resort",
            "address": f"456 Ocean Avenue, {destination}",
            "rating": "4.5/5",
            "price": "$220/night",
            "url": "https://example.com/seaside",
            "summary": "Luxury beachfront property with pool, spa, and excellent family amenities.",
        },
    ]


def tavily_search(query: str) -> list[dict]:
    destination = query
    if not client:
        return _sample_hotels(destination)

    try:
        response = client.search(query=query, max_results=5)
    except Exception:
        return _sample_hotels(destination)

    results = []
    for item in response.get("results", [])[:5]:
        title = item.get("title", "Unknown")
        url = item.get("url", "")
        snippet = item.get("content", "").strip()
        if len(snippet) > 250:
            snippet = snippet[:250].rsplit(" ", 1)[0] + "..."

        results.append(
            {
                "name": title,
                "address": item.get("address", "Unknown location"),
                "rating": item.get("rating", "N/A"),
                "price": item.get("price", "N/A"),
                "url": url,
                "summary": snippet,
            }
        )

    if not results:
        return _sample_hotels(destination)
    return results
