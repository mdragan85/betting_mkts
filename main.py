from polymarket_data.client import PolymarketClient
from datetime import datetime
import json


def parse_end_date(m):
    """Safely parse endDate into a datetime object, or return None."""
    raw = m.get("endDate")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def sort_markets_by_end_date(markets: list[dict]):
    """Return list sorted in ascending order by endDate."""
    # Markets with valid dates first, invalid dates last
    markets_sorted = sorted(
        markets,
        key=lambda m: (parse_end_date(m) is None, parse_end_date(m))
    )
    return markets_sorted


def search_markets_text(client: PolymarketClient, text: str, limit_per_type: int = 50):
    data = client.search_public(text, limit_per_type=limit_per_type, optimized=False)

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

    # filter for only active markets & sort by end date
    only_active = sort_markets_by_end_date([m for m in markets if m.get("active") and not m.get("closed")])

    # sort in ascending by 
    if not only_active:
        print("No markets found for that query.")
        return

    print(f"\nFound {len(only_active)} markets for '{query}':\n")
    print_markets(only_active)

    #output to JSON
    with open("examples\markets_snapshot.json", "w") as f:
        json.dump(markets, f, indent=2)  

if __name__ == "__main__":
    main()