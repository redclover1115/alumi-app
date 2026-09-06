import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from decimal import Decimal, ROUND_HALF_UP

# --- パスワード認証機能 ---
def check_password():
    """正解のパスワードが入力されたらTrueを返す"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # すでに認証済みならパス
    if st.session_state["password_correct"]:
        return True

    # パスワード入力画面の表示
    st.title("🔒 社内専用システム：認証画面")
    st.write("このアプリは社内調達メンバー専用です。")
    
    # 💡 ここに社内で共有するパスワードを設定します（自由に変更してください）
    COMPANY_PASSWORD = "APJ_ALUMI_2026" 

    user_password = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if user_password == COMPANY_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    return False

# 認証チェックを実行（間違っていたらここで処理をストップ）
if not check_password():
    st.stop()

# --- ここから下は元のアプリのプログラム ---
st.set_page_config(page_title="アルミ相場管理", layout="wide")
st.title("🏭 社内調達用 アルミ地金相場・NSP自動計算")

@st.cache_data(ttl=3600)
def load_market_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=180)
    df_list = []
    for name, ticker in {"LMEアルミ先物 ($/t)": "ALI=F", "ドル円為替 (円)": "JPY=X"}.items():
        data = yf.download(ticker, start=start_date, end=end_date)
        if not data.empty:
            close_data = data['Close'] if 'Close' in data.columns else data
            df_list.append(pd.DataFrame({name: close_data.iloc[:, 0] if isinstance(close_data, pd.DataFrame) else close_data}))
    if len(df_list) == 2:
        df = pd.concat(df_list, axis=1).dropna()
        df["国内地金換算 (円/kg)"] = (df["LMEアルミ先物 ($/t)"] * df["ドル円為替 (円)"]) / 1000
        return df.sort_index(ascending=False)
    return pd.DataFrame()

with st.spinner("データ取得中..."):
    df_market = load_market_data()

if df_market.empty:
    st.error("データ取得に失敗しました。")
    st.stop()

latest = df_market.iloc[0]
prev = df_market.iloc[1] if len(df_market) > 1 else latest

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="LMEアルミ先物価格 (終値)", value=f"${latest['LMEアルミ先物 ($/t)']:,.1f} / t", delta=f"{latest['LMEアルミ先物 ($/t)'] - prev['LMEアルミ先物 ($/t)']:+.2f}")
with col2:
    st.metric(label="ドル円為替レート", value=f"¥{latest['ドル円為替 (円)']:,.2f}", delta=f"{latest['ドル円為替 (円)'] - prev['ドル円為替 (円)']:+.2f}")
with col3:
    st.metric(label="国内地金換算（計算値）", value=f"¥{latest['国内地金換算 (円/kg)']:,.1f} / kg", delta=f"{latest['国内地金換算 (円/kg)'] - prev['国内地金換算 (円/kg)']:+.1f}")

st.markdown("---")
st.header("📊 直近の地金価格トレンド (円/kg)")
st.line_chart(df_market["国内地金換算 (円/kg)"])

st.markdown("---")
st.header("🧮 NSP（製品価格基準）自動計算")
df_monthly = df_market.resample('ME').mean().sort_index(ascending=False)

col_calc1, col_calc2 = st.columns(2)
with col_calc1:
    m1_val = float(df_monthly.iloc[0]["国内地金換算 (円/kg)"]) if len(df_monthly) > 0 else 650.0
    m2_val = float(df_monthly.iloc[1]["国内地金換算 (円/kg)"]) if len(df_monthly) > 1 else 640.0
    m3_val = float(df_monthly.iloc[2]["国内地金換算 (円/kg)"]) if len(df_monthly) > 2 else 630.0
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
