import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk
import os
import itertools # for combining population data

st.set_page_config(page_title="서울 대기질 & 라이프스타일 분석 대시보드", layout="wide")
st.title("[PR 관점에서 본 서울 미세먼지 농도의 영향 분석 대시보드]")

# matplotlib에서 한글 폰트 설정을 위한 함수 (환경별 폰트 안정적 적용)
def set_matplotlib_korean_font():
    """Matplotlib에서 한글 깨짐 방지 및 다양한 환경 대응 폰트 설정 함수"""
    import platform
    import matplotlib.font_manager as fm
    
    # 플랫폼별 기본 폰트 후보
    if platform.system() == 'Windows':
        font_name = 'Malgun Gothic'
    elif platform.system() == 'Darwin':
        font_name = 'AppleGothic'
    else:  # 리눅스 등 기타
        font_name = 'NanumGothic'

    # 시스템에 폰트가 있는지 우선 확인 후 적용
    if font_name in [f.name for f in fm.fontManager.ttflist]:
        plt.rcParams['font.family'] = font_name
    else:
        # 폰트 미설치 시 기본 폰트 유지, 경고 출력
        st.warning(f"한글 폰트 '{font_name}'를 시스템에서 찾을 수 없습니다. 한글 깨짐이 발생할 수 있습니다.")
    plt.rcParams['axes.unicode_minus'] = False

set_matplotlib_korean_font()

# --- PM10 농도 기준 색상 및 레이블 정의 ---
def get_pm10_status(pm10):
    """PM10 농도에 따른 상태 및 색상(RGB) 반환"""
    if pd.isna(pm10):
        return '미정', [128, 128, 128]
    elif pm10 <= 30:
        return '좋음(0~30)', [170, 204, 247]
    elif pm10 <= 80:
        return '보통(31~80)', [133, 224, 133]
    elif pm10 <= 150:
        return '나쁨(81~150)', [255, 179, 71]
    else:
        return '매우 나쁨(151+)', [255, 118, 117]

