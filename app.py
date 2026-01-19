import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from concurrent.futures import ThreadPoolExecutor
import logging

# 網頁基本設定
st.set_page_config(page_title="台股首日噴發篩選器", layout="wide")
st.title("🔥 橫盤結束：首日噴發上軌篩選器 (同步版)")

# 隱藏 yfinance 訊息
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def scan_logic(stock_id):
    try:
        info = twstock.codes[stock_id]
        suffix = ".TW" if info.market == '上市' else ".TWO"
        symbol = f"{stock_id}{suffix}"
        
        # 下載資料 (與 Jupyter 一致)
        df = yf.download(symbol, period="6mo", interval="1d", progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if df.empty or len(df) < 21: return None

        # 技術指標 (嚴格對齊 Jupyter)
        close = df['Close']
        vol = df['Volume']
        ma20 = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = ma20 + (std * 2)
        vol_ma20 = vol.rolling(20).mean()

        # 取得數值
        c0, c1, c2, c3, c4 = close.iloc[-1], close.iloc[-2], close.iloc[-3], close.iloc[-4], close.iloc[-5]
        u0, u1, u2, u3, u4 = upper.iloc[-1], upper.iloc[-2], upper.iloc[-3], upper.iloc[-4], upper.iloc[-5]
        v0, v_avg = vol.iloc[-1], vol_ma20.iloc[-1]

        # 核心判斷邏輯 (移除 0.5% 與 500張門檻，只要滿足邏輯就顯示)
        # 1. 過去 4 天都在上軌之下
        was_squeezing = all(close.iloc[i] < upper.iloc[i] for i in range(-5, -1))
        # 2. 今天收盤 > 上軌 (不加 0.5%)
        is_breakout = c0 > u0
        # 3. 今日量 > 均量 (不加 1.3 倍)
        is_vol_ok = v0 > v_avg

        if was_squeezing and is_breakout and is_vol_ok:
            return {
                "產業": info.group,
                "代碼": stock_id,
                "名稱": info.name,
                "收盤": round(float(c0), 2),
                "上軌": round(float(u0), 2),
                "漲幅": f"{round(((c0/c1)-1)*100, 2)}%",
                "量能倍數": round(float(v0/v_avg), 2),
                "狀態": "🔥 橫盤首日突破上軌"
            }
    except:
        return None

# 按鈕觸發
if st.button("🚀 開始全市場同步掃描"):
    all_stocks = [code for code, info in twstock.codes.items() 
                  if info.type == '股票' and info.market in ['上市', '上櫃']]
    
    bar = st.progress(0)
    results = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        for i, res in enumerate(executor.map(scan_logic, all_stocks)):
            if res: results.append(res)
            bar.progress((i + 1) / len(all_stocks))

    if results:
        df_final = pd.DataFrame(results).sort_values(by="量能倍數", ascending=False)
        # 重新排序列，確保與你 Jupyter 的視覺一致
        st.dataframe(df_final[["產業", "代碼", "名稱", "收盤", "上軌", "漲幅", "量能倍數", "狀態"]], use_container_width=True)
    else:
        st.info("今日無符合條件標的。")
