import streamlit as st
import pandas as pd
import requests
from requests_oauthlib import OAuth1Session
import plotly.graph_objects as go
import datetime
import csv
import os

# Setup for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants for E*TRADE API access - use sandbox API keys and URLs
CONSUMER_KEY = os.getenv('CONSUMER_SANDBOX_KEY')  # Your sandbox consumer key from environment variable
CONSUMER_SECRET = os.getenv('CONSUMER_SANDBOX_SECRET')  # Your sandbox consumer secret from environment variable
OAUTH_BASE_URL = 'https://apisb.etrade.com/oauth'
API_BASE_URL = 'https://apisb.etrade.com/v1/market'

# Authenticate and create an OAuth session
def etrade_oauth():
    try:
        oauth = OAuth1Session(client_key=CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri='oob')
        fetch_response = oauth.fetch_request_token(f"{OAUTH_BASE_URL}/request_token")
        authorization_url = oauth.authorization_url(f"{OAUTH_BASE_URL}/authorize")
        st.write('Please authenticate by visiting this URL:', authorization_url)
        verifier = st.text_input('Enter the verifier code here:')
        if verifier:
            oauth.fetch_access_token(f"{OAUTH_BASE_URL}/access_token", verifier=verifier)
        return oauth
    except Exception as e:
        logging.error(f"Authentication Error: {e}")
        st.error("Authentication failed, please check your credentials and network connection.")

# Fetch stock data using the E*TRADE sandbox API
def fetch_stock_data(session, symbol):
    try:
        response = session.get(f"{API_BASE_URL}/quote/{symbol}.json")
        data = response.json()
        if 'QuoteResponse' in data and 'QuoteData' in data['QuoteResponse'] and len(data['QuoteResponse']['QuoteData']) > 0:
            return pd.DataFrame([data['QuoteResponse']['QuoteData'][0]['All']])
        else:
            st.error("No data available for the given symbol.")
            return None
    except Exception as e:
        logging.error(f"Data Fetching Error: {e}")
        st.error("Failed to fetch stock data.")
        return None

# Calculate Ichimoku Cloud
def calculate_ichimoku(data):
    if data is not None and len(data) >= 52:
        high_prices = data['high']
        low_prices = data['low']
        close_prices = data['lastTrade']

        # Tenkan-sen (Conversion Line)
        tenkan_sen = (high_prices.rolling(window=9).max() + low_prices.rolling(window=9).min()) / 2

        # Kijun-sen (Base Line)
        kijun_sen = (high_prices.rolling(window=26).max() + low_prices.rolling(window=26).min()) / 2

        # Senkou Span A (Leading Span A)
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)

        # Senkou Span B (Leading Span B)
        senkou_span_b = ((high_prices.rolling(window=52).max() + low_prices.rolling(window=52).min()) / 2).shift(26)

        # Chikou Span (Lagging Span)
        chikou_span = close_prices.shift(-26)

        return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span
    else:
        st.error("Not enough data for Ichimoku Cloud calculation.")
        return None

# Trading strategy based on the average of the first 5 candles
def apply_trading_strategy(data, target_price):
    if data is not None and len(data) >= 5:
        avg_close = data['close'].head(5).mean()
        first_open = data['open'].iloc[0]
        
        if avg_close > first_open:
            action = 'buy call'
            st.success(f"Average close is above the first open; buying calls at ${target_price}")
        elif avg_close < first_open:
            action = 'buy put'
            st.success(f"Average close is below the first open; buying puts at ${target_price}")
        else:
            action = 'hold'
            st.info("Average close is equal to the first open; no action recommended.")
        
        log_trade({'symbol': data['symbol'].iloc[0], 'action': action, 'price': target_price})
    else:
        st.error("Not enough data to apply the strategy.")

# Log trade actions to a CSV file
def log_trade(trade_info):
    with open('trade_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.datetime.now(), trade_info['symbol'], trade_info['action'], trade_info['price']])
    st.success(f"Trade logged: {trade_info}")

# Plotting function for trading signals
def plot_signals(data, tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span):
    fig = go.Figure()
    # Plot close price
    fig.add_trace(go.Scatter(x=data.index, y=data['close'], mode='lines', name='Close Price'))
    # Plot Ichimoku components
    fig.add_trace(go.Scatter(x=data.index, y=tenkan_sen, mode='lines', name='Tenkan-sen'))
    fig.add_trace(go.Scatter(x=data.index, y=kijun_sen, mode='lines', name='Kijun-sen'))
    fig.add_trace(go.Scatter(x=data.index, y=senkou_span_a, mode='lines', fill='tonexty', name='Senkou Span A'))
    fig.add_trace(go.Scatter(x=data.index, y=senkou_span_b, mode='lines', fill='tonexty', name='Senkou Span B'))
    fig.add_trace(go.Scatter(x=data.index, y=chikou_span, mode='lines', name='Chikou Span'))

    st.plotly_chart(fig)

# Main function to drive the app
def main():
    st.title('Trading App with E*TRADE Sandbox and Ichimoku Strategy')
    session = etrade_oauth()
    if session:
        symbol = st.text_input('Enter stock symbol:')
        if symbol:
            data = fetch_stock_data(session, symbol)
            if data is not None:
                st.write(data)
                ichimoku_components = calculate_ichimoku(data)
                if ichimoku_components:
                    tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span = ichimoku_components
                    plot_signals(data, tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span)
                target_price = st.number_input('Enter your target price for trade execution:', min_value=0.0, step=0.01, format="%.2f")
                apply_trading_strategy(data, target_price)

if __name__ == "__main__":
    main()
