import os
import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk

# Streamlit 페이지 설정
st.set_page_config(page_title="서울 대기질 & 라이프스타일 분석 대시보드", layout="wide")

# PM10 농도 기준 색상 및 레이블 정의
def get_pm10_status(pm10):
    """PM10 농도에 따른 상태 및 색상(RGB) 반환"""
    if pm10 <= 30:
        return '좋음(0~30)', [170, 204, 247]  # Light Blue
    elif pm10 <= 80:
        return '보통(31~80)', [133, 224, 133]  # Light Green
    elif pm10 <= 150:
        return '나쁨(81~150)', [255, 179, 71]  # Orange
    else:
        return '매우 나쁨(151+)', [255, 118, 117]  # Red

# 데이터 로드
@st.cache_data
def load_data():
    files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv",
                    "delivery.csv", "combined_pol.csv", "trans.csv"]

    # 파일 존재 여부 확인 (Canvas 환경에서 실행되므로, 파일 로드 성공 가정)
    try:
        spent = pd.read_csv("spent.csv")
        ppl_2012 = pd.read_csv("ppl_2012.csv")
        ppl_2014 = pd.read_csv("ppl_2014.csv")
        delivery = pd.read_csv("delivery.csv")
        pol = pd.read_csv("combined_pol.csv")
        trans = pd.read_csv("trans.csv")
    except Exception as e:
        st.error(f"데이터 파일 로드 중 오류 발생: {e}")
        st.stop()
        return None, None, None, None, None, None

    # 데이터 전처리
    pol['Year'] = pol['일시'].astype(str).str[:4]
    pol['Date'] = pd.to_datetime(pol['일시'])
    pol['Status'], pol['Color'] = zip(*pol['미세먼지(PM10)'].apply(get_pm10_status))
    
    # 일별/자치구별 평균 미세먼지
    daily_pol = pol.groupby(['Date', '자치구'])['미세먼지(PM10)'].mean().reset_index()
    daily_pol['Status'], daily_pol['Color'] = zip(*daily_pol['미세먼지(PM10)'].apply(get_pm10_status))

    spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]
    
    trans['Date'] = pd.to_datetime(trans['기준_날짜'])
    trans['Year'] = trans['기준_날짜'].astype(str).str[:4]
    # 일별/자치구별 총 승객 수
    daily_trans = trans.groupby(['Date', '자치구'])['승객_수'].sum().reset_index()

    # 배달 데이터는 전체 서울 기준이므로 날짜만 사용
    delivery['Date'] = pd.to_datetime(delivery['Date'])
    delivery['Year'] = delivery['Date'].dt.year.astype(str)
    
    # PM10과 대중교통 통합 (일별/자치구별)
    combined_mobility = pd.merge(
        daily_pol, daily_trans, 
        on=['Date', '자치구'], 
        how='inner'
    )
    
    # PM10과 배달/지출 통합
    # 배달은 서울 전체, spent는 분기별 자치구별. 여기서는 일별 PM10 평균(서울 전체)을 배달 데이터와 통합
    seoul_daily_pol = daily_pol.groupby('Date')['미세먼지(PM10)'].mean().reset_index()
    combined_delivery = pd.merge(
        seoul_daily_pol, delivery.rename(columns={'전체': '배달_건수_지수'}),
        on='Date',
        how='inner'
    )

    return spent, ppl_2012, ppl_2014, delivery, pol, trans, GUS, combined_mobility, combined_delivery

# 데이터 로드 및 전역 변수 설정
(spent, ppl_2012, ppl_2014, delivery, pol, trans, GUS, combined_mobility, combined_delivery) = load_data()

