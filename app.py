import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

# Page Layout Configuration
st.set_page_config(layout="wide")
st.title("🔥 DELTA EXCHANGE INDIA - LIVE TRADING DESK WITH CHARTS")

# Sidebar Configuration
st.sidebar.header("🎯 Market Settings")
asset = st.sidebar.selectbox("Select Asset", ["BTC", "ETH"])
expiry_date = st.sidebar.text_input("Enter Expiry Date (DD-MM-YYYY)", "18-09-2026")

# --- FETCH DATA & CALCULATE INDICATORS ---
@st.cache_data(ttl=60)
def fetch_market_data(symbol):
    try:
        # Fetch last 50 hours of 1-Hour candles
        history_url = f"https://api.india.delta.exchange/v2/history/candles?resolution=1h&symbol={symbol}USDT"
        res = requests.get(history_url).json()
        
        if "result" in res and len(res["result"]) > 0:
            df = pd.DataFrame(res["result"])
            # Format and convert data types
            df['close'] = df['close'].astype(float)
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['volume'] = df['volume'].astype(float)
            df['time'] = pd.to_datetime(df['start_time'], unit='s')
            
            # EMA Calculations
            df['EMA9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
            
            # VWAP Calculation
            df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            df['tp_vol'] = df['typical_price'] * df['volume']
            vwap_val = df['tp_vol'].sum() / df['volume'].sum()
            df['VWAP'] = vwap_val
            
            return df
    except:
        pass
    return None

# Load Data
df_candles = fetch_market_data(asset)

if df_candles is not None:
    # Latest Metric Values
    spot_price = round(df_candles['close'].iloc[-1], 2)
    ema_9 = round(df_candles['EMA9'].iloc[-1], 2)
    ema_21 = round(df_candles['EMA21'].iloc[-1], 2)
    vwap = round(df_candles['VWAP'].iloc[-1], 2)
else:
    spot_price, vwap, ema_9, ema_21 = 65000, 64850, 65100, 64900

# --- TOP SECTION: LIVE METRICS ---
st.markdown("### 🎯 Live Indicators")
col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Underlying Spot ({asset})", f"${spot_price:,}")
col2.metric("Calculated VWAP", f"${vwap:,}")
col3.metric("9 EMA (Momentum)", f"${ema_9:,}")
col4.metric("21 EMA (Trend)", f"${ema_21:,}")

# --- NEW SECTION: LIVE CANDLESTICK CHART ---
st.markdown("---")
st.markdown("### 📈 Real-Time Technical Chart")

if df_candles is not None:
    # Build Plotly Candlestick Chart
    fig = go.Figure()
    
    # Add Candlesticks
    fig.add_trace(go.Candlestick(
        x=df_candles['time'],
        open=df_candles['open'],
        high=df_candles['high'],
        low=df_candles['low'],
        close=df_candles['close'],
        name='Market Price'
    ))
    
    # Add 9 EMA Line
    fig.add_trace(go.Scatter(
        x=df_candles['time'], y=df_candles['EMA9'], 
        mode='lines', line=dict(color='orange', width=1.5), name='9 EMA'
    ))
    
    # Add 21 EMA Line
    fig.add_trace(go.Scatter(
        x=df_candles['time'], y=df_candles['EMA21'], 
        mode='lines', line=dict(color='blue', width=1.5), name='21 EMA'
    ))
    
    # Layout Adjustments
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=400,
        margin=dict(l=20, r=20, t=20, b=20),
        template="plotly_dark"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 ચાર્ટનો ડેટા લોડ થઈ રહ્યો છે અથવા અવેલેબલ નથી.")

# --- MIDDLE SECTION: OPTIONS CHAIN WITH AUTO-SIGNALS ---
st.markdown("---")
st.markdown("### 📊 Live Options Chain & Execution Signals")

options_url = f"https://api.india.delta.exchange/v2/tickers?contract_types=call_options,put_options&underlying_asset_symbols={asset}&expiry_date={expiry_date}"

try:
    response = requests.get(options_url).json()
    if "result" in response and len(response["result"]) > 0:
        raw_data = response["result"]
        processed_rows = []
        
        for item in raw_data:
            strike = item.get("strike_price", 0)
            ltp = float(item.get("close", 0))
            oi = item.get("open_interest", 0)
            vol = item.get("volume", 0)
            delta = float(item.get("delta", 0))
            contract_type = item.get("contract_type", "")
            opt_type = "CE" if "call" in contract_type else "PE"
            
            # Smart Signal Logic
            trend = "BULLISH" if ema_9 > ema_21 else "BEARISH"
            iv_status = "SQUEEZE" if abs(spot_price - vwap) < 200 else "NORMAL"
            
            if opt_type == "CE" and trend == "BULLISH" and delta > 0.40:
                signal = "🚀 BUY CALL"
                sl, t1, t2 = ltp * 0.80, ltp * 1.25, ltp * 1.50
            elif opt_type == "PE" and trend == "BEARISH" and delta < -0.40:
                signal = "📉 BUY PUT"
                sl, t1, t2 = ltp * 0.80, ltp * 1.25, ltp * 1.50
            else:
                signal = "⏳ HOLD / WAIT"
                sl, t1, t2 = 0, 0, 0

            processed_rows.append({
                "Strike Price": strike,
                "Option Type": opt_type,
                "LTP (Premium)": ltp,
                "Delta": delta,
                "Open Interest (OI)": oi,
                "Volume": vol,
                "EMA/VWAP Trend": trend,
                "IV Squeeze": iv_status,
                "EXECUTION SIGNAL": signal,
                "Stop Loss": round(sl, 1),
                "Target 1": round(t1, 1),
                "Target 2": round(t2, 1)
            })

        df_options = pd.DataFrame(processed_rows).sort_values(by="Strike Price").reset_index(drop=True)
        st.dataframe(df_options, use_container_width=True)
    else:
        st.warning("⚠️ આ એક્સપાયરી તારીખ માટે કોઈ લાઈવ કોન્ટ્રેક્ટ મળ્યા નથી.")
except Exception as e:
    st.error(f"ડેટા કનેક્શન પ્રોબ્લેમ: {str(e)}")

# --- BOTTOM SECTION: PERFORMANCE LOG & TRACKER ---
st.markdown("---")
st.markdown("### 📝 Daily Performance Log & Trade Tracker")

if "trade_log" not in st.session_state:
    st.session_state.trade_log = pd.DataFrame(columns=[
        "Trade ID", "Timestamp", "Contract Option", "Entry Price (LTP)", "Exit Price", "Quantity", "Gross P&L ($)", "Status"
    ])

with st.form("trade_form", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        t_id = st.text_input("Trade ID", value=f"TR-{len(st.session_state.trade_log)+1}")
    with c2:
        t_contract = st.text_input("Contract Name", "BTC 65000 CE")
    with c3:
        t_entry = st.number_input("Entry Price ($)", min_value=0.0, value=100.0)
    with c4:
        t_exit = st.number_input("Exit Price ($)", min_value=0.0, value=130.0)
    with c5:
        t_qty = st.number_input("Quantity", min_value=1, value=5)
        
    submit_trade = st.form_submit_button("➕ Log Trade")

if submit_trade:
    pnl = (t_exit - t_entry) * t_qty
    status = "PROFIT" if pnl > 0 else "LOSS"
    new_trade = {
        "Trade ID": t_id,
        "Timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
        "Contract Option": t_contract,
        "Entry Price (LTP)": t_entry,
        "Exit Price": t_exit,
        "Quantity": t_qty,
        "Gross P&L ($)": pnl,
        "Status": status
    }
    st.session_state.trade_log = pd.concat([st.session_state.trade_log, pd.DataFrame([new_trade])], ignore_index=True)

st.dataframe(st.session_state.trade_log, use_container_width=True)
