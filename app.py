import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from concurrent.futures import ThreadPoolExecutor
import datetime

# 網頁介面設定
st.set_page_config(page_title="台股首日噴發篩選器", layout="wide")
st.title("🔥 橫盤結束：首日噴發上軌篩選器 (強制對齊版)")

def scan_logic(stock_id):
    try:
        info = twstock.codes[stock_id]
        suffix = ".TW" if info.market == '上市' else ".TWO"
        symbol = f"{stock_id}{suffix}"
        
        # 抓取較長區間，確保 MA20/STD 計算精準
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 關鍵：確保抓到的是最新的資料，並刪除可能存在的空白行
        df = df.dropna()
        if len(df) < 25: return None

        # 技術指標計算
        close = df['Close']
        vol = df['Volume']
        ma20 = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = ma20 + (std * 2)
        vol_ma20 = vol.rolling(20).mean()

        # 取得最後 5 筆資料 (保證對齊最後一個交易日)
        curr_close = close.values[-5:] # [前4, 前3, 前2, 昨日, 今日]
        curr_upper = upper.values[-5:]
        curr_vol = vol.values[-1]
        avg_vol = vol_ma20.values[-1]

        # 核心判斷邏輯
        # 1. 過去 4 天 (昨日到大前日) 都在上軌之下
        was_squeezing = all(curr_close[i] < curr_upper[i] for i in range(0, 4))
        # 2. 今天收盤 > 上軌
        is_breakout = curr_close[4] > curr_upper[4]
        # 3. 今日量 > 均量
        is_vol_ok = curr_vol > avg_vol

        if was_squeezing and is_breakout and is_vol_ok:
            return {
                "產業": info.group,
                "代碼": stock_id,
                "名稱": info.name,
                "今日價格": round(float(curr_close[4]), 2),
                "今日上軌": round(float(curr_upper[4]), 2),
                "漲幅": f"{round(((curr_close[4]/curr_close[3])-1)*100, 2)}%",
                "量能倍數": round(float(curr_vol/avg_vol), 2),
                "更新日期": df.index[-1].strftime('%Y-%m-%d')
            }
    except:
        return None

if st.button("🚀 開始同步掃描 (強制對齊最後交易日)"):
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
        st.write(f"📅 資料最後日期：{results[0]['更新日期']}")
        st.dataframe(df_final, use_container_width=True)
    else:
        st.info("今日無符合條件標的。")
