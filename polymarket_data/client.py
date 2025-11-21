import httpx

BASE_URL = "https://gamma-api.polymarket.com"

class PolymarketClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def get_markets(self, params: dict | None = None) -> dict:
        params = params or {}
        resp = self._client.get("/markets", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_market_details(self, market_id: str) -> dict:
        """
        Fetch full market details including clobTokenIds, bestBid, bestAsk, etc.
        """
        resp = self._client.get("/markets", params={"id": market_id})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data[0]
        return data


    def search_public(self, query: str, limit_per_type: int = 50, optimized: bool = True):
        """
        Wraps Gamma public-search.

        Parameters roughly follow:
          q: query string (REQUIRED)
          limit_per_type: how many events/tags/profiles per section
          search_tags/search_profiles: false to skip that noise
        """
        params = {
            "q": query,
            "limit_per_type": limit_per_type,
            "search_tags": False,
            "search_profiles": False,
            "optimized": optimized,
        }
        resp = self._client.get("/public-search", params=params)
        resp.raise_for_status()
        return resp.json()


