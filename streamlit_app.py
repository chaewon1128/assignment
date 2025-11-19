# streamlit_app.py

import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.express as px
import pydeck as pdk

st.set_page_config(page_title="서울 대기오염 & 생활행동 대시보드", layout="wide")
st.title("🌏 서울 대기오염 & 생활행동 대시보드")
st.markdown(
    """
    - **자치구/연도별 대기오염, 유동인구, 교통, 소비, 배달 데이터를 다각도로 비교해봅니다.**
    - **홍보 및 정책관점에서 PR 인사이트를 쉽게 얻는 대시보드입니다.**
    """
)

@st.cache_data
import os
import streamlit as st

files_needed = [
    "combined_pol.csv", "ppl_2012.csv", "ppl_2014.csv",
    "trans.csv", "spent.csv", "배달외식_매출건수_2020년_1월.csv"
]
st.write("현재 실행 디렉토리 파일 목록:", os.listdir('.'))

for f in files_needed:
    if not os.path.exists(f):
        st.error(f"파일이 누락되었거나 경로가 다릅니다: {f}")

# 이후 기존의 데이터 로딩/분석 코드 작성
def load_data():
    pol = pd.read_csv("combined_pol.csv")
    ppl_2012 = pd.read_csv("ppl_2012.csv")
    ppl_2014 = pd.read_csv("ppl_2014.csv")
    trans = pd.read_csv("trans.csv")
    spent = pd.read_csv("spent.csv")
    deliver = pd.read_csv("배달외식_매출건수_2020년_1월.csv")
    return pol, ppl_2012, ppl_2014, trans, spent, deliver

# 데이터 불러오기
pol, ppl_2012, ppl_2014, trans, spent, deliver = load_data()

# ---- SIDEBAR (공통 선택) ----
with st.sidebar:
    st.header("🔎 필터")
    year_list = sorted(pol["일시"].str[:4].unique())
    gu_list = sorted(pol["자치구"].unique())
    gu_list_selector = st.multiselect("자치구(복수 선택 가능)", gu_list, default=gu_list[:5])
    years = st.slider("연도 범위", int(year_list[0]), int(year_list[-1]), (2019, 2024))
    st.write("작업중인 파일 전체 다운로드는 마지막 탭에서 제공됩니다.")

# ----- 미세먼지 (PM10) ----- #
st.subheader("📊 미세먼지(PM10) 연도·자치구별 트렌드")
subpol = pol[
    pol["자치구"].isin(gu_list_selector) & 
    (pol["일시"].str[:4].astype(int).between(years[0], years[1]))
]
if subpol.empty:
    st.info("선택한 조건에 데이터가 없습니다.")
else:
    st.line_chart(
        subpol.groupby(["일시", "자치구"])["미세먼지(PM10)"].mean().unstack(),
        use_container_width=True
    )

# ---- Boxplot: 미세먼지 분포 ----
st.subheader("☁️ 미세먼지 분포(Boxplot, 자치구별)")
fig, ax = plt.subplots(figsize=(12,5))
sns.boxplot(data=pol[pol["자치구"].isin(gu_list_selector)], x="자치구", y="미세먼지(PM10)", ax=ax)
plt.xticks(rotation=45)
st.pyplot(fig, use_container_width=True)

# ---- 유동인구 변화 ----
st.subheader("🚶 유동인구 (2012, 2014) 비교")
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### 2012")
    st.bar_chart(
        ppl_2012.set_index("거주지")["개수"].reindex(gu_list).fillna(0),
        use_container_width=True,
    )
with col2:
    st.markdown("#### 2014")
    st.bar_chart(
        ppl_2014.set_index("거주지")["개수"].reindex(gu_list).fillna(0),
        use_container_width=True,
    )

# ---- 대중교통 승객 변화 ----
st.subheader("🚇 대중교통 승객 변화")
st.line_chart(
    trans[trans["자치구"].isin(gu_list_selector)].set_index("기준_날짜").pivot(columns="자치구", values="승객_수"),
    use_container_width=True,
)

# ---- 상권 소비 금액 분석 ----
st.subheader("💵 상권 소비(지출) 변화")
st.markdown("##### (기준_년분기_코드 → YYYYMM 변환)")
spent_view = spent.copy()
# 년분기 코드 변환
spent_view["년월"] = spent_view["기준_년분기_코드"].astype(str).apply(lambda x: x[:-1] + '0' + x[-1] if len(x)==5 else x)
spent_view = spent_view[spent_view["기준_년분기_코드"]<20241]
st.line_chart(
    spent_view[spent_view["자치구"].isin(gu_list_selector)].pivot(index="년월", columns="자치구", values="지출_총금액"),
    use_container_width=True,
)

# ---- 배달 매출 변화 ----
st.subheader("🍱 배달외식 매출 변화량 (2020-2025)")
st.line_chart(
    deliver.set_index("Date")["전체"],
    use_container_width=True
)

# ---- 지도 시각화 (예: 미세먼지 평균 자치구별) ----
st.subheader("🗺️ 미세먼지 지도 (자치구별 연평균)")
# 서울 자치구 중심 위경도 (간략 예시 - 실제 repo에서는 csv/mapping 등 활용 추천)
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
year_avg = pol[
    pol["일시"].str[:4].astype(int).between(years[0], years[1])
].groupby("자치구")["미세먼지(PM10)"].mean().reset_index()
year_avg["lat"] = year_avg["자치구"].map(lambda x: seoul_gu_latlon.get(x, (0,0))[0])
year_avg["lon"] = year_avg["자치구"].map(lambda x: seoul_gu_latlon.get(x, (0,0))[1])
layer = pdk.Layer(
    "ScatterplotLayer",
    data=year_avg,
    get_position="[lon, lat]",
    get_fill_color="[255, 140, 0, 160]",
    get_radius=1800,
    pickable=True,
)
st.pydeck_chart(
    pdk.Deck(
        initial_view_state=pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10),
        layers=[layer],
        tooltip={"text": "{자치구}\n미세먼지 평균: {미세먼지(PM10)}"}
    )
)

# ---- 파일 다운로드 탭 ----
st.subheader("📥 데이터 다운로드")
for fname in [
    "combined_pol.csv", "ppl_2012.csv", "ppl_2014.csv",
    "trans.csv", "spent.csv", "배달외식_매출건수_2020년_1월.csv"
]:
    with open(fname, "rb") as f:
        st.download_button(label=f"Download {fname}", data=f, file_name=fname)

st.markdown("---")
st.caption("by PR/빅데이터 분석 자동화 대시보드")


