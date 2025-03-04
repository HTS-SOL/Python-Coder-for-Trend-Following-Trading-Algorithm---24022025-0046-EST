import ccxt
import pandas as pd
import datetime
import time
import numpy as np
import streamlit as st

st.title("Algorithmic Trading Bot")

api_key = st.text_input("Enter API Key", type="password")
api_secret = st.text_input("Enter API Secret", type="password")

if api_key and api_secret:
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'options': {'defaultType': 'spot'},
    })

    params = {
        "timeframe": "3m",
        "bollinger_period": 20,
        "bollinger_std_dev": 3,
        "entry_start_time": "09:15",
        "entry_end_time": "09:45",
        "max_stocks": 5,
        "min_price": 200,
        "trade_amount": 1,
        "stop_loss": 2000,
        "target": 2000,
    }

    in_position = {}
    fno_stocks = ["RELIANCE/USDT", "TCS/USDT", "INFY/USDT", "HDFCBANK/USDT", "ICICIBANK/USDT"]

    def fetch_data(symbol, timeframe):
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe, limit=params["bollinger_period"] + 5)
            df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["close"] = df["close"].astype(float)
            return df
        except:
            return None

    def calculate_indicators(df):
        df["SMA"] = df["close"].rolling(params["bollinger_period"]).mean()
        df["STD"] = df["close"].rolling(params["bollinger_period"]).std()
        df["Upper"] = df["SMA"] + (params["bollinger_std_dev"] * df["STD"])
        df["Lower"] = df["SMA"] - (params["bollinger_std_dev"] * df["STD"])
        return df

    def check_conditions(df, symbol):
        global in_position
        if df is None or df.empty:
            return False
        first_candle = df.iloc[0]
        if not (first_candle["high"] > first_candle["Upper"] or first_candle["low"] < first_candle["Lower"]):
            return False
        prev_candle = df.iloc[-2]
        curr_candle = df.iloc[-1]
        order_type = None
        if curr_candle["close"] > prev_candle["high"]:
            order_type = "CALL"
        elif curr_candle["close"] < prev_candle["low"]:
            order_type = "PUT"
        if order_type and len(in_position) < params["max_stocks"] and curr_candle["close"] >= params["min_price"]:
            place_trade(symbol, order_type, curr_candle["close"])
            return True
        return False

    def place_trade(symbol, order_type, price):
        global in_position
        option_symbol = f"{symbol}_{order_type}_ATM"
        try:
            order = exchange.create_market_order(option_symbol, "buy", params["trade_amount"])
            st.write(f"Executed {order_type} Order on {option_symbol} at ₹{price}")
            in_position[symbol] = {
                "type": order_type,
                "entry_price": price,
                "stop_loss": price - params["stop_loss"],
                "target": price + params["target"]
            }
        except:
            pass

    def monitor_trades():
        global in_position
        for symbol, trade in list(in_position.items()):
            df = fetch_data(symbol, params["timeframe"])
            if df is None or df.empty:
                continue
            last_price = df.iloc[-1]["close"]
            if (trade["type"] == "CALL" and last_price < trade["stop_loss"]) or \
               (trade["type"] == "PUT" and last_price > trade["stop_loss"]):
                close_trade(symbol, last_price, "STOP LOSS HIT")
                continue
            if trade["type"] == "CALL" and last_price > trade["target"]:
                trade["target"] = last_price
                trade["stop_loss"] = last_price - params["stop_loss"]
            elif trade["type"] == "PUT" and last_price < trade["target"]:
                trade["target"] = last_price
                trade["stop_loss"] = last_price + params["stop_loss"]
            if (trade["type"] == "CALL" and last_price > trade["target"]) or \
               (trade["type"] == "PUT" and last_price < trade["target"]):
                close_trade(symbol, last_price, "TARGET HIT")

    def close_trade(symbol, price, reason):
        global in_position
        st.write(f"Closing {symbol} trade at ₹{price} due to {reason}")
        del in_position[symbol]

    def is_entry_time():
        now = datetime.datetime.now().strftime("%H:%M")
        return params["entry_start_time"] <= now <= params["entry_end_time"]

    if st.button("Start Trading Bot"):
        while True:
            try:
                if is_entry_time():
                    for stock in fno_stocks:
                        df = fetch_data(stock, params["timeframe"])
                        if df is not None:
                            df = calculate_indicators(df)
                            check_conditions(df, stock)
                monitor_trades()
                time.sleep(60)
            except:
                time.sleep(5)