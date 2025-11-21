# Polymarket Data MVP

Goal:
Pull market data from Polymarket, filter for daily expiry threshold markets  
(e.g. “BTC > $100k on YYYY-MM-DD”), and poll prices at regular intervals.  

## MVP Objectives

1. Connect to Polymarket’s Gamma API  
2. Search for markets using text filters  
3. Let the user choose markets to subscribe to  
4. Poll and display prices at X-second intervals

## Current Status

- CLI prototype only (no Streamlit yet)  
- Basic HTTP client using `httpx`  
- Interactive selection via Python `input()`  
- Polling loop prints latest prices

## Future Steps

- Standardize parsed market into a `ThresholdBinaryMarket` dataclass  
- Add better parsing/filtering (expiry, strike, underlying)  
- Store time-series locally (CSV or pandas)  
- Then port core logic into Streamlit app  
- Eventually: support Kalshi and Limitless

## Requirements
