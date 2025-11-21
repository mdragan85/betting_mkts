from polymarket_data.client import PolymarketClient

from polymarket_data.client import PolymarketClient

def search_markets_text(client: PolymarketClient, text: str, limit_per_type: int = 50):
    data = client.search_public(text, limit_per_type=limit_per_type)

    events = data.get("events") or []

    markets = []
    for ev in events:
        ev_title = ev.get("title")
        ev_id = ev.get("id")
        for m in ev.get("markets", []) or []:
            # Attach event context so you can see where the market came from
            m_with_event = dict(m)
            m_with_event["eventTitle"] = ev_title
            m_with_event["eventId"] = ev_id
            markets.append(m_with_event)

    return markets


def print_markets(markets):
    for i, m in enumerate(markets):
        print("-" * 80)
        print(f"[{i}] {m.get('question') or m.get('groupItemTitle') or m.get('slug')}")
        print(f"     market id:   {m.get('id')}")
        print(f"     event:       {m.get('eventTitle')} (id={m.get('eventId')})")
        print(f"     category:    {m.get('category')}")
        print(f"     endDate:     {m.get('endDate')}")
        print(f"     active:      {m.get('active')}  closed: {m.get('closed')}")



def main():
    client = PolymarketClient()

    query = input("Search term (e.g. BTC, Bitcoin, Trump, CPI): ").strip()
    if not query:
        print("No search term provided. Exiting.")
        return

    markets = search_markets_text(client, query, limit_per_type=25)

    if not markets:
        print("No markets found for that query.")
        return

    print(f"\nFound {len(markets)} markets for '{query}':\n")
    print_markets(markets)


if __name__ == "__main__":
    main()