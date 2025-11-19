import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

st.set_page_config(page_title="서울 미세먼지 생활지표 인사이트", layout="wide")

files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv", "delivery.csv", "combined_pol.csv", "trans.csv"]
for f in files_needed:
    if not os.path.exists(f):
        st.error(f"❌ 파일이 경로에 없습니다: {f}")

# ---------------- 데이터 로딩 ----------------
spent = pd.read_csv("spent.csv")
ppl_2012 = pd.read_csv("ppl_2012.csv")
ppl_2014 = pd.read_csv("ppl_2014.csv")
delivery = pd.read_csv("delivery.csv")
pol = pd.read_csv("combined_pol.csv")
trans = pd.read_csv("trans.csv")

# ---------------- 연도/자치구 선택 ----------------
YEARS = ['2019', '2020', '2021', '2022']
GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))

# ---- 미세먼지: 자치구-연평균 ----
pol['연'] = pol['일시'].astype(str).str[:4]
pol_y = pol[(pol['연'].isin(YEARS)) & (pol['자치구'] != '평균')]
pm_year_gu = pol_y.groupby(['연', '자치구'])['미세먼지(PM10)'].mean().unstack()

st.title("서울 미세먼지 및 생활지표 인사이트 대시보드")
st.markdown("#### 자치구별 미세먼지 (연도별 패턴)")

fig, ax = plt.subplots(figsize=(12,5))
sns.heatmap(pm_year_gu, cmap="YlOrRd", annot=True, fmt=".0f", ax=ax)
plt.xlabel("자치구")
plt.ylabel("연도")
plt.title("연도별 자치구별 연평균 미세먼지(PM10)")
st.pyplot(fig, use_container_width=True)

# ---- 지출: 자치구-연평균 ----
spent['연'] = spent['기준_년분기_코드'].astype(str).str[:4]
spent_y = spent[(spent['연'].isin(YEARS))]
spent_gu = spent_y.groupby(['연', '자치구'])['지출_총금액'].sum().unstack()

st.markdown("#### 자치구별 연도별 연간 총지출")
fig2, ax2 = plt.subplots(figsize=(12,5))
sns.heatmap(spent_gu.apply(np.log1p), cmap="BuGn", annot=False, ax=ax2)
plt.xlabel("자치구")
plt.ylabel("연도")
plt.title("연도별 자치구별 총지출 (log scale)")
st.pyplot(fig2, use_container_width=True)

# ---- 유동인구: ppl_2012 vs ppl_2014 ----
st.markdown("#### 자치구별 유동인구 변화 (2012→2014)")
ppl2012 = ppl_2012.set_index("거주지").reindex(GUS)["개수"].fillna(0)
ppl2014 = ppl_2014.set_index("거주지").reindex(GUS)["개수"].fillna(0)
move_df = pd.DataFrame({"2012": ppl2012, "2014": ppl2014})
move_df["증감(2014-2012)"] = move_df["2014"] - move_df["2012"]
st.bar_chart(move_df[["2012", "2014"]])

# ---- 대중교통: 최근 연도별 자치구별 일평균 ----
trans['연'] = trans['기준_날짜'].astype(str).str[:4]
trans_sub = trans[trans['연'].isin(['2021','2022'])]
trans_gu = trans_sub.groupby(['연', '자치구'])['승객_수'].sum().unstack(fill_value=0)

st.markdown("#### 대중교통 연도별 자치구별 이용(합계)")
fig3, ax3 = plt.subplots(figsize=(12,5))
sns.heatmap(trans_gu.apply(np.log1p), cmap="Blues", annot=False, ax=ax3)
plt.xlabel("자치구")
plt.ylabel("연도")
plt.title("연도별 자치구별 대중교통 승객수 (log scale)")
st.pyplot(fig3, use_container_width=True)

# ---- 배달 매출: 시계열 -->
st.markdown("#### 서울 배달 매출 전체 변화 (2020 이후)")
if 'Date' in delivery.columns:
    delivery['Date'] = pd.to_datetime(delivery['Date'])
    delivery = delivery.sort_values('Date')
    st.line_chart(delivery.set_index('Date')['전체'])
else:
    st.line_chart(delivery.iloc[:,1])

# ---- 연평균 미세먼지-지출-승객수-유동인구 상관 Heatmap ----
st.markdown("#### 🚩 지표 상관관계(구별, 연도별 평균값)")
# 맞춰진 구와 연도별 summary row 만들기
corr_df = pd.DataFrame(index=YEARS, columns=pd.MultiIndex.from_product([GUS, ['pm','spent','trans','ppl2012','ppl2014']]))

for y in YEARS:
    for gu in GUS:
        pm = pm_year_gu.loc[y,gu] if (y in pm_year_gu.index) and (gu in pm_year_gu.columns) else np.nan
        sp = spent_gu.loc[y,gu] if (y in spent_gu.index) and (gu in spent_gu.columns) else np.nan
        tr = trans_gu.loc[y,gu] if (y in trans_gu.index) and (gu in trans_gu.columns) else np.nan
        p2012 = move_df.loc[gu,"2012"] if gu in move_df.index else np.nan
        p2014 = move_df.loc[gu,"2014"] if gu in move_df.index else np.nan
        corr_df.loc[y,(gu,'pm')] = pm
        corr_df.loc[y,(gu,'spent')] = sp
        corr_df.loc[y,(gu,'trans')] = tr
        corr_df.loc[y,(gu,'ppl2012')] = p2012
        corr_df.loc[y,(gu,'ppl2014')] = p2014

# 전체적으로 평균치(년도X자치구)별 상관관계
flat_corr = corr_df.stack().dropna().astype(float).reset_index().pivot_table(index='level_1',values=[0,1,2,3,4],aggfunc='mean')
flat_corr.columns=['pm','spent','trans','ppl2012','ppl2014']
corr_mat = flat_corr.corr()

fig4, ax4 = plt.subplots(figsize=(6,5))
sns.heatmap(corr_mat, annot=True, fmt=".2f", cmap='vlag', ax=ax4)
plt.title("미세먼지-지출-교통-유동인구 상관 Heatmap")
plt.tight_layout()
st.pyplot(fig4)

# ---- 데이터 다운로드 ----
st.markdown("---")
st.header("📦 CSV 데이터 다운로드")
for fname in files_needed:
    with open(fname, "rb") as f:
        st.download_button(label=f'{fname} 다운로드', data=f, file_name=fname)

st.caption("2025 서울 미세먼지(생활지표) 데이터 대시보드 by AI")
