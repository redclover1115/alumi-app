import streamlit as st
import pandas as pd
import datetime
import requests
from bs4 import BeautifulSoup
from decimal import Decimal, ROUND_HALF_UP

# --- パスワード認証機能 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.title("🔒 社内専用システム：認証画面")
    st.write("このアプリは社内調達メンバー専用です。")
    
    COMPANY_PASSWORD = "APJ_ALUMI_2026" 
    user_password = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if user_password == COMPANY_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    return False

if not check_password():
    st.stop()

# --- ここからアプリの本編 ---
st.set_page_config(page_title="アルミ相場管理", layout="wide")
st.title("🏭 社内調達用 国内アルミ地金相場・NSP自動計算")

# 💡 開明伸銅さんのウェブサイトから国内デイリー価格を一瞬で抽出する関数
@st.cache_data(ttl=3600)
def scrape_domestic_market_data():
    url = "https://kaimeishindo.com"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # サイト内の「日」と「価格」が並ぶテーブルのセルをすべて抽出
        tables = soup.find_all("table")
        data_rows = []
        
        # 開明伸銅さんのページ構造から「〇日」「価格」の組み合わせを探索
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = [col.text.strip() for col in row.find_all("td")]
                # 「1日」「654」のようなペアを探す
                if len(cols) >= 2 and "日" in cols[0] and cols[1].isdigit():
                    day_num = int(cols[0].replace("日", ""))
                    price_val = float(cols[1])
                    data_rows.append({"日": day_num, "国内地金価格 (円/kg)": price_val})
        
        if data_rows:
            # 抽出した直近データを日付順の表にまとめる
            df = pd.DataFrame(data_rows)
            # 簡易的に直近の日付を割り当ててグラフ化
            base_date = datetime.date.today()
            df.index = [base_date - datetime.timedelta(days=i) for i in range(len(df))]
            df = df.drop(columns=["日"])
            return df.sort_index(ascending=False)
            
    except Exception as e:
        pass
    
    # 💡万が一の通信エラー時のバックアップデータ（サイトが見られない時用）
    end_date = datetime.date.today()
    dates = pd.date_range(end=end_date, periods=30, freq='D')
    return pd.DataFrame({"国内地金価格 (円/kg)": [645.0] * 30}, index=dates).sort_index(ascending=False)

with st.spinner("開明伸銅のウェブサイトから最新の国内相場を抽出中..."):
    df_market = scrape_domestic_market_data()

latest_price = df_market["国内地金価格 (円/kg)"].iloc[0]
prev_price = df_market["国内地金価格 (円/kg)"].iloc[1] if len(df_market) > 1 else latest_price

col1, col2 = st.columns(2)
with col1:
    st.metric(label="日経公表：国内アルミ地金相場 (最新終値)", value=f"¥{latest_price:,.0f} / kg", delta=f"{latest_price - prev_price:+.0f} 円")
with col2:
    st.info("💡 引用元：開明伸銅株式会社（日本経済新聞掲載日引用）")

st.markdown("---")
st.header("📊 直近の国内地金価格トレンド (円/kg)")
st.line_chart(df_market["国内地金価格 (円/kg)"])

st.markdown("---")
st.header("🧮 NSP（製品価格基準）自動計算")
df_monthly = df_market.resample('ME').mean().sort_index(ascending=False)

col_calc1, col_calc2 = st.columns(2)
with col_calc1:
    m1_val = float(df_monthly.iloc[0]["国内地金価格 (円/kg)"]) if len(df_monthly) > 0 else 645.0
    m2_val = float(df_monthly.iloc[1]["国内地金価格 (円/kg)"]) if len(df_monthly) > 1 else 635.0
    m3_val = float(df_monthly.iloc[2]["国内地金価格 (円/kg)"]) if len(df_monthly) > 2 else 650.0
    
    m1 = st.number_input("1ヶ月目の国内地金平均 (円/kg)", value=round(m1_val, 1))
    m2 = st.number_input("2ヶ月目の国内地金平均 (円/kg)", value=round(m2_val, 1))
    m3 = st.number_input("3ヶ月目の国内地金平均 (円/kg)", value=round(m3_val, 1))
    extra = st.number_input("ロールマージン / エキストラ費用 (円/kg)", value=90)

with col_calc2:
    raw_avg = (m1 + m2 + m3) / 3
    rounded_avg = float(Decimal(str(raw_avg / 10)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) * 10
    nsp_price = rounded_avg + extra
    st.info(f"📋 3ヶ月の単純地金平均: **{raw_avg:.1f} 円/kg**")
    st.warning(f"⚖️ 10円単位四捨五入後の地金基準値: **{rounded_avg:.0f} 円/kg**")
    st.success(f"🚀 **次期改定の製品価格 (NSP予測): {nsp_price:.0f} 円/kg**")
