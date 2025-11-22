# streamlit_app.py

import streamlit as st
import pandas as pd

from polymarket_data.client import PolymarketClient
from polymarket_data.market import PolymarketMarket

# ---------- Helpers ----------

def search_markets_text(client: PolymarketClient, text: str, limit_per_type: int = 50):
    """
    Minimal reimplementation of your earlier search:
    calls /public-search and flattens events -> markets.
    """
    data = client.search_public(
        text,
        limit_per_type=limit_per_type,
        optimized=False,     # <-- THIS is the important bit
    )

    events = data.get("events") or []
    markets = []

    for ev in events:
        ev_title = ev.get("title")
        ev_id = ev.get("id")

        for m in ev.get("markets") or []:
            m_copy = dict(m)
            m_copy["eventTitle"] = ev_title
            m_copy["eventId"] = ev_id
            markets.append(m_copy)

    return markets


def get_client():
    # Simple singleton-ish pattern using session_state
    if "polymarket_client" not in st.session_state:
        st.session_state["polymarket_client"] = PolymarketClient()
    return st.session_state["polymarket_client"]


# ---------- Streamlit UI ----------

def main():
    st.title("Polymarket Market Viewer (Demo)")

    client = get_client()

    st.sidebar.header("Search")
    query = st.sidebar.text_input("Search text", value="bitcoin")

    limit = st.sidebar.number_input(
        "Max markets per search",
        min_value=1,
        max_value=100,
        value=20,
        step=1,
    )

    if st.sidebar.button("Run search"):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching markets..."):
                markets = search_markets_text(client, query.strip(), limit_per_type=limit)
            st.session_state["search_results"] = markets

    markets = st.session_state.get("search_results", [])

    if not markets:
        st.info("Run a search from the sidebar to see markets.")
        return

    # Show search results in a compact table
    st.subheader("Search results")

    summary_rows = []
    for m in markets:
        summary_rows.append({
            "market_id": m.get("id"),
            "question": m.get("question"),
            "event_title": m.get("eventTitle"),
            "end_date": m.get("endDate"),
            "best_bid": m.get("bestBid"),
            "best_ask": m.get("bestAsk"),
        })

    df_summary = pd.DataFrame(summary_rows)
    st.dataframe(df_summary, use_container_width=True)

    # Build choices for user selection
    options = []
    labels = {}
    for m in markets:
        mid = m.get("id")
        q = (m.get("question") or "")[:80]
        label = f"{mid} – {q}"
        options.append(label)
        labels[label] = mid

    st.subheader("Select markets to plot")

    selected_labels = st.multiselect(
        "Choose one or more markets:",
        options=options,
        default=options[:1] if options else [],
    )

    if not selected_labels:
        st.info("Select at least one market above.")
        return

    # Plot settings
    st.sidebar.header("History settings")
    hours_back = st.sidebar.slider("Hours back", min_value=1, max_value=168, value=24)
    fidelity = st.sidebar.selectbox(
        "Bucket size (minutes)",
        options=[1, 5, 15, 60],
        index=1,
    )

    # For each selected market: load data and plot
    tabs = st.tabs(selected_labels)

    for tab_label, label in zip(tabs, selected_labels):
        market_id = labels[label]

        with tab_label:
            st.write(f"### Market {market_id}")
            try:
                pm = PolymarketMarket.from_market_id(client, market_id)
                pm.refresh_quotes(client)

                # Clean, minimal header
                st.markdown(f"### {pm.question}")
                st.caption(
                    f"Market ID: {pm.market_id} · "
                    f"Expiry: {pm.end_date:%Y-%m-%d %H:%M} UTC · "
                    f"YES bid/ask: {pm.best_bid_yes or 'N/A'} / {pm.best_ask_yes or 'N/A'}"
                )

                with st.spinner("Loading price history..."):
                    pm.load_price_history(client, hours_back=hours_back, fidelity=fidelity)
                    df = pm.price_history()  # your method; adjust below if needed

                if df is None or df.empty:
                    st.warning("No price history returned for this market.")
                    continue

                # Try to be robust about the price column name
                if "yes_price" in df.columns:
                    y_col = "yes_price"
                elif "price" in df.columns:
                    y_col = "price"
                else:
                    st.error(f"Unexpected columns in price history: {df.columns.tolist()}")
                    continue

                df_plot = df[[y_col]]
                df_plot = df_plot.rename(columns={y_col: "YES price"})

                st.line_chart(df_plot)
                
            except Exception as e:
                st.error(f"Error loading market {market_id}: {e}")


if __name__ == "__main__":
    main()
