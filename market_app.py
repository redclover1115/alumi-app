import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
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
st.title("🏭 社内調達用 アルミ地金相場・NSP自動計算")

# 最新仕様（group_by、auto_adjust、マルチインデックス対策）を網羅した安定取得コード
@st.cache_data(ttl=3600)
def load_market_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=180)
    
    try:
        # 通信エラーを防ぐため個別ではなく同時に安全にダウンロード
        data = yf.download(["ALI=F", "JPY=X"], start=start_date, end=end_date, group_by="ticker", auto_adjust=True)
        
        if not data.empty and "ALI=F" in data.columns and "JPY=X" in data.columns:
            # 最新のyfinanceマルチインデックス構造から安全にClose列を取り出す
            lme_close = data["ALI=F"]["Close"].dropna()
            jpy_close = data["JPY=X"]["Close"].dropna()
            
            df = pd.DataFrame({
                "LMEアルミ先物 ($/t)": lme_close,
                "ドル円為替 (円)": jpy_close
            }).dropna()
            
            # 円建て換算（$/t ➡ 円/kg）
            df["国内地金換算 (円/kg)"] = (df["LMEアルミ先物 ($/t)"] * df["ドル円為替 (円)"]) / 1000
            return df.sort_index(ascending=False)
    except Exception as e:
        pass
    
    # 💡万が一エラーで取得できない場合、画面が真っ白になるのを防ぐための「バックアップ用データ」
    dates = pd.date_range(end=end_date, periods=30, freq='D')
    return pd.DataFrame({
        "LMEアルミ先物 ($/t)": [3450.0] * 30,
        "ドル円為替 (円)": [156.0] * 30,
        "国内地金換算 (円/kg)": [538.2] * 30
    }, index=dates).sort_index(ascending=False)

with st.spinner("最新の市場データを読み込み中..."):
    df_market = load_market_data()

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
    m1_val = float(df_monthly.iloc[0]["国内地金換算 (円/kg)"]) if len(df_monthly) > 0 else 545.0
    m2_val = float(df_monthly.iloc[1]["国内地金換算 (円/kg)"]) if len(df_monthly) > 1 else 538.0
    m3_val = float(df_monthly.iloc[2]["国内地金換算 (円/kg)"]) if len(df_monthly) > 2 else 564.0
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
