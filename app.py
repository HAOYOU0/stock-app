import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from concurrent.futures import ThreadPoolExecutor
import logging

# 基本網頁設定
st.set_page_config(page_title="台股首日噴發篩選器", layout="wide")
st.title("🔥 橫盤結束：首日噴發上軌篩選器")
st.write("條件：過去 4 天在中軌震盪且未破上軌，今天首度帶量突破上軌。")

# 隱藏 yfinance 訊息
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def scan_logic(stock_id):
    try:
        info = twstock.codes[stock_id]
        suffix = ".TW" if info.market == '上市' else ".TWO"
        symbol = f"{stock_id}{suffix}"
        
        # 下載資料
        df = yf.download(symbol, period="3mo", interval="1d", progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty or len(df) < 25: return None

        # 計算指標
        close = df['Close']
        vol = df['Volume']
        ma20 = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = ma20 + (std * 2)
        vol_ma20 = vol.rolling(20).mean()

        # 數值序列 (今日為索引 0)
        c = [close.iloc[-1], close.iloc[-2], close.iloc[-3], close.iloc[-4], close.iloc[-5]]
        u = [upper.iloc[-1], upper.iloc[-2], upper.iloc[-3], upper.iloc[-4], upper.iloc[-5]]
        v0, v_avg = vol.iloc[-1], vol_ma20.iloc[-1]

        # 核心判斷邏輯
        was_squeezing = all(c[i] < u[i] for i in range(1, 5))
        is_first_breakout = c[0] > (u[0] * 1.005)
        is_vol_confirmed = v0 > (v_avg * 1.3)
        is_liquid = v_avg > 500000

        if was_squeezing and is_first_breakout and is_vol_confirmed and is_liquid:
            return {
                "產業": info.group,
                "代碼": stock_id,
                "名稱": info.name,
                "收盤": round(float(c[0]), 2),
                "上軌": round(float(u[0]), 2),
                "漲幅": f"{round(((c[0]/c[1])-1)*100, 2)}%",
                "量能倍數": round(float(v0/v_avg), 2),
                "狀態": "🔥 首日突破上軌"
            }
    except:
        return None

# 介面按鈕
if st.button("🚀 開始掃描全市場 (約 2-3 分鐘)"):
    all_stocks = [code for code, info in twstock.codes.items() 
                  if info.type == '股票' and info.market in ['上市', '上櫃']]
    
    status_placeholder = st.empty()
    bar = st.progress(0)
    
    results = []
    # 使用 ThreadPoolExecutor 加速
    with ThreadPoolExecutor(max_workers=15) as executor:
        for i, res in enumerate(executor.map(scan_logic, all_stocks)):
            if res:
                results.append(res)
            # 更新進度條
            progress = (i + 1) / len(all_stocks)
            bar.progress(progress)
            if i % 100 == 0:
                status_placeholder.text(f"🔍 正在檢查第 {i} 檔股票...")

    status_placeholder.success("✅ 掃描完成！")
    
    if results:
        df_final = pd.DataFrame(results).sort_values(by="量能倍數", ascending=False)
        st.dataframe(df_final, use_container_width=True)
        
        # 額外統計：產業分佈
        st.subheader("📊 今日強勢族群")
        st.bar_chart(df_final['產業'].value_counts())
    else:
        st.info("今日無符合「長期震盪後首日突破上軌」的標的。")
