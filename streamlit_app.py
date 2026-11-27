Python
import folium
import requests
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="日本国内ドローン制限マップ", layout="wide")
st.title("🚁 日本国内 ドローン飛行制限マップ（レイヤー表示）")
st.caption("出典：国土地理院（地理院タイル） ※実際の飛行前には必ず国土交通省 DIPS 2.0 等で最新規制をご確認ください。")

# サイドバー：初期表示エリアの選択
PRESETS = {
    "東京駅周辺": [35.6812, 139.7671, 12],
    "羽田空港周辺": [35.5494, 139.7798, 12],
    "大阪駅周辺": [34.7024, 135.4959, 12],
    "名古屋駅周辺": [35.1709, 136.8815, 12],
    "福岡空港周辺": [33.5859, 130.4507, 12],
    "札幌駅周辺": [43.0687, 141.3508, 12],
}

with st.sidebar:
    st.header("表示設定")
    area = st.selectbox("エリア移動", list(PRESETS.keys()))
    lat, lon, zoom = PRESETS[area]

    st.subheader("重ねる制限レイヤー")
    show_did = st.checkbox("人口集中地区（DID・令和2年）", value=True)
    show_airport = st.checkbox("空港等の周辺空域（進入表面等）", value=True)
    show_photo = st.checkbox("背景を航空写真にする", value=False)

# ベースマップの作成（国土地理院タイル）
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

# レイヤー1：人口集中地区（DID）タイル（赤系半透明表示）
if show_did:
    folium.TileLayer(
        tiles="https://maps.gsi.go.jp/xyz/did2020/{z}/{x}/{y}.png",
        attr="国土地理院（人口集中地区 令和2年）",
        name="人口集中地区（DID）",
        overlay=True,
        control=True,
        opacity=0.6,
    ).add_to(m)

# レイヤー2：空港等の周辺空域（地理院タイルのタイルGeoJSON）
if show_airport:
    @st.cache_data(ttl=86400)
    def fetch_airport_zones():
        features = []
        for x in range(224, 236):
            for y in range(95, 107):
                url = f"https://maps.gsi.go.jp/xyz/kokuarea/8/{x}/{y}.geojson"
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    features.extend(data.get("features", []))
        return {"type": "FeatureCollection", "features": features}

    airport_geojson = fetch_airport_zones()
    if airport_geojson["features"]:
        folium.GeoJson(
            airport_geojson,
            name="空港等の周辺空域",
            style_function=lambda _: {
                "fillColor": "#00AA55",
                "color": "#007733",
                "weight": 1.5,
                "fillOpacity": 0.35,
            },
        ).add_to(m)

# 地図右上のレイヤー切替コントロールを追加
folium.LayerControl(collapsed=False).add_to(m)

# Streamlit画面に地図を描画
st_folium(m, use_container_width=True, height=650, returned_objects=[])
