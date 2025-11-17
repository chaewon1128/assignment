import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="교통사고 데이터 분석", layout="wide")

st.title("🚗 교통사고 데이터 분석 Dashboard")

# ------------------------------
# 데이터 로드
# ------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("accident.csv", encoding='utf-8')
    
    # 날짜 변환
    df['ACC_DTTM'] = pd.to_datetime(df['ACC_DTTM'])
    df['year'] = df['ACC_DTTM'].dt.year
    df['month'] = df['ACC_DTTM'].dt.month
    df['hour'] = df['ACC_DTTM'].dt.hour
    return df

df = load_data()

# ------------------------------
# 사이드바 필터
# ------------------------------
st.sidebar.header("필터 설정")

# 연도 필터
years = sorted(df['year'].unique())
selected_year = st.sidebar.selectbox("연도 선택", years)

# 시도 필터
sido_list = sorted(df['SIDO'].unique())
selected_sido = st.sidebar.multiselect("시도 선택", sido_list, default=sido_list)

# 시군구 필터
filtered_sigungu = df[df["SIDO"].isin(selected_sido)]["SIGUNGU"].unique()
selected_sigungu = st.sidebar.multiselect("시군구 선택", filtered_sigungu, default=filtered_sigungu)

# 데이터 필터 적용
df_filtered = df[
    (df['year'] == selected_year) &
    (df['SIDO'].isin(selected_sido)) &
    (df['SIGUNGU'].isin(selected_sigungu))
]

st.subheader(f"📊 {selected_year}년 선택된 지역 교통사고 데이터 ({len(df_filtered)}건)")

# ------------------------------
# 1) 사고 유형별 건수
# ------------------------------
st.markdown("### 1) 사고 유형별 발생 건수")

fig1, ax1 = plt.subplots()
df_filtered['A_TYPE'].value_counts().plot(kind='bar', ax=ax1)
ax1.set_title("사고 유형별 발생 건수")
ax1.set_xlabel("사고 유형")
ax1.set_ylabel("건수")
st.pyplot(fig1)

# ------------------------------
# 2) 시간대별 사고 발생 추이
# ------------------------------
st.markdown("### 2) 시간대별 사고 발생 추이")

fig2, ax2 = plt.subplots()
df_filtered['hour'].value_counts().sort_index().plot(kind='line', ax=ax2)
ax2.set_title("시간대별 사고 발생 추이")
ax2.set_xlabel("시간")
ax2.set_ylabel("건수")
st.pyplot(fig2)

# ------------------------------
# 3) 월별 사고 발생 추세
# ------------------------------
st.markdown("### 3) 월별 사고 발생 추이")

fig3, ax3 = plt.subplots()
df_filtered['month'].value_counts().sort_index().plot(kind='bar', ax=ax3)
ax3.set_title("월별 사고 발생 추이")
ax3.set_xlabel("월")
ax3.set_ylabel("건수")
st.pyplot(fig3)

# ------------------------------
# 4) 기상상태별 사고 비율
# ------------------------------
st.markdown("### 4) 기상상태별 사고 비율")

fig4, ax4 = plt.subplots()
df_filtered['WETHR_COND'].value_counts().plot(kind='pie', autopct='%1.1f%%', ax=ax4)
ax4.set_ylabel("")
ax4.set_title("기상상태별 사고 비율")
st.pyplot(fig4)

# ------------------------------
# 5) 도로 형태별 사고 건수
# ------------------------------
st.markdown("### 5) 도로 형태별 사고 건수")

fig5, ax5 = plt.subplots()
df_filtered['ROAD_TYPE'].value_counts().plot(kind='bar', ax=ax5)
ax5.set_title("도로 형태별 사고 건수")
ax5.set_xlabel("도로 형태")
ax5.set_ylabel("건수")
st.pyplot(fig5)

st.success("✅ 분석 완료! 좌측 필터를 조정하여 다양한 시각화를 확인해보세요.")