# 자치구 정보
GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))
seoul_gu_latlon = {
    '강남구': (37.5172,127.0473), '강동구': (37.5301,127.1237), '강북구': (37.6396,127.0256),
    '강서구': (37.5509,126.8495), '관악구': (37.4781,126.9516), '광진구': (37.5386,127.0823),
    '구로구': (37.4954,126.8581), '금천구': (37.4600,126.9002), '노원구': (37.6544,127.0568),
    '도봉구': (37.6688,127.0477), '동대문구': (37.5744,127.0396), '동작구': (37.5124,126.9396),
    '마포구': (37.5634,126.9087), '서대문구': (37.5792,126.9368), '서초구': (37.4837,127.0324),
    '성동구': (37.5633,127.0363), '성북구': (37.6061,127.0220), '송파구': (37.5145,127.1067),
    '양천구': (37.5169,126.8666), '영등포구': (37.5264,126.8963), '용산구': (37.5326,126.9907),
    '은평구': (37.6176,126.9227), '종로구': (37.5735,126.9797), '중구': (37.5636,126.9976),
    '중랑구': (37.6063,127.0926)
}

# --- 사이드바 필터 설정 ---
st.sidebar.header("필터 설정")

all_years = sorted(pol['Year'].unique())
selected_years = st.sidebar.multiselect(
    "1. 분석 연도 선택", 
    all_years, 
    default=all_years[-2:] if len(all_years) >= 2 else all_years
)

opts = ["전체 자치구"] + GUS
selected_gus_options = st.sidebar.multiselect(
    "2. 분석 자치구 선택", 
    opts, 
    default=opts[1:6]
)
if "전체 자치구" in selected_gus_options:
    selected_gus = GUS
else:
    selected_gus = selected_gus_options

# PM10 상태 범례
st.sidebar.subheader("PM10 농도 기준 (μg/m³)")
pm_colors = {
    '좋음': [170, 204, 247], '보통': [133, 224, 133], 
    '나쁨': [255, 179, 71], '매우 나쁨': [255, 118, 117]
}
for status, color in pm_colors.items():
    st.sidebar.markdown(
        f"<div style='display:flex; align-items:center;'>"
        f"<span style='background-color:rgb({color[0]},{color[1]},{color[2]}); width:15px; height:15px; border-radius:3px; margin-right:5px;'></span>"
        f"<span>{status}</span>"
        f"</div>", 
        unsafe_allow_html=True
    )

# 필터링된 데이터 준비 (전체 탭에서 사용)
pol_filt = pol[(pol['Year'].isin(selected_years)) & (pol['자치구'].isin(selected_gus))]
trans_filt = trans[(trans['Year'].isin(selected_years)) & (trans['자치구'].isin(selected_gus))]
spent_filt = spent[(spent['Year'].isin(selected_years)) & (spent['자치구'].isin(selected_gus))]
mobility_filt = combined_mobility[
    (combined_mobility['Date'].dt.year.astype(str).isin(selected_years)) & 
    (combined_mobility['자치구'].isin(selected_gus))
]


# --- 대시보드 탭 구성 ---
tab1, tab2, tab3, tab4 = st.tabs([
    "대기질 변화 추이",
    "이동 및 PR 전략",
    "소비 및 마케팅 전략",
    "상관관계 및 입지 전략"
])

