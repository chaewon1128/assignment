# streamlit_app.py

import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.express as px
import pydeck as pdk

# === 파일 존재 여부 체크 & 안내 ===
files_needed = [
    "combined_pol.csv", "ppl_2012.csv", "ppl_2014.csv",
    "trans.csv", "spent.csv", "delivery.csv"
]
st.write("✅ 현재 작업 디렉토리 파일 목록:", os.listdir('.'))
for f in files_needed:
    if not os.path.exists(f):
        st.error(f"❌ 파일 누락 또는 경로 문제: {f}")

# === Streamlit 페이지 설정 ===
st.set_page_config(page_title="서울 대기오염 & 생활행동 대시보드", layout="wide")
st.title("🌏 서울 대기오염 & 생활행동 대시보드")
st.markdown(
    """
    - 자치구, 연도 선택 후 미세먼지, 유동인구, 교통, 소비, 배달 시각화  
    - 홍보 및 정책 관점 인사이트 추출에 최적화  
    """
)

# === 데이터 로딩 함수 ===
@st.cache_data
def load_data():
    pol = pd.read_csv("combined_pol.csv")
    ppl_2012 = pd.read_csv("ppl_2012.csv")
    ppl_2014 = pd.read_csv("ppl_2014.csv")
    trans = pd.read_csv("trans.csv")
    spent = pd.read_csv("spent.csv")
    deliver = pd.read_csv("delivery.csv")
    return pol, ppl_2012, ppl_2014, trans, spent, deliver

pol, ppl_2012, ppl_2014, trans, spent, deliver = load_data()

# === 사이드바 필터 ===
with st.sidebar:
    st.header("🔎 분석 필터")
    gu_list = sorted(pol["자치구"].unique())
    selected_gus = st.multiselect("자치구 선택", gu_list, default=gu_list[:5])
    years = st.slider("연도 범위 선택", min_value=2012, max_value=2024, value=(2019, 2023))
    st.markdown("---")
    st.info("마지막 탭에서 데이터 파일 다운로드 가능합니다.")

# === 미세먼지 데이터 필터링 ===
pol_filtered = pol[
    (pol["자치구"].isin(selected_gus)) &
    (pol["일시"].str.slice(0,4).astype(int).between(years[0], years[1]))
]

# --- 미세먼지 라인차트 ---
st.subheader("📈 미세먼지 (PM10) 연도·자치구별 추이")
if not pol_filtered.empty:
    pm10_pivot = pol_filtered.pivot_table(index='일시', columns='자치구', values='미세먼지(PM10)')
    st.line_chart(pm10_pivot)
else:
    st.warning("선택 조건에 맞는 미세먼지 데이터가 없습니다.")

# --- 미세먼지 박스플롯 ---
st.subheader("☁️ 미세먼지 분포 (자치구별 Boxplot)")
select_box_gus = pol[pol["자치구"].isin(selected_gus)]
fig, ax = plt.subplots(figsize=(12, 5))
sns.boxplot(data=select_box_gus, x="자치구", y="미세먼지(PM10)", ax=ax)
plt.xticks(rotation=45)
st.pyplot(fig, use_container_width=True)

# === 유동인구 시각화 ===
st.subheader("🚶 유동인구 비교 (2012년 vs 2014년)")

col1, col2 = st.columns(2)
with col1:
    st.markdown("### 2012년 유동인구")
    ppl_2012_filtered = ppl_2012[ppl_2012['거주지'].isin(selected_gus)]
    ppl_2012_plot = ppl_2012_filtered.set_index('거주지')['개수'].reindex(selected_gus).fillna(0)
    st.bar_chart(ppl_2012_plot)

with col2:
    st.markdown("### 2014년 유동인구")
    ppl_2014_filtered = ppl_2014[ppl_2014['거주지'].isin(selected_gus)]
    ppl_2014_plot = ppl_2014_filtered.set_index('거주지')['개수'].reindex(selected_gus).fillna(0)
    st.bar_chart(ppl_2014_plot)

# === 대중교통 승객 수 추이 ===
st.subheader("🚇 대중교통 승객 수 변화")
trans_filtered = trans[(trans['자치구'].isin(selected_gus)) & 
                       (trans['기준_날짜'].str[:4].astype(int).between(years[0], years[1]))]
if not trans_filtered.empty:
    trans_pivot = trans_filtered.pivot(index='기준_날짜', columns='자치구', values='승객_수')
    st.line_chart(trans_pivot)
else:
    st.info("대중교통 데이터 없음")

# === 상권 지출 현황 시각화 ===
st.subheader("💰 상권별 분기 지출 현황")
spent_filtered = spent[(spent['자치구'].isin(selected_gus)) & (spent['기준_년분기_코드'] < 20241)]
spent_filtered['년월'] = spent_filtered['기준_년분기_코드'].astype(str).apply(lambda x: x[:-1]+'0'+x[-1] if len(x)==5 else x)
pivot_spent = spent_filtered.pivot(index='년월', columns='자치구', values='지출_총금액')
st.line_chart(pivot_spent)

# === 배달 외식 매출 추이 ===
st.subheader("🍲 배달 외식 매출 변화 (2020~2025년)")
deliver.set_index('Date', inplace=True)
st.line_chart(deliver['전체'])

# === 지도에 미세먼지 평균 농도 표시 ===
st.subheader("🗺️ 자치구별 미세먼지 연평균 (선택 연도 내)")

seoul_gu_latlon = {
    '강남구': (37.5172,127.0473), '강동구': (37.5301,127.1237), '강북구': (37.6396,127.0256),
    '강서구': (37.5509,126.8495), '관악구': (37.4781,126.9516), '광진구': (37.5386,127.0823),
    '구로구': (37.4954,126.8581), '금천구': (37.4600,126.9002), '노원구': (37.6544,127.0568),
    '도봉구': (37.6688,127.0477), '동대문구': (37.5744,127.0396), '동작구': (37.5124,126.9396),
    '마포구': (37.5634,126.9087), '서대문구': (37.5792,126.9368), '서초구': (37.4837,127.0324),
    '성동구': (37.5633,127.0363), '성북구': (37.6061,127.0220), '송파구': (37.5145,127.1067),
    '양천구': (37.5169,126.8666), '영등포구': (37.5264,126.8963), '용산구': (37.5326,126.9907),
    '은평구': (37.6176,126.9227), '종로구': (37.5735,126.9797), '중구': (37.5636,126.9976), '중랑구': (37.6063,127.0926)
}

map_data = pol_filtered.groupby('자치구')['미세먼지(PM10)'].mean().reset_index()
map_data['lat'] = map_data['자치구'].map(lambda x: seoul_gu_latlon.get(x, (0,0))[0])
map_data['lon'] = map_data['자치구'].map(lambda x: seoul_gu_latlon.get(x, (0,0))[1])

layer = pdk.Layer(
    'ScatterplotLayer',
    data=map_data,
    get_position='[lon, lat]',
    get_fill_color='[255, 140, 0, 160]',
    get_radius=2000,
    pickable=True,
)

view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10)

st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state,
                        tooltip={"text": "{자치구}\n평균 미세먼지: {미세먼지(PM10)}"}))

# === 데이터 다운로드 ===
st.subheader("📥 분석에 사용된 데이터 다운로드")
for file_name in files_needed:
    with open(file_name, 'rb') as f:
        st.download_button(label=f'Download {file_name}', data=f, file_name=file_name)

st.markdown("---")
st.caption("Developed by your PR/Data Analysis Toolkit")
