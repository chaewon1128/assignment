import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("🚗 교통사고 데이터 분석 Dashboard")

# 데이터 불러오기
df = pd.read_csv("accident.csv")

# 날짜 변환
df['date'] = pd.to_datetime(df['date'])
df['year'] = df['date'].dt.year
df['month'] = df['date'].dt.month
df['hour'] = pd.to_datetime(df['time'], format="%H:%M").dt.hour

# ------------------------------
# 사이드바 필터
# ------------------------------
st.sidebar.header("필터")
selected_year = st.sidebar.selectbox("연도 선택", sorted(df['year'].unique()))
selected_region = st.sidebar.multiselect("지역 선택", df['region'].unique(), default=df['region'].unique())

df_filtered = df[(df['year'] == selected_year) & (df['region'].isin(selected_region))]

st.subheader(f"📊 {selected_year}년 교통사고 데이터 ({len(df_filtered)}건)")

# ------------------------------
# 1) 사고 유형별 건수
# ------------------------------
fig1, ax1 = plt.subplots()
df_filtered['type'].value_counts().plot(kind='bar', ax=ax1)
ax1.set_title("사고 유형별 발생 건수")
ax1.set_xlabel("사고 유형")
ax1.set_ylabel("건수")
st.pyplot(fig1)

# ------------------------------
# 2) 시간대별 사고 건수
# ------------------------------
fig2, ax2 = plt.subplots()
df_filtered['hour'].value_counts().sort_index().plot(kind='line', ax=ax2)
ax2.set_title("시간대별 사고 발생 추이")
ax2.set_xlabel("시간")
ax2.set_ylabel("건수")
st.pyplot(fig2)

# ------------------------------
# 3) 월별 사고 추세
# ------------------------------
fig3, ax3 = plt.subplots()
df_filtered['month'].value_counts().sort_index().plot(kind='bar', ax=ax3)
ax3.set_title("월별 사고 발생 추이")
ax3.set_xlabel("월")
ax3.set_ylabel("건수")
st.pyplot(fig3)