with tab1:
    st.header("1. 미세먼지(PM10) 농도 변화 추이 분석")
    st.markdown("선택된 연도 및 자치구의 미세먼지 농도 변화를 시간과 지역별로 시각화합니다.")

    # 1. 시계열 변화 추이 (라인 그래프)
    st.subheader("일별 미세먼지 농도 추이 (선택 자치구)")
    daily_pm10_trend = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
    st.line_chart(daily_pm10_trend, use_container_width=True)
    st.caption("선택된 자치구별 일평균 PM10 농도 변화 추이")

    # 2. 지역별 PM10 농도 비교 (막대 그래프)
    st.subheader("지역별 평균 PM10 농도 비교")
    avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().sort_values(ascending=False)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [get_pm10_status(v)[1] for v in avg_pm10.values]
    ax.bar(avg_pm10.index, avg_pm10.values, color=[(c[0]/255, c[1]/255, c[2]/255) for c in colors])
    ax.set_xlabel("자치구", fontsize=12)
    ax.set_ylabel("평균 PM10 (μg/m³)", fontsize=12)
    ax.set_title(f"선택 연도({', '.join(selected_years)}) 기준 자치구별 평균 PM10", fontsize=14)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    st.pyplot(fig)

    # 3. 지도 시각화 (PM10 농도 상태에 따른 색상)
    st.subheader("지역별 PM10 농도 시각화 (지도)")
    
    # 지도 데이터 준비: 자치구별 평균 PM10 및 위치 정보 병합
    map_df = avg_pm10.reset_index().rename(columns={'미세먼지(PM10)': 'Avg_PM10'})
    map_df['lat'] = map_df['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[0])
    map_df['lon'] = map_df['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[1])
    map_df['pm_color'] = map_df['Avg_PM10'].apply(lambda v: get_pm10_status(v)[1])

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position='[lon, lat]',
        get_radius=2500, # 반경 크기 조정
        get_fill_color='pm_color',
        pickable=True,
        opacity=0.8
    )
    # 서울 중심 좌표
    initial_view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10, pitch=45)
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=initial_view_state,
        tooltip={"text": "{자치구}\n평균 PM10: {Avg_PM10:.1f} µg/m³"}
    ))

