from datetime import datetime, timedelta, timezone
import io
import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="日本国内ドローン制限・飛行計画マップ", layout="wide")
st.title("🚁 日本国内 ドローン飛行制限 ＆ 飛行計画マップ")
st.caption("出典：国土地理院（地理院タイル） ／ DIPS 2.0 飛行計画データ ※飛行前は必ずDIPS 2.0公式画面で最新規制をご確認ください。")

JST = timezone(timedelta(hours=9))
today_jst = datetime.now(JST).date()

# サイドバー：エリア選択とレイヤー設定
PRESETS = {
    "東京駅・皇居周辺": [35.6812, 139.7671, 13],
    "羽田空港周辺": [35.5494, 139.7798, 12],
    "大阪駅周辺": [34.7024, 135.4959, 12],
    "名古屋駅周辺": [35.1709, 136.8815, 12],
    "福岡空港周辺": [33.5859, 130.4507, 12],
    "札幌駅周辺": [43.0687, 141.3508, 12],
}

with st.sidebar:
    st.header("1. エリア・背景設定")
    area = st.selectbox("エリア移動", list(PRESETS.keys()))
    lat, lon, zoom = PRESETS[area]
    show_photo = st.checkbox("背景を航空写真にする", value=False)

    st.header("2. 飛行制限レイヤー")
    show_did = st.checkbox("人口集中地区（DID・令和2年）", value=True)
    show_airport = st.checkbox("空港等の周辺空域（航空法）", value=True)
    show_prohibited = st.checkbox("小型無人機等飛行禁止法（重要施設等）", value=True)

    st.header("3. DIPS 2.0 飛行計画（直近3日間）")
    st.markdown(
        f"**対象期間:** `{today_jst}` 〜 `{today_jst + timedelta(days=2)}`"
    )
    use_sample_plan = st.checkbox("サンプル飛行計画を表示する", value=True)
    uploaded_file = st.file_uploader(
        "DIPS 2.0 飛行計画CSVをアップロード",
        type=["csv"],
        help="列に「飛行開始日(date)」「緯度(lat)」「経度(lon)」「高度(alt)」「飛行目的(purpose)」を含むCSVを読み込めます。",
    )

# ベースマップ作成
base_tile = (
    "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"
    if show_photo
    else "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png"
)

m = folium.Map(
    location=[lat, lon],
    zoom_start=zoom,
    tiles=base_tile,
    attr="国土地理院",
)

# レイヤー1：人口集中地区（DID）
if show_did:
    folium.TileLayer(
        tiles="https://maps.gsi.go.jp/xyz/did2020/{z}/{x}/{y}.png",
        attr="国土地理院（人口集中地区 令和2年）",
        name="人口集中地区（DID）",
        overlay=True,
        control=True,
        opacity=0.55,
    ).add_to(m)

# 地理院タイルGeoJSON取得用共通関数
@st.cache_data(ttl=86400)
def fetch_gsi_geojson(layer_id: str):
    features = []
    for x in range(224, 236):
        for y in range(95, 107):
            url = f"https://maps.gsi.go.jp/xyz/{layer_id}/8/{x}/{y}.geojson"
            try:
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    features.extend(data.get("features", []))
            except Exception:
                continue
    return {"type": "FeatureCollection", "features": features}

# レイヤー2：空港等の周辺空域
if show_airport:
    airport_geojson = fetch_gsi_geojson("kokuarea")
    if airport_geojson["features"]:
        folium.GeoJson(
            airport_geojson,
            name="空港等の周辺空域",
            style_function=lambda _: {
                "fillColor": "#00AA55",
                "color": "#007733",
                "weight": 1.5,
                "fillOpacity": 0.3,
            },
        ).add_to(m)

# レイヤー3：小型無人機等飛行禁止法対象施設（地理院タイル sikou）
if show_prohibited:
    prohibited_geojson = fetch_gsi_geojson("sikou")
    if prohibited_geojson["features"]:
        folium.GeoJson(
            prohibited_geojson,
            name="小型無人機等飛行禁止法（対象施設周辺）",
            style_function=lambda _: {
                "fillColor": "#9B59B6",
                "color": "#6C3483",
                "weight": 2.0,
                "fillOpacity": 0.45,
            },
        ).add_to(m)

# レイヤー4：DIPS 2.0 直近3日間の飛行計画プロット
def load_flight_plans():
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    if use_sample_plan:
        # 動作確認用の直近3日間のサンプルデータ（東京・羽田周辺）
        d0 = today_jst.strftime("%Y-%m-%d")
        d1 = (today_jst + timedelta(days=1)).strftime("%Y-%m-%d")
        d2 = (today_jst + timedelta(days=2)).strftime("%Y-%m-%d")
        sample_csv = f"""date,lat,lon,radius_m,alt,purpose,operator
{d0},35.6895,139.7600,150,80m,インフラ点検（ビル外壁）,サンプル事業者A
{d1},35.6762,139.7720,200,100m,空撮・測量調査,サンプル事業者B
{d2},35.5620,139.7520,120,60m,橋梁定期点検,サンプル事業者C
"""
        return pd.read_csv(io.StringIO(sample_csv))
    return None

plan_df = load_flight_plans()

if plan_df is not None and not plan_df.empty:
    plan_group = folium.FeatureGroup(name="DIPS 2.0 飛行計画（直近3日間）")
    end_date = today_jst + timedelta(days=2)

    # 日付列で直近3日間にフィルタリング
    plan_df["parsed_date"] = pd.to_datetime(plan_df["date"]).dt.date
    filtered_df = plan_df[
        (plan_df["parsed_date"] >= today_jst) & (plan_df["parsed_date"] <= end_date)
    ]

    for _, row in filtered_df.iterrows():
        p_lat = float(row["lat"])
        p_lon = float(row["lon"])
        radius = float(row.get("radius_m", 150))
        popup_html = (
            f"<b>飛行日:</b> {row['date']}<br>"
            f"<b>高度上限:</b> {row.get('alt', '不明')}<br>"
            f"<b>目的:</b> {row.get('purpose', '記載なし')}<br>"
            f"<b>通報者:</b> {row.get('operator', '非公開')}"
        )
        # 飛行空域の円
        folium.Circle(
            location=[p_lat, p_lon],
            radius=radius,
            color="#FF6600",
            fill=True,
            fill_color="#FF8800",
            fill_opacity=0.35,
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(plan_group)

        # 中心ピン
        folium.Marker(
            location=[p_lat, p_lon],
            icon=folium.Icon(color="orange", icon="plane", prefix="fa"),
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(plan_group)

    plan_group.add_to(m)

# レイヤー切替コントロール
folium.LayerControl(collapsed=False).add_to(m)

# 地図表示
st_folium(m, use_container_width=True, height=650, returned_objects=[])

# 画面下部に直近3日間の飛行計画一覧テーブルを表示
if plan_df is not None and not plan_df.empty:
    st.subheader(f"📋 直近3日間の飛行計画一覧（{today_jst} 〜 {today_jst + timedelta(days=2)}）")
    display_cols = [c for c in ["date", "purpose", "alt", "radius_m", "lat", "lon", "operator"] if c in filtered_df.columns]
    st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)
