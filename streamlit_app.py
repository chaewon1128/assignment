# app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pydeck as pdk
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="교통사고 데이터 분석", layout="wide")
st.title("🚗 교통사고 데이터 분석 Dashboard")

# -------------------------
# 유틸: 컬럼 유추 함수
# -------------------------
def find_col(df, candidates):
    """DataFrame과 후보 컬럼명 리스트를 받아 실제 존재하는 컬럼명을 반환(없으면 None)."""
    for c in candidates:
        if c in df.columns:
            return c
    # 소문자/대문자 무시해서 검색
    lc = {col.lower(): col for col in df.columns}
    for c in candidates:
        if c.lower() in lc:
            return lc[c.lower()]
    return None

# -------------------------
# 데이터 로드 또는 샘플
# -------------------------
st.sidebar.header("데이터 입력")
upload = st.sidebar.file_uploader("CSV 또는 Excel 파일 업로드 (TAAS 등)", type=["csv","xlsx","xls"])
use_sample = st.sidebar.checkbox("샘플 데이터 사용 (테스트용)", value=False)

if upload is None and not use_sample:
    st.info("왼쪽에서 파일을 업로드하거나 '샘플 데이터 사용'을 체크하세요.")
    st.stop()

@st.cache_data
def load_df_from_upload(uploaded_file):
    if uploaded_file.name.lower().endswith(('.xls', '.xlsx')):
        df = pd.read_excel(uploaded_file, engine='openpyxl')
    else:
        df = pd.read_csv(uploaded_file, low_memory=False)
    return df

@st.cache_data
def sample_df():
    # 샘플 데이터: ACC_DTTM, SIDO, SIGUNGU, A_TYPE, CASLT_CNT, WETHR_COND, ROAD_TYPE, LAT, LON
    rng = pd.date_range("2023-01-01", periods=1000, freq="6H")
    n = len(rng)
    df = pd.DataFrame({
        "ACC_DTTM": rng,
        "SIDO": np.random.choice(["서울특별시","경기도","부산광역시","대구광역시"], n),
        "SIGUNGU": np.random.choice(["강남구","노원구","수원시","해운대구","달서구"], n),
        "A_TYPE": np.random.choice(["차대차","차대사람","차량단독","추돌"], n),
        "CASLT_CNT": np.random.poisson(1.2, n),
        "WETHR_COND": np.random.choice(["맑음","비","눈","안개","흐림"], n, p=[0.6,0.2,0.05,0.05,0.1]),
        "ROAD_TYPE": np.random.choice(["교차로","일반도로","고속도로","터널","횡단보도"], n),
    })
    # 임의 좌표(서울 중심 근처 분포)
    lat0, lon0 = 37.56, 126.97
    df["LAT"] = lat0 + (np.random.randn(n) * 0.05)
    df["LON"] = lon0 + (np.random.randn(n) * 0.05)
    return df

if use_sample:
    df_raw = sample_df()
else:
    df_raw = load_df_from_upload(upload)

st.sidebar.write(f"데이터 행: {len(df_raw)}, 열: {len(df_raw.columns)}")

# -------------------------
# 자동 컬럼 매핑
# -------------------------
# 후보 이름 리스트(TAAS 등 서로 다른 이름에 대응)
candidates = {
    "datetime": ["ACC_DTTM", "acc_dttm", "accident_datetime", "사고일시", "날짜", "date", "Date"],
    "sido": ["SIDO", "sido", "시도", "시도명"],
    "sigungu": ["SIGUNGU", "sigungu", "시군구", "시군구명"],
    "atype": ["A_TYPE", "atype", "사고유형", "사고_유형", "사고구분"],
    "caslt": ["CASLT_CNT","CASLT","caslt_cnt","사상자수","사상자"],
    "wethr": ["WETHR_COND","WTHR","기상상태","기상"],
    "road": ["ROAD_TYPE","ROAD","도로형태","도로"],
    "lat": ["LAT","lat","위도","latitude","Y"],
    "lon": ["LON","lon","경도","longitude","X"]
}

cols = {}
for k,v in candidates.items():
    cols[k] = find_col(df_raw, v)

st.write("### 🔎 자동으로 인식된 주요 컬럼 (없으면 수동으로 선택하세요)")
col_table = pd.DataFrame.from_dict(cols, orient='index', columns=['detected']).reset_index().rename(columns={'index':'field'})
st.table(col_table)

# 수동 매핑 UI (컬럼명이 자동으로 안잡히면 수동으로 지정)
st.sidebar.markdown("#### (선택) 컬럼 수동 지정")
for key in cols:
    cols[key] = st.sidebar.selectbox(f"{key} 컬럼 선택 (자동:{cols[key]})", options=[None] + list(df_raw.columns), index=0 if cols[key] is None else (1 + list(df_raw.columns).index(cols[key])))

# -------------------------
# 전처리
# -------------------------
df = df_raw.copy()