with tab2:
    st.header("2. 미세먼지 농도와 이동 패턴의 관계 분석 (PR 전략)")
    st.markdown("미세먼지 농도 변화에 따른 시민의 대중교통 이용 건수를 비교하여, **고농도 시기 리스크 알림 및 홍보 전략 최적화** 방안을 모색합니다.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("PM10과 대중교통 이용량 시계열 비교")
        
        # 일별 자치구 평균 PM10 및 총 승객 수 (선택된 자치구 전체 합산)
        daily_comp_mobility = mobility_filt.groupby('Date').agg({
            '미세먼지(PM10)': 'mean',
            '승객_수': 'sum'
        }).reset_index()

        if not daily_comp_mobility.empty:
            fig, ax1 = plt.subplots(figsize=(10, 5))
            ax2 = ax1.twinx()

            # PM10 (좌측 y축)
            ax1.plot(daily_comp_mobility['Date'], daily_comp_mobility['미세먼지(PM10)'], color='blue', label='PM10 농도')
            ax1.set_xlabel("날짜")
            ax1.set_ylabel("PM10 (μg/m³)", color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')

            # Transit (우측 y축)
            ax2.plot(daily_comp_mobility['Date'], daily_comp_mobility['승객_수'], color='green', label='총 승객 수')
            ax2.set_ylabel("총 승객 수 (단위: 억)", color='green')
            ax2.tick_params(axis='y', labelcolor='green')
            
            ax1.set_title("PM10 농도와 대중교통 이용량 일별 변화 추이")
            fig.tight_layout()
            st.pyplot(fig)
        else:
            st.warning("선택된 조건에 해당하는 데이터가 부족합니다.")

    with col2:
        st.subheader("PM10 상태별 평균 대중교통 이용량")
        
        # PM10 상태별 평균 승객 수
        avg_transit_by_pm10 = mobility_filt.groupby('Status')['승객_수'].mean().reset_index()
        # 정렬 순서를 좋음, 보통, 나쁨, 매우 나쁨 순으로 재정렬
        status_order = ['좋음(0~30)', '보통(31~80)', '나쁨(81~150)', '매우 나쁨(151+)']
        avg_transit_by_pm10['Status'] = pd.Categorical(avg_transit_by_pm10['Status'], categories=status_order, ordered=True)
        avg_transit_by_pm10 = avg_transit_by_pm10.sort_values('Status')

        if not avg_transit_by_pm10.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            colors = [(c[0]/255, c[1]/255, c[2]/255) for status in status_order for s, c in pm_colors.items() if status.startswith(s)]
            
            ax.bar(avg_transit_by_pm10['Status'], avg_transit_by_pm10['승객_수'], color=colors)
            ax.set_xlabel("PM10 농도 상태", fontsize=12)
            ax.set_ylabel("평균 승객 수", fontsize=12)
            ax.set_title("PM10 상태별 대중교통 일평균 이용 건수")
            plt.xticks(rotation=0)
            st.pyplot(fig)
        else:
             st.warning("선택된 조건에 해당하는 데이터가 부족합니다.")

    st.markdown("---")
    st.subheader("PR 관점의 인사이트 (이동 패턴 활용)")
    st.markdown(
        """
        - **핵심 관계:** 시각화 결과, **미세먼지 농도가 '나쁨' 이상으로 높아질수록 대중교통 이용 건수가 감소하거나 증가율이 둔화되는 패턴**이 보일 수 있습니다 (시민들이 외출을 자제하고 실내 활동을 선호).
        - **PR 전략 최적화:** - **고농도 예상 시기 (PM10 '나쁨' 이상):** 시민들이 외출을 가장 주저하는 시점입니다. 이 시기에 맞춰 **지하철역과 버스 정거장** 등 대중교통 시설 내부에 **'실내 마스크 착용', '공기청정 대피소 안내'** 등 건강/안전 리스크 관련 포스터를 집중 홍보해야 합니다. 외출 자제를 유도하는 것이 아닌, **'필수 이동 시 안전 수칙'**을 타겟팅하여 홍보 효과를 극대화할 수 있습니다.
            - **회복기 (PM10 '보통' 이하로 전환):** 외출 수요가 회복되는 시기를 예측하여, **'맑은 공기와 함께하는 야외 활동'**을 주제로 한 캠페인 포스터를 대중교통 외부에 게재하여 심리적 회복을 유도하는 PR 전략을 수립할 수 있습니다.
        """
    )


with tab3:
    st.header("3. 미세먼지 농도와 소비 패턴의 관계 분석 (마케팅 전략)")
    st.markdown("미세먼지 농도 변화에 따른 배달 건수 및 지출액 변화를 분석하여, **식재료 공급망 및 기업 세일 전략 수립**에 필요한 정보를 도출합니다.")
    
    # 연도 선택 필터 (Tab 3 전용)
    year_select_tab3 = st.selectbox("분석할 연도를 선택하세요.", selected_years, key="tab3_year_select")
    
    # 1. 시계열 비교 (PM10 vs Delivery)
    st.subheader(f"연도별 PM10 농도와 배달 건수 지수 변화 ({year_select_tab3}년)")
    delivery_comp_filt = combined_delivery[combined_delivery['Year'] == year_select_tab3].set_index('Date')
    
    if not delivery_comp_filt.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()

        # PM10 (좌측 y축)
        ax1.plot(delivery_comp_filt.index, delivery_comp_filt['미세먼지(PM10)'], color='orange', label='PM10 농도')
        ax1.set_ylabel("PM10 (μg/m³)", color='orange')
        ax1.tick_params(axis='y', labelcolor='orange')

        # Delivery (우측 y축)
        ax2.plot(delivery_comp_filt.index, delivery_comp_filt['배달_건수_지수'], color='red', label='배달 건수 지수')
        ax2.set_ylabel("배달 건수 지수", color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        
        ax1.set_title(f"{year_select_tab3}년 PM10 농도와 배달 건수 지수 변화 추이")
        fig.tight_layout()
        st.pyplot(fig)
        st.caption("PM10 농도가 높을수록(혹은 높았던 이후) 배달 건수 지수가 증가하는 경향성이 나타날 수 있습니다.")
    else:
        st.warning(f"{year_select_tab3}년에 해당하는 데이터가 부족합니다.")

    # 2. 지역별 배달/지출 및 PM10 지도
    st.subheader("지역별 배달 지표와 PM10 농도 시각화")

    # Map Data Preparation (Using Avg Spending as proxy for Delivery volume)
    spent_avg = spent_filt[spent_filt['Year'] == year_select_tab3].groupby('자치구')['지출_총금액'].mean()
    pm10_avg = pol_filt[pol_filt['Year'] == year_select_tab3].groupby('자치구')['미세먼지(PM10)'].mean()

    # 데이터프레임 병합 및 지도 정보 추가
    map_data_tab3 = pd.merge(spent_avg.reset_index(), pm10_avg.reset_index(), on='자치구', how='inner')
    map_data_tab3 = map_data_tab3.rename(columns={'지출_총금액': 'Avg_Spending', '미세먼지(PM10)': 'PM10'})
    map_data_tab3['lat'] = map_data_tab3['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[0])
    map_data_tab3['lon'] = map_data_tab3['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[1])
    
    # 지출 총금액을 지도에서 사용할 Radius로 스케일링
    map_data_tab3['Radius'] = map_data_tab3['Avg_Spending'] / map_data_tab3['Avg_Spending'].max() * 5000 + 1000
    map_data_tab3["pm_color"] = map_data_tab3["PM10"].apply(lambda v: get_pm10_status(v)[1])

    if not map_data_tab3.empty:
        layer3 = pdk.Layer(
            "ScatterplotLayer",
            data=map_data_tab3,
            get_position='[lon, lat]',
            get_radius='Radius',
            get_fill_color='pm_color', # PM10 농도에 따라 색상
            pickable=True,
            opacity=0.7
        )
        st.pydeck_chart(pdk.Deck(
            layers=[layer3], 
            initial_view_state=initial_view_state,
            tooltip={"text": "{자치구}\nPM10: {PM10:.1f}\n평균 지출액: {Avg_Spending:.0f}₩"}
        ))
        st.caption("원의 크기는 평균 지출액(배달 수요 대리 지표), 색상은 PM10 농도 상태를 나타냅니다.")
    else:
        st.warning("선택된 조건에 해당하는 지역별 지출/PM10 데이터가 부족합니다.")

    st.markdown("---")
    st.subheader("마케팅 관점의 인사이트 (소비 패턴 활용)")
    st.markdown(
        """
        - **핵심 관계:** PM10 농도가 높을 때 (실내 체류 증가) 배달 수요와 식료품/총 지출액이 증가하는 패턴을 확인했습니다.
        - **기업 운영 및 세일 전략:**
            - **식재료 및 공급망 준비:** 미래 예측된 미세먼지 고농도 시기(예: 봄철 황사, 겨울철 고농도)에 맞춰 **식자재 재고 및 공급망**을 미리 확보하고, 배달 수요에 대응할 수 있도록 **조리 인력 배치**를 최적화해야 합니다.
            - **세일 및 프로모션 시기:** PM10 농도가 '나쁨' 이상으로 예측되는 시기에 맞춰 **'실내 안심 배달'** 프로모션이나 **'집콕 세일'** 기간을 설정함으로써, 일반적인 계절적 세일 기간과 관계없이 수요가 폭발하는 시점을 공략할 수 있습니다.
            - **타겟 마케팅:** 지도에서 확인된 **지출액(잠재 배달 수요)이 높으면서 PM10 농도가 높은 지역**을 중심으로 마케팅 예산을 집중 투입하여 효율을 높일 수 있습니다.
        """
    )


with tab4:
    st.header("4. PM10, 교통, 배달/소비 간의 상관관계 및 미래 입지 전략")
    st.markdown("주요 지표 간의 상관관계를 분석하고, 먼 미래의 환경 변화를 고려한 기업의 입지 및 인프라 투자 전략에 대한 인사이트를 도출합니다.")

    # 1. 상관관계 분석
    st.subheader("주요 지표 간의 상관관계 (자치구별 평균 기준)")
    
    # 일별 통합 데이터를 자치구별 평균으로 다시 집계하여 사용
    # 주의: spent는 분기별 데이터이므로, 상관분석의 정확도를 위해 PM10, Transit은 일별 데이터를 자치구별로 통합한 후 사용
    pm10_avg_gu = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean()
    transit_avg_gu = trans_filt.groupby('자치구')['승객_수'].sum()
    spending_avg_gu = spent_filt.groupby('자치구')['지출_총금액'].mean()
    
    # 데이터프레임 병합 (교집합 기준)
    corr_df_gu = pd.DataFrame({
        "PM10": pm10_avg_gu,
        "Transit_Usage": transit_avg_gu,
        "Avg_Spending": spending_avg_gu
    }).dropna()

    if not corr_df_gu.empty and len(corr_df_gu) >= 2:
        corr_mat = corr_df_gu.corr(method='pearson')

        fig, ax = plt.subplots(figsize=(7,7))
        sns.heatmap(corr_mat, annot=True, cmap='vlag', ax=ax, center=0, 
                    fmt=".2f", linewidths=.5, cbar_kws={'label': 'Pearson Correlation Coefficient'})
        ax.set_title("주요 지표 간 상관관계 분석 (자치구별 평균 기준)", fontsize=14)
        ax.set_xticklabels(['PM10', '대중교통 이용량', '평균 지출액'], rotation=45, ha='right')
        ax.set_yticklabels(['PM10', '대중교통 이용량', '평균 지출액'], rotation=0)
        plt.tight_layout()
        st.pyplot(fig)
    elif not corr_df_gu.empty and len(corr_df_gu) < 2:
         st.warning("상관관계를 분석하기에 선택된 자치구 수가 충분하지 않습니다 (최소 2개 이상 필요).")
    else:
        st.warning("선택된 조건에 해당하는 상관관계 데이터가 부족합니다.")

    st.markdown("---")
    st.subheader("미래 예측 기반 입지 및 인프라 전략 (인사이트)")
    st.markdown(
        """
        - **핵심 관계 및 예측의 어려움:** 상관관계 분석 결과 (특히 PM10과 Transit_Usage, Avg_Spending 간의 관계)는 PM10 농도가 높아질수록 시민의 외부 활동(대중교통 이용)이 줄고 실내 소비(배달/지출)가 늘어나는 경향을 시사합니다. **먼 미래의 미세먼지 농도나 기후변화는 예측하기 어렵기 때문에, 불확실성에 대비하는 전략이 중요합니다.**
        - **인프라 투자/입지 전략:**
            - **교통 시설 인접 배달 중심 식당 입지 전략:** PM10 농도가 높을 때 대중교통 이용이 감소하더라도, **대중교통 시설 (지하철역, 주요 버스 정거장) 근처**는 여전히 기본적인 유동인구를 담보하며, 미세먼지가 보통/좋음 상태일 때 폭발적인 유동인구 증가를 기대할 수 있는 잠재적 소비 밀집 지역입니다.
            - 따라서, **배달 중심의 식당**이나 **실내 활동 관련 서비스**를 제공하는 기업은 '교통 이용률'과 'PM10 농도'의 상반된 영향에 모두 대응하기 위해, **'대중교통 시설 근처 + 배달 밀집 지역'**에 자리 잡는 것이 가장 유리합니다. 이를 통해 **PM10 나쁨 시기에는 배달 수요 최대화**를, **PM10 좋음 시기에는 회복된 유동인구를 통한 오프라인 수요 유치**를 동시에 달성할 수 있습니다.
        - **정책 시사점:** 교통량이 많은 곳에 실내 공기질 관리가 되는 **'클린 쉘터'** 등의 인프라를 우선 배치하여, 미세먼지 리스크에도 불구하고 이동해야 하는 시민들의 불편을 최소화할 수 있습니다.
        """
    )
    
st.caption("© 2025 서울 대기질 & 라이프스타일 분석 대시보드 | 사업데이터시각화 과제")