# --- 데이터 로드 및 전처리 함수 (기존 코드 유지) ---
@st.cache_data
def load_data():
    files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv",
                    "delivery.csv", "combined_pol.csv", "trans.csv"]
    data_map = {}
    for file_name in files_needed:
        var_name = file_name.replace('.csv', '').replace('combined_', '')
        df = pd.DataFrame()
        try:
            try:
                df = pd.read_csv(file_name, encoding='euc-kr')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_name, encoding='cp949')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_name, encoding='utf-8')
            data_map[var_name] = df
        except FileNotFoundError:
            st.error(f"❌ 데이터 파일 로드 실패: '{file_name}' 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
            data_map[var_name] = pd.DataFrame()
        except Exception as e:
            st.error(f"❌ '{file_name}' 파일 로드 중 심각한 오류 발생: {e}")
            data_map[var_name] = pd.DataFrame()

    pol = data_map.get('pol')
    if pol is None or pol.empty:
        pol = pd.DataFrame()
        daily_pol = pd.DataFrame()
    else:
        pol['일시'] = pol['일시'].astype(str)
        pol['Year'] = pol['일시'].str[:4]
        pol['Date'] = pd.to_datetime(pol['일시'], errors='coerce') 
        pol.dropna(subset=['Date'], inplace=True)
        pol['Status'], pol['Color'] = zip(*pol['미세먼지(PM10)'].apply(get_pm10_status))
        daily_pol = pol.groupby(['Date', '자치구'])['미세먼지(PM10)'].mean().reset_index()
        daily_pol['Status'], daily_pol['Color'] = zip(*daily_pol['미세먼지(PM10)'].apply(get_pm10_status))

    spent = data_map.get('spent')
    if spent is None or spent.empty:
        spent = pd.DataFrame()
    else:
        spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]

    trans = data_map.get('trans')
    if trans is None or trans.empty:
        trans = pd.DataFrame()
        daily_trans = pd.DataFrame()
    else:
        trans['Date'] = pd.to_datetime(trans['기준_날짜'], errors='coerce')
        trans.dropna(subset=['Date'], inplace=True)
        trans['Year'] = trans['기준_날짜'].astype(str).str[:4]
        daily_trans = trans.groupby(['Date', '자치구'])['승객_수'].sum().reset_index()

    delivery = data_map.get('delivery')
    if delivery is None or delivery.empty:
        delivery = pd.DataFrame()
    else:
        delivery.columns = delivery.columns.str.strip().str.replace('"', '')
        delivery = delivery.rename(columns={'전체': '배달_건수_지수'})
        delivery['Date'] = pd.to_datetime(delivery['Date'], errors='coerce')
        delivery.dropna(subset=['Date'], inplace=True)
        delivery['Year'] = delivery['Date'].dt.year.astype(str)

    ppl_2012_df = data_map.get('ppl_2012', pd.DataFrame())
    ppl_2014_df = data_map.get('ppl_2014', pd.DataFrame())

    def preprocess_ppl_data(df, year):
        if df.empty:
            return df
        df = df.rename(columns={'거주지': '자치구', '개수': '인구_이동_건수'})
        df['인구_이동_건수'] = pd.to_numeric(df['인구_이동_건수'], errors='coerce')
        df.dropna(subset=['인구_이동_건수'], inplace=True)
        df['Year'] = str(year)
        seoul_gus_list = ['강남구', '강동구', '강북구', '강서구', '관악구', '광진구', '구로구', '금천구', '노원구', '도봉구', '동대문구', '동작구', '마포구', '서대문구', '서초구', '성동구', '성북구', '송파구', '양천구', '영등포구', '용산구', '은평구', '종로구', '중구', '중랑구']
        return df[df['자치구'].isin(seoul_gus_list)]

    ppl_2012 = preprocess_ppl_data(ppl_2012_df, 2012)
    ppl_2014 = preprocess_ppl_data(ppl_2014_df, 2014)
    if not ppl_2012.empty and not ppl_2014.empty:
        combined_ppl = pd.concat([ppl_2012, ppl_2014], ignore_index=True)
    else:
        combined_ppl = pd.DataFrame()

    if not daily_pol.empty and not daily_trans.empty:
        combined_mobility = pd.merge(
            daily_pol, daily_trans, 
            on=['Date', '자치구'], 
            how='inner'
        )
    else:
        combined_mobility = pd.DataFrame()
    
    if not daily_pol.empty and not delivery.empty:
        seoul_daily_pol = daily_pol.groupby('Date')['미세먼지(PM10)'].mean().reset_index()
        combined_delivery = pd.merge(
            seoul_daily_pol, delivery,
            on='Date',
            how='inner'
        )
    else:
        combined_delivery = pd.DataFrame()

    GUS_df = pd.DataFrame()
    
    return (spent, ppl_2012, ppl_2014, delivery, pol, trans, 
            GUS_df, combined_mobility, combined_delivery, combined_ppl)

try:
    (spent, ppl_2012, ppl_2014, delivery, pol, trans, GUS_df, combined_mobility, combined_delivery, combined_ppl) = load_data()
except Exception as e:
    st.error(f"데이터 로드 과정 중 예측하지 못한 오류가 발생했습니다: {e}")
    st.stop()

if not pol.empty:
    GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))
else:
    GUS = []

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

if pol.empty:
    st.error("🚨 미세먼지 데이터(combined_pol.csv) 로드에 실패하여 대시보드 기능을 사용할 수 없습니다. 파일을 확인해 주세요.")
    st.stop()
elif trans.empty:
    st.warning("⚠️ 대중교통 데이터(trans.csv) 로드에 실패했습니다. '이동 및 PR 전략' 탭의 일부 기능이 제한됩니다.")
elif spent.empty:
    st.warning("⚠️ 지출 데이터(spent.csv) 로드에 실패했습니다. '소비 및 마케팅 전략' 탭의 일부 기능이 제한됩니다.")