# 날짜/시간 컬럼 처리
dt_col = cols.get("datetime")
if dt_col:
    try:
        df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
    except Exception:
        # 흔한 형태 분리 가능성 처리
        df[dt_col] = pd.to_datetime(df[dt_col].astype(str).str[:19], errors='coerce')
    df["year"] = df[dt_col].dt.year
    df["month"] = df[dt_col].dt.month
    df["day"] = df[dt_col].dt.day
    df["hour"] = df[dt_col].dt.hour
else:
    st.warning("⚠ 날짜/시간 컬럼을 찾지 못했습니다. 날짜 관련 분석(연도/월/시간)은 불가합니다.")

# 범주 컬럼 이름 통일
if cols.get("sido"):
    df.rename(columns={cols["sido"]: "SIDO"}, inplace=True)
if cols.get("sigungu"):
    df.rename(columns={cols["sigungu"]: "SIGUNGU"}, inplace=True)
if cols.get("atype"):
    df.rename(columns={cols["atype"]: "A_TYPE"}, inplace=True)
if cols.get("caslt"):
    df.rename(columns={cols["caslt"]: "CASLT_CNT"}, inplace=True)
if cols.get("wethr"):
    df.rename(columns={cols["wethr"]: "WETHR_COND"}, inplace=True)
if cols.get("road"):
    df.rename(columns={cols["road"]: "ROAD_TYPE"}, inplace=True)
if cols.get("lat") and cols.get("lon"):
    df.rename(columns={cols["lat"]: "LAT", cols["lon"]: "LON"}, inplace=True)

# 필요한 컬럼이 없을 때 기본값 처리
if "CASLT_CNT" not in df.columns:
    df["CASLT_CNT"] = 0

# 결측치 간단 처리(중요 컬럼)
# (실제 분석에선 더 정교한 처리 권장)
df['A_TYPE'] = df['A_TYPE'].fillna("Unknown")
df['WETHR_COND'] = df['WETHR_COND'].fillna("Unknown")
df['ROAD_TYPE'] = df['ROAD_TYPE'].fillna("Unknown")
df['SIDO'] = df['SIDO'].fillna("Unknown")
df['SIGUNGU'] = df['SIGUNGU'].fillna("Unknown")

st.success("데이터 로드 및 기본 전처리 완료")

# -------------------------
# 사이드바: 필터
# -------------------------
st.sidebar.header("분석 필터")
years = sorted(df['year'].dropna().unique().astype(int)) if 'year' in df.columns else []
if years:
    sel_year = st.sidebar.selectbox("연도 선택", options=years, index=len(years)-1)
else:
    sel_year = None

sido_options = sorted(df['SIDO'].unique())
sel_sido = st.sidebar.multiselect("시도 선택 (여러개 선택 가능)", options=sido_options, default=sido_options)

sigungu_options = sorted(df[df['SIDO'].isin(sel_sido)]['SIGUNGU'].unique())
sel_sigungu = st.sidebar.multiselect("시군구 선택 (여러개 선택 가능)", options=sigungu_options, default=sigungu_options)

atype_options = sorted(df['A_TYPE'].unique())
sel_atype = st.sidebar.multiselect("사고유형 선택", options=atype_options, default=atype_options)

hour_range = None
if 'hour' in df.columns:
    min_h, max_h = int(df['hour'].min()), int(df['hour'].max())
    hour_range = st.sidebar.slider("시간대 범위 (hour)", min_value=0, max_value=23, value=(0,23))
else:
    st.sidebar.write("시간대 데이터 없음")

# 필터 적용
df_f = df.copy()
if sel_year is not None and 'year' in df.columns:
    df_f = df_f[df_f['year'] == sel_year]
if sel_sido:
    df_f = df_f[df_f['SIDO'].isin(sel_sido)]
if sel_sigungu:
    df_f = df_f[df_f['SIGUNGU'].isin(sel_sigungu)]
if sel_atype:
    df_f = df_f[df_f['A_TYPE'].isin(sel_atype)]
if hour_range and 'hour' in df.columns:
    df_f = df_f[(df_f['hour'] >= hour_range[0]) & (df_f['hour'] <= hour_range[1])]

st.write(f"### 선택된 데이터: {len(df_f)} 건")

# -------------------------
# 레이아웃: 좌측 요약 / 우측 상세 그래프
# -------------------------
col1, col2 = st.columns([1,2])

with col1:
    st.subheader("요약 통계")
    st.metric("총 사고 건수", f"{len(df_f):,}")
    st.metric("총 사상자 수", f"{int(df_f['CASLT_CNT'].sum()):,}")
    # 사고 평균 사상자
    st.metric("평균 사상자(사고 당)", f"{df_f['CASLT_CNT'].mean():.2f}")

    st.markdown("#### 상위 사고유형")
    st.table(df_f['A_TYPE'].value_counts().head(8).rename_axis("사고유형").reset_index(name="건수"))

    st.markdown("#### 상위 시군구 (건수)")
    st.table(df_f['SIGUNGU'].value_counts().head(8).rename_axis("시군구").reset_index(name="건수"))

