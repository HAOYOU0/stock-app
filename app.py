import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from concurrent.futures import ThreadPoolExecutor

# 設定網頁標題
st.set_page_config(page_title="台股首發突破篩選器", layout="wide")
st.title("📈 台股橫盤首日突破篩選器")
st.write("條件：過去4天中軌震盪，今日首度突破上軌且帶量。")

def scan_logic(stock_id):
    try:
        info = twstock.codes[stock_id]
        suffix = ".TW" if info.market == '上市' else ".TWO"
        symbol = f"{stock_id}{suffix}"
        df = yf.download(symbol, period="3mo", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 25: return None

        close = df['Close']
        vol = df['Volume']
        ma20 = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = ma20 + (std * 2)
        vol_ma20 = vol.rolling(20).mean()

        # 取得數據序列
        c = close.iloc[-5:].values[::-1] # 今日到前4天
        u = upper.iloc[-5:].values[::-1]
        v0, v_avg = vol.iloc[-1], vol_ma20.iloc[-1]

        # 邏輯判斷
        was_squeezing = all(c[i] < u[i] for i in range(1, 5))
        is_first_breakout = c[0] > (u[0] * 1.005)
        is_vol_ok = v0 > (v_avg * 1.2)

        if was_squeezing and is_first_breakout and is_vol_ok:
            return {
                "產業": info.group,
                "代碼": stock_id,
                "名稱": info.name,
                "價格": round(float(c[0]), 2),
                "漲幅": f"{round(((c[0]/c[1])-1)*100, 2)}%",
                "量能倍數": round(float(v0/v_avg), 2)
            }
    except:
        return None

# 介面按鈕
if st.button("🚀 開始全市場掃描"):
    all_stocks = [code for code, info in twstock.codes.items() 
                  if info.type == '股票' and info.market in ['上市', '上櫃']]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for i, res in enumerate(executor.map(scan_logic, all_stocks)):
            if res: results.append(res)
            progress_bar.progress((i + 1) / len(all_stocks))
            if i % 100 == 0: status_text.text(f"已掃描 {i} 檔...")

    status_text.text("✅ 掃描完成！")
    
    if results:
        df_res = pd.DataFrame(results).sort_values("量能倍數", ascending=False)
        st.dataframe(df_res, use_container_width=True)
        
        # 產業統計圖表
        st.subheader("📊 產業熱度分析")
        st.bar_chart(df_res['產業'].value_counts())
    else:
        st.warning("今日無符合條件標的。")