elif delivery.empty:
    st.warning("⚠️ 배달 데이터(delivery.csv) 로드에 실패했습니다. '소비 및 마케팅 전략' 탭의 일부 기능이 제한됩니다.")
elif combined_ppl.empty:
    st.warning("⚠️ 인구 이동 데이터(ppl_2012.csv, ppl_2014.csv) 로드에 실패했습니다. '상관관계 및 입지 전략' 탭의 인구 분석 기능이 제한됩니다.")

st.sidebar.header("필터 설정")
all_years = sorted(pol['Year'].unique())
default_years = all_years[-2:] if len(all_years) >= 2 else all_years
selected_years = st.sidebar.multiselect("1. 분석 연도 선택", all_years, default=default_years)
opts = ["전체 자치구"] + GUS
default_gus = opts[1:6] if len(opts) >= 6 else opts[1:]

selected_gus_options = st.sidebar.multiselect("2. 분석 자치구 선택", opts, default=default_gus)
if "전체 자치구" in selected_gus_options:
    selected_gus = GUS
else:
    selected_gus = selected_gus_options

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

pol_filt = pol[(pol['Year'].isin(selected_years)) & (pol['자치구'].isin(selected_gus))]
trans_filt = trans[(trans['Year'].isin(selected_years)) & (trans['자치구'].isin(selected_gus))]
spent_filt = spent[(spent['Year'].isin(selected_years)) & (spent['자치구'].isin(selected_gus))]

if not combined_mobility.empty:
    mobility_filt = combined_mobility[
        (combined_mobility['Date'].dt.year.astype(str).isin(selected_years)) & 
        (combined_mobility['자치구'].isin(selected_gus))
    ].copy()
else:
    mobility_filt = pd.DataFrame()

tab1, tab2, tab3, tab4 = st.tabs([
    "대기질 변화 추이",
    "이동 및 PR 전략",
    "소비 및 마케팅 전략",
    "상관관계 및 입지 전략"
])

with tab1:
    st.markdown("<h2 style='margin-bottom:10px;'>1. 미세먼지(PM10) 농도 변화 추이 분석</h2>", unsafe_allow_html=True)
    st.markdown("선택된 연도 및 자치구의 미세먼지 농도 변화를 시간과 지역별로 시각화합니다.")
    st.markdown("<br>", unsafe_allow_html=True)

    if pol_filt.empty:
        st.warning("선택된 연도 및 자치구에 해당하는 미세먼지 데이터가 없습니다.")
    else:
        st.subheader("일별 미세먼지 농도 추이 (선택 자치구)")
        daily_pm10_trend = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
        st.line_chart(daily_pm10_trend, use_container_width=True)
        st.caption("선택된 자치구별 일평균 PM10 농도 변화 추이")
        st.markdown("<br>", unsafe_allow_html=True)

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
        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("지역별 PM10 농도 시각화 (지도)")
        map_df = avg_pm10.reset_index().rename(columns={'미세먼지(PM10)': 'Avg_PM10'})
        map_df['lat'] = map_df['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[0])
        map_df['lon'] = map_df['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[1])
        map_df['pm_color'] = map_df['Avg_PM10'].apply(lambda v: get_pm10_status(v)[1])

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position='[lon, lat]',
            get_radius=2500,
            get_fill_color='pm_color',
            pickable=True,
            opacity=0.8
        )
        initial_view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10, pitch=45)
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=initial_view_state,
            tooltip={"text": "{자치구}\n평균 PM10: {Avg_PM10:.1f} µg/m³"}
        ))
        st.markdown("<br>", unsafe_allow_html=True)