with col2:
    st.subheader("시계열 & 분포")

    # 연도별 추이
    if 'year' in df_f.columns:
        fig, ax = plt.subplots(figsize=(8,3))
        df_f.groupby('year').size().plot(ax=ax, marker='o')
        ax.set_title("연도별 사고 건수")
        ax.set_ylabel("건수")
        st.pyplot(fig)

    # 월별(있다면)
    if 'month' in df_f.columns:
        fig, ax = plt.subplots(figsize=(8,3))
        df_f['month'].value_counts().sort_index().plot(kind='bar', ax=ax)
        ax.set_title("월별 사고 건수")
        ax.set_xlabel("월")
        st.pyplot(fig)

    # 시간대 분포
    if 'hour' in df_f.columns:
        fig, ax = plt.subplots(figsize=(8,3))
        df_f['hour'].value_counts().sort_index().plot(kind='line', marker='o', ax=ax)
        ax.set_title("시간대별 사고 분포")
        ax.set_xlabel("시(hour)")
        st.pyplot(fig)

# -------------------------
# 사고 유형별, 기상별, 도로별 시각화 (중간 섹션)
# -------------------------
st.markdown("---")
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("사고유형별 건수")
    fig, ax = plt.subplots()
    df_f['A_TYPE'].value_counts().plot(kind='bar', ax=ax)
    ax.set_ylabel("건수")
    st.pyplot(fig)

with c2:
    st.subheader("기상상태별 비율")
    fig, ax = plt.subplots()
    df_f['WETHR_COND'].value_counts().plot(kind='pie', autopct="%1.1f%%", ax=ax)
    ax.set_ylabel("")
    st.pyplot(fig)

with c3:
    st.subheader("도로형태별 건수")
    fig, ax = plt.subplots()
    df_f['ROAD_TYPE'].value_counts().plot(kind='bar', ax=ax)
    ax.set_ylabel("건수")
    st.pyplot(fig)

# -------------------------
# 심화: 사상자 수 관련 분석
# -------------------------
st.markdown("---")
st.subheader("사상자 수(심화 분석)")

# 사고 유형별 평균 사상자
avg_caslt_by_type = df_f.groupby('A_TYPE')['CASLT_CNT'].mean().sort_values(ascending=False)
fig, ax = plt.subplots()
avg_caslt_by_type.plot(kind='bar', ax=ax)
ax.set_ylabel("평균 사상자 수")
ax.set_title("사고유형별 평균 사상자")
st.pyplot(fig)

# 기상 + 도로 형태 교차 테이블 (pivot)
st.write("기상상태 × 도로형태 (사상자 합계)")
pivot = pd.pivot_table(df_f, values='CASLT_CNT', index='WETHR_COND', columns='ROAD_TYPE', aggfunc='sum', fill_value=0)
st.dataframe(pivot)

# -------------------------
# 지도 시각화 (좌표가 있을 때)
# -------------------------
st.markdown("---")
st.subheader("지도 시각화 (위도/경도 필요)")

if ('LAT' in df_f.columns) and ('LON' in df_f.columns):
    st.write("반응형 지도 (pydeck)")
    midpoint = (np.nanmean(df_f['LAT']), np.nanmean(df_f['LON']))
    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/light-v8',
        initial_view_state=pdk.ViewState(
            latitude=midpoint[0],
            longitude=midpoint[1],
            zoom=10,
            pitch=0,
        ),
        layers=[
            pdk.Layer(
                "HexagonLayer",
                data=df_f[['LAT','LON']],
                get_position='[LON, LAT]',
                radius=300,
                elevation_scale=4,
                pickable=True,
                elevation_range=[0, 1000],
            ),
            pdk.Layer(
                "ScatterplotLayer",
                data=df_f[['LAT','LON','CASLT_CNT','A_TYPE']].rename(columns={'LAT':'lat','LON':'lon'}),
                get_position='[lon, lat]',
                get_color='[200, 30, 0, 160]',
                get_radius=50,
                pickable=True
            ),
        ],
    ))

    st.write("Folium 지도 (클러스터 표시)")
    m = folium.Map(location=midpoint, zoom_start=11)
    from folium.plugins import MarkerCluster
    marker_cluster = MarkerCluster().add_to(m)
    for idx, r in df_f.dropna(subset=['LAT','LON']).iterrows():
        folium.CircleMarker(location=(r['LAT'], r['LON']),
                            radius=3 + min(10, int(r.get('CASLT_CNT',0))),
                            popup=f"{r.get('A_TYPE','')}, 사상자:{r.get('CASLT_CNT',0)}",
                            color=None,
                            fill=True).add_to(marker_cluster)
    st_folium(m, width=900, height=500)

else:
    st.info("데이터에 LAT/LON(또는 위도/경도) 컬럼이 없습니다. 지도 시각화를 하려면 위도/경도 컬럼을 포함하세요.")

st.markdown("---")
st.info("앱이 필요로 하는 컬럼 예시: ACC_DTTM(사고일시), SIDO, SIGUNGU, A_TYPE(사고유형), CASLT_CNT(사상자수), WETHR_COND(기상), ROAD_TYPE(도로형태), LAT, LON(선택)")
st.success("대시보드 준비 완료 — 왼쪽 사이드바에서 파일 업로드/필터를 변경해 보세요.")
