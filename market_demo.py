from polymarket_data.client import PolymarketClient
from polymarket_data.market import PolymarketMarket


if __name__ == '__main__':
    client = PolymarketClient()

    market_id = '684373'

    # Build object with full metadata
    pm = PolymarketMarket.from_market_id(client, market_id)
    print(f"\nLoaded market: {pm.question}")
    print(f"YES token: {pm.clob_token_yes}")
    print(f"NO  token: {pm.clob_token_no}")
    print(f"End date:  {pm.end_date}")
    print(f"Active:    {pm.active}, Closed: {pm.closed}")

    # Refresh quotes
    pm.refresh_quotes(client)
    print("\nCurrent quotes (approx):")
    print(f"YES bid/ask: {pm.best_bid_yes} / {pm.best_ask_yes}")
    print(f"NO  bid/ask: {pm.best_bid_no}  / {pm.best_ask_no}")

    # Load trades (tweak hours_back as needed)
    pm.load_all_trades()
    df_yes = pm.build_yes_price_history()

    print(f"\nYES price history (combined YES+NO trades): {len(df_yes)} rows")
    print(df_yes.head())