with tab2:
    st.markdown("<h2 style='margin-bottom:10px;'>2. 미세먼지 농도와 이동 패턴의 관계 분석 (PR 전략)</h2>", unsafe_allow_html=True)
    st.markdown("미세먼지 농도 변화에 따른 시민의 대중교통 이용 건수를 비교하여, **고농도 시기 리스크 알림 및 홍보 전략 최적화** 방안을 모색합니다.")
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    if mobility_filt.empty:
        st.warning("선택된 조건에 해당하는 미세먼지-교통 통합 데이터가 부족하거나, trans.csv 파일 로드에 문제가 있었습니다.")
    else:
        with col1:
            st.subheader("PM10과 대중교통 이용량 시계열 비교")
            daily_comp_mobility = mobility_filt.groupby('Date').agg({
                '미세먼지(PM10)': 'mean',
                '승객_수': 'sum'
            }).reset_index()
            if not daily_comp_mobility.empty:
                fig, ax1 = plt.subplots(figsize=(10, 5))
                ax2 = ax1.twinx()
                ax1.plot(daily_comp_mobility['Date'], daily_comp_mobility['미세먼지(PM10)'], color='blue', label='PM10 농도')
                ax1.set_xlabel("날짜")
                ax1.set_ylabel("PM10 (μg/m³)", color='blue')
                ax1.tick_params(axis='y', labelcolor='blue')
                ax2.plot(daily_comp_mobility['Date'], daily_comp_mobility['승객_수'], color='green', label='총 승객 수')
                ax2.set_ylabel("총 승객 수", color='green')
                ax2.tick_params(axis='y', labelcolor='green')
                ax1.set_title("PM10 농도와 대중교통 이용량 일별 변화 추이")
                fig.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("선택된 조건에 해당하는 데이터가 부족합니다.")

        with col2:
            st.subheader("PM10 상태별 평균 대중교통 이용량")
            avg_transit_by_pm10 = mobility_filt.groupby('Status')['승객_수'].mean().reset_index()
            status_order = ['좋음(0~30)', '보통(31~80)', '나쁨(81~150)', '매우 나쁨(151+)']
            if not avg_transit_by_pm10.empty:
                avg_transit_by_pm10['Status'] = pd.Categorical(avg_transit_by_pm10['Status'], categories=status_order, ordered=True)
                avg_transit_by_pm10 = avg_transit_by_pm10.sort_values('Status').dropna(subset=['Status'])
                fig, ax = plt.subplots(figsize=(10, 5))
                bar_colors = []
                for status in avg_transit_by_pm10['Status']:
                    simple_status = status.split('(')[0]
                    color = pm_colors.get(simple_status, [128, 128, 128])
                    bar_colors.append((color[0]/255, color[1]/255, color[2]/255))
                ax.bar(avg_transit_by_pm10['Status'], avg_transit_by_pm10['승객_수'], color=bar_colors)
                ax.set_xlabel("PM10 농도 상태", fontsize=12)
                ax.set_ylabel("평균 승객 수", fontsize=12)
                ax.set_title("PM10 상태별 대중교통 일평균 이용 건수")
                plt.xticks(rotation=0)
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("PM10 상태별 평균 대중교통 이용량 데이터를 생성할 수 없습니다.")

        st.markdown("---")
        st.subheader("PR 관점의 인사이트 (이동 패턴 활용)")
        st.markdown("""
            - **핵심 관계:** 시각화 결과, **미세먼지 농도가 '나쁨' 이상으로 높아질수록 대중교통 이용 건수가 감소하거나 증가율이 둔화되는 패턴**이 보일 수 있습니다 (시민들이 외출을 자제하고 실내 활동을 선호).
            - **PR 전략 최적화:** - **고농도 예상 시기 (PM10 '나쁨' 이상):** 시민들이 외출을 가장 주저하는 시점입니다. 이 시기에 맞춰 **지하철역과 버스 정거장** 등 대중교통 시설 내부에 **'실내 마스크 착용', '공기청정 대피소 안내'** 등 건강/안전 리스크 관련 포스터를 집중 홍보해야 합니다. 외출 자제를 유도하는 것이 아닌, **'필수 이동 시 안전 수칙'**을 타겟팅하여 홍보 효과를 극대화할 수 있습니다.
              - **회복기 (PM10 '보통' 이하로 전환):** 외출 수요가 회복되는 시기를 예측하여, **'맑은 공기와 함께하는 야외 활동'**을 주제로 한 캠페인 포스터를 대중교통 외부에 게재하여 심리적 회복을 유도하는 PR 전략을 수립할 수 있습니다.
            """)
        st.markdown("<br>", unsafe_allow_html=True)

