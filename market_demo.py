from polymarket_data.client import PolymarketClient
from polymarket_data.market import PolymarketMarket


if __name__ == '__main__':
    client = PolymarketClient()

    market_id = '684373'

    # Build object with full metadata
    pm = PolymarketMarket.from_market_id(client, market_id)

    # Refresh quotes
    pm.refresh_quotes(client)
    pm.load_price_history(client, hours_back=24, fidelity=1)

    print(pm)