with tab3:
    st.markdown("<h2 style='margin-bottom:10px;'>3. 미세먼지 농도와 소비 패턴의 관계 분석 (마케팅 전략)</h2>", unsafe_allow_html=True)
    st.markdown("미세먼지 농도 변화에 따른 배달 건수 및 지출액 변화를 분석하여, **식재료 공급망 및 기업 세일 전략 수립**에 필요한 정보를 도출합니다.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    year_select_tab3 = st.selectbox("분석할 연도를 선택하세요.", selected_years, key="tab3_year_select")
    st.subheader(f"연도별 PM10 농도와 배달 건수 지수 변화 ({year_select_tab3}년)")
    delivery_comp_filt = combined_delivery[combined_delivery['Year'] == year_select_tab3].set_index('Date')

    if not delivery_comp_filt.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()
        ax1.plot(delivery_comp_filt.index, delivery_comp_filt['미세먼지(PM10)'], color='orange', label='PM10 농도')
        ax1.set_ylabel("PM10 (μg/m³)", color='orange')
        ax1.tick_params(axis='y', labelcolor='orange')
        ax2.plot(delivery_comp_filt.index, delivery_comp_filt['배달_건수_지수'], color='red', label='배달 건수 지수')
        ax2.set_ylabel("배달 건수 지수", color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        ax1.set_title(f"{year_select_tab3}년 PM10 농도와 배달 건수 지수 변화 추이")
        fig.tight_layout()
        st.pyplot(fig)
        st.caption("PM10 농도가 높을수록(혹은 높았던 이후) 배달 건수 지수가 증가하는 경향성이 나타날 수 있습니다.")
    else:
        st.warning(f"선택된 연도({year_select_tab3}년)에 해당하는 PM10-배달 통합 데이터가 부족하거나, delivery.csv 로드에 문제가 있었습니다.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("지역별 배달 지표와 PM10 농도 시각화")

    if not spent_filt.empty:
        spent_avg_tab3 = spent_filt[spent_filt['Year'] == year_select_tab3].groupby('자치구')['지출_총금액'].mean()
    else:
        spent_avg_tab3 = pd.Series()
    pm10_avg_tab3 = pol_filt[pol_filt['Year'] == year_select_tab3].groupby('자치구')['미세먼지(PM10)'].mean()

    map_data_tab3 = pd.merge(spent_avg_tab3.reset_index(), pm10_avg_tab3.reset_index(), on='자치구', how='inner', suffixes=('_spending', '_pm10'))
    map_data_tab3 = map_data_tab3.rename(columns={'지출_총금액': 'Avg_Spending', '미세먼지(PM10)': 'PM10'})
    map_data_tab3['lat'] = map_data_tab3['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[0])
    map_data_tab3['lon'] = map_data_tab3['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[1])

    if not map_data_tab3.empty and map_data_tab3['Avg_Spending'].max() > 0:
        map_data_tab3['Radius'] = map_data_tab3['Avg_Spending'] / map_data_tab3['Avg_Spending'].max() * 5000 + 1000
        map_data_tab3["pm_color"] = map_data_tab3["PM10"].apply(lambda v: get_pm10_status(v)[1])

        layer3 = pdk.Layer(
            "ScatterplotLayer",
            data=map_data_tab3,
            get_position='[lon, lat]',
            get_radius='Radius',
            get_fill_color='pm_color',
            pickable=True,
            opacity=0.7
        )
        initial_view_state = pdk.ViewState(latitude=37.5665, longitude=126.9780, zoom=10, pitch=45)
        st.pydeck_chart(pdk.Deck(
            layers=[layer3], 
            initial_view_state=initial_view_state,
            tooltip={"text": "{자치구}\nPM10: {PM10:.1f}\n평균 지출액: {Avg_Spending:.0f}₩"}
        ))
        st.caption("원의 크기는 평균 지출액(배달 수요 대리 지표), 색상은 PM10 농도 상태를 나타냅니다.")
    else:
        st.warning(f"선택된 연도({year_select_tab3}년)에 해당하는 지역별 지출/PM10 데이터가 부족합니다.")
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("마케팅 관점의 인사이트 (소비 패턴 활용)")
    st.markdown("""
        - **핵심 관계:** PM10 농도가 높을 때 (실내 체류 증가) 배달 수요와 식료품/총 지출액이 증가하는 패턴을 확인했습니다.
        - **기업 운영 및 세일 전략:**
            - **식재료 및 공급망 준비:** 미래 예측된 미세먼지 고농도 시기(예: 봄철 황사, 겨울철 고농도)에 맞춰 **식자재 재고 및 공급망**을 미리 확보하고, 배달 수요에 대응할 수 있도록 **조리 인력 배치**를 최적화해야 합니다.
            - **세일 및 프로모션 시기:** PM10 농도가 '나쁨' 이상으로 예측되는 시기에 맞춰 **'실내 안심 배달'** 프로모션이나 **'집콕 세일'** 기간을 설정함으로써, 일반적인 계절적 세일 기간과 관계없이 수요가 폭발하는 시점을 공략할 수 있습니다.
            - **타겟 마케팅:** 지도에서 확인된 **지출액(잠재 배달 수요)이 높으면서 PM10 농도가 높은 지역**을 중심으로 마케팅 예산을 집중 투입하여 효율을 높일 수 있습니다.
        """)
    st.markdown("<br>", unsafe_allow_html=True)

with tab4:
    st.markdown("<h2 style='margin-bottom:10px;'>4. PM10, 교통, 배달/소비 간의 상관관계 및 미래 입지 전략</h2>", unsafe_allow_html=True)
    st.markdown("주요 지표 간의 상관관계를 분석하고, 먼 미래의 환경 변화를 고려한 기업의 입지 및 인프라 투자 전략에 대한 인사이트를 도출합니다.")
    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("주요 지표 간의 상관관계 (자치구별 평균 기준)")
    if not pol_filt.empty:
        pm10_avg_gu = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean()
    else:
        pm10_avg_gu = pd.Series()
    if not trans_filt.empty:
        transit_avg_gu = trans_filt.groupby('자치구')['승객_수'].sum()
    else:
        transit_avg_gu = pd.Series()
    if not spent_filt.empty:
        spending_avg_gu = spent_filt.groupby('자치구')['지출_총금액'].mean()
    else:
        spending_avg_gu = pd.Series()
    corr_df_gu = pd.DataFrame({
        "PM10": pm10_avg_gu,
        "대중교통 이용량": transit_avg_gu,
        "평균 지출액": spending_avg_gu
    }).dropna()

    if not corr_df_gu.empty and len(corr_df_gu) >= 2:
        corr_mat = corr_df_gu.corr(method='pearson')
        fig, ax = plt.subplots(figsize=(7,7))
        sns.heatmap(corr_mat, annot=True, cmap='vlag', ax=ax, center=0, 
                    fmt=".2f", linewidths=.5, cbar_kws={'label': 'Pearson Correlation Coefficient'})
        ax.set_title("주요 지표 간 상관관계 분석 (자치구별 평균 기준)", fontsize=14)
        ax.set_xticklabels(corr_mat.columns, rotation=45, ha='right')
        ax.set_yticklabels(corr_mat.columns, rotation=0)
        plt.tight_layout()
        st.pyplot(fig)
    elif not corr_df_gu.empty and len(corr_df_gu) < 2:
        st.warning("상관관계를 분석하기에 선택된 자치구 수가 충분하지 않습니다 (최소 2개 이상 필요).")
    else:
        st.warning("선택된 조건에 해당하는 상관관계 데이터가 부족합니다.")
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("인구 이동 변화와 PM10 농도 연계 분석 (장기 입지 전략)")
    if not combined_ppl.empty and not pol_filt.empty:
        ppl_2012_pivot = combined_ppl[combined_ppl['Year'] == '2012'].set_index('자치구')['인구_이동_건수']
        ppl_2014_pivot = combined_ppl[combined_ppl['Year'] == '2014'].set_index('자치구')['인구_이동_건수']
        ppl_change = (ppl_2014_pivot - ppl_2012_pivot).rename("인구_이동_변화량")
        pm10_long_term_avg = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().rename("평균_PM10")
        ppl_pm10_comp = pd.concat([ppl_change, pm10_long_term_avg], axis=1).dropna()
        if not ppl_pm10_comp.empty and len(ppl_pm10_comp) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=ppl_pm10_comp, 
                x='평균_PM10', 
                y='인구_이동_변화량', 
                ax=ax, 
                s=100,
                color='purple'
            )
            for gu, row in ppl_pm10_comp.iterrows():
                ax.text(row['평균_PM10'] * 1.01, row['인구_이동_변화량'], gu, fontsize=9)
            ax.axvline(ppl_pm10_comp['평균_PM10'].mean(), color='r', linestyle='--', linewidth=1, label='평균 PM10')
            ax.axhline(0, color='k', linestyle='-', linewidth=1, label='인구 변화량 0')
            ax.set_title("PM10 농도와 인구 이동 건수 변화량 관계 (2014년 - 2012년 기준)", fontsize=14)
            ax.set_xlabel(f"평균 PM10 농도 (선택 연도 기준)", fontsize=12)
            ax.set_ylabel("인구 이동 건수 변화량 (2014 - 2012)", fontsize=12)
            ax.legend(loc='lower left')
            plt.tight_layout()
            st.pyplot(fig)
            st.markdown("""
                - **핵심 관계:** 이 산점도를 통해 **평균 PM10 농도가 높은 지역일수록 인구 이동 건수 변화량(감소 또는 증가 둔화)이 음의 값(인구 유출 경향)을 보이는지** 장기적인 관점에서 분석할 수 있습니다.
                - **입지 전략 재검토:** 만약 PM10이 높고 인구 변화량이 낮은(음수인) 사분면에 위치한 자치구가 있다면, 해당 지역은 장기적으로 거주 매력이 감소하고 있음을 시사합니다. 기업은 이 지역에 **새로운 인프라 투자를 신중하게 고려**하거나, 혹은 **공기질 개선 등 환경 요소를 고려한 차별화된 투자**를 진행해야 합니다.
            """)
        else:
            st.warning("인구 이동 변화 분석을 위한 데이터가 부족합니다 (자치구별 2012년/2014년 데이터 모두 필요).")
    else:
        st.warning("인구 이동 데이터(ppl_2012.csv, ppl_2014.csv) 로드에 문제가 있어 인구 분석을 수행할 수 없습니다.")
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("미래 예측 기반 입지 및 인프라 전략 (종합 인사이트)")
    st.markdown("""
        - **장기 입지 전략 (미세먼지 vs. 인구):** 인구 이동 변화와 미세먼지 농도의 상관관계를 확인하여, 장기적으로 인구 유입이 예상되는 '청정 + 인구 유입' 지역에 H&B(Health & Beauty), 헬스케어, 에코투어리즘 시설 등에 집중 투자하는 전략이 유효합니다.
        - **인프라 투자:**
            - **고농도 지역:** 실내 공기질 개선 및 환기 시스템을 갖춘 '미세먼지 대피형' 복합 상업 시설 투자 및 실내 활동 관련 인프라(배달 거점 등) 확충.
            - **청정 지역:** 환경과 연계된 헬스케어, 에코투어리즘, 야외 스포츠 시설에 대한 인프라 투자.
        """)

