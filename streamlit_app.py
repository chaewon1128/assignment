import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk
import os
import itertools

# 앱 전체 큰 제목 표시 추가
st.title("[translate:서울 대기질 & 라이프스타일 분석 대시보드]")  

st.set_page_config(page_title="서울 대기질 & 라이프스타일 분석 대시보드", layout="wide")

def set_matplotlib_korean_font():
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    try:
        plt.rc('font', family='NanumGothic')
    except:
        pass

set_matplotlib_korean_font()

def get_pm10_status(pm10):
    if pd.isna(pm10):
        return 'Unknown', [128, 128, 128]
    elif pm10 <= 30:
        return 'Good (0~30)', [170, 204, 247]
    elif pm10 <= 80:
        return 'Moderate (31~80)', [133, 224, 133]
    elif pm10 <= 150:
        return 'Bad (81~150)', [255, 179, 71]
    else:
        return 'Very Bad (151+)', [255, 118, 117]

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
            st.error(f"❌ [translate:'{file_name}' 데이터 파일 로드 실패: 경로를 확인해주세요.]")
            data_map[var_name] = pd.DataFrame()
        except Exception as e:
            st.error(f"❌ [translate:'{file_name}' 파일 로드 중 오류 발생: {e}]")
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
    st.error(f"[translate:데이터 로드 중 예기치 못한 오류 발생:] {e}")
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
    st.error("[translate:미세먼지 데이터(combined_pol.csv) 로드 실패. 대시보드 기능 사용 불가. 파일을 확인하세요.]")
    st.stop()
elif trans.empty:
    st.warning("[translate:대중교통 데이터(trans.csv) 로드 실패. 일부 기능 제한.]")
elif spent.empty:
    st.warning("[translate:지출 데이터(spent.csv) 로드 실패. 일부 기능 제한.]")
elif delivery.empty:
    st.warning("[translate:배달 데이터(delivery.csv) 로드 실패. 일부 기능 제한.]")
elif combined_ppl.empty:
    st.warning("[translate:인구 이동 데이터(ppl_2012.csv, ppl_2014.csv) 로드 실패. 일부 기능 제한.]")

st.sidebar.header("[translate:필터 설정]")

all_years = sorted(pol['Year'].unique())
default_years = all_years[-2:] if len(all_years) >= 2 else all_years

selected_years = st.sidebar.multiselect(
    "[translate:1. 분석 연도 선택]", 
    all_years, 
    default=default_years
)

opts = ["[translate:전체 자치구]"] + GUS
default_gus = opts[1:6] if len(opts) >= 6 else opts[1:]
selected_gus_options = st.sidebar.multiselect(
    "[translate:2. 분석 자치구 선택]", 
    opts, 
    default=default_gus
)
if "[translate:전체 자치구]" in selected_gus_options:
    selected_gus = GUS
else:
    selected_gus = selected_gus_options

st.sidebar.subheader("[translate:PM10 농도 기준 (μg/m³)]")
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
    "[translate:대기질 변화 추이]",
    "[translate:이동 및 PR 전략]",
    "[translate:소비 및 마케팅 전략]",
    "[translate:상관관계 및 입지 전략]"
])

with tab1:
    st.header("[translate:1. 미세먼지(PM10) 농도 변화 추이 분석]")
    st.markdown("[translate:선택된 연도 및 자치구의 미세먼지 농도 변화를 시간과 지역별로 시각화합니다.]")

    if pol_filt.empty:
        st.warning("[translate:선택된 연도 및 자치구에 해당하는 미세먼지 데이터가 없습니다.]")
    else:
        st.subheader("Daily PM10 Concentration Trend (Selected Districts)")
        daily_pm10_trend = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
        st.line_chart(daily_pm10_trend, use_container_width=True)
        st.caption("Daily average PM10 concentration trend by district")

        st.subheader("Average PM10 by District")
        avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = [get_pm10_status(v)[1] for v in avg_pm10.values]
        ax.bar(avg_pm10.index, avg_pm10.values, color=[(c[0]/255, c[1]/255, c[2]/255) for c in colors])
        ax.set_xlabel("[translate:자치구]", fontsize=12)
        ax.set_ylabel("Average PM10 (μg/m³)", fontsize=12)
        ax.set_title(f"Average PM10 by District ({', '.join(selected_years)})", fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        st.pyplot(fig)

        st.subheader("[translate:지역별 PM10 농도 시각화 (지도)]")
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
            tooltip={"text": "{자치구}\nAverage PM10: {Avg_PM10:.1f} µg/m³"}
        ))

with tab2:
    st.header("[translate:2. 미세먼지 농도와 이동 패턴의 관계 분석 (PR 전략)]")
    st.markdown("[translate:미세먼지 농도 변화에 따른 시민의 대중교통 이용 건수를 비교하여, 고농도 시기 리스크 알림 및 홍보 전략 최적화 방안을 모색합니다.]")

    col1, col2 = st.columns(2)
    if mobility_filt.empty:
        st.warning("[translate:선택된 조건에 해당하는 미세먼지-교통 통합 데이터가 부족하거나, trans.csv 파일 로드에 문제가 있었습니다.]")
    else:
        with col1:
            st.subheader("PM10 vs Transit Time Series")
            daily_comp_mobility = mobility_filt.groupby('Date').agg({
                '미세먼지(PM10)': 'mean',
                '승객_수': 'sum'
            }).reset_index()
            if not daily_comp_mobility.empty:
                fig, ax1 = plt.subplots(figsize=(10, 5))
                ax2 = ax1.twinx()
                ax1.plot(daily_comp_mobility['Date'], daily_comp_mobility['미세먼지(PM10)'], color='blue', label='PM10')
                ax1.set_xlabel("[translate:날짜]")
                ax1.set_ylabel("PM10 (μg/m³)", color='blue')
                ax1.tick_params(axis='y', labelcolor='blue')
                ax2.plot(daily_comp_mobility['Date'], daily_comp_mobility['승객_수'], color='green', label='Transit Total')
                ax2.set_ylabel("[translate:총 승객 수]", color='green')
                ax2.tick_params(axis='y', labelcolor='green')
                ax1.set_title("PM10 & Public Transit Daily Trend")
                fig.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("[translate:선택된 조건에 해당하는 데이터가 부족합니다.]")

        with col2:
            st.subheader("[translate:PM10 상태별 평균 대중교통 이용량]")
            avg_transit_by_pm10 = mobility_filt.groupby('Status')['승객_수'].mean().reset_index()
            status_order = ['Good (0~30)', 'Moderate (31~80)', 'Bad (81~150)', 'Very Bad (151+)']
            if not avg_transit_by_pm10.empty:
                avg_transit_by_pm10['Status'] = pd.Categorical(avg_transit_by_pm10['Status'], categories=status_order, ordered=True)
                avg_transit_by_pm10 = avg_transit_by_pm10.sort_values('Status').dropna(subset=['Status'])
                fig, ax = plt.subplots(figsize=(10, 5))
                bar_colors = []
                for status in avg_transit_by_pm10['Status']:
                    simple_status = status.split('(')[0].split()[0]
                    color = pm_colors.get(simple_status, [128, 128, 128])
                    bar_colors.append((color[0]/255, color[1]/255, color[2]/255))
                ax.bar(avg_transit_by_pm10['Status'], avg_transit_by_pm10['승객_수'], color=bar_colors)
                ax.set_xlabel("PM10 Status", fontsize=12)
                ax.set_ylabel("[translate:평균 승객 수]", fontsize=12)
                ax.set_title("Average Daily Transit Use by PM10 Status")
                plt.xticks(rotation=0)
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("[translate:PM10 상태별 평균 대중교통 이용량 데이터를 생성할 수 없습니다.]")

        st.markdown("---")
        st.subheader("[translate:PR 관점의 인사이트 (이동 패턴 활용)]")
        st.markdown(
            """
            - [translate:핵심 관계:] 미세먼지 농도가 '나쁨' 이상으로 높아질수록 대중교통 이용 건수가 감소하거나 증가율이 둔화되는 패턴이 보일 수 있습니다 (시민들이 외출을 자제하고 실내 활동을 선호).
            - [translate:PR 전략 최적화:] 고농도 예상 시기 (PM10 '나쁨' 이상)에는 지하철역과 버스 정거장 등 대중교통 시설 내부에 '실내 마스크 착용', '공기청정 대피소 안내' 포스터 집중 홍보 필요.
            """
        )

with tab3:
    st.header("[translate:3. 미세먼지 농도와 소비 패턴의 관계 분석 (마케팅 전략)]")
    st.markdown("[translate:미세먼지 농도 변화에 따른 배달 건수 및 지출액 변화를 분석하여, 식재료 공급망 및 기업 세일 전략 수립에 필요한 정보를 도출합니다.]")

    year_select_tab3 = st.selectbox("[translate:분석할 연도를 선택하세요.]", selected_years, key="tab3_year_select")
    st.subheader(f"Annual PM10 & Delivery Index Trend ({year_select_tab3})")
    delivery_comp_filt = combined_delivery[combined_delivery['Year'] == year_select_tab3].set_index('Date')

    if not delivery_comp_filt.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()
        ax1.plot(delivery_comp_filt.index, delivery_comp_filt['미세먼지(PM10)'], color='orange', label='PM10')
        ax1.set_ylabel("PM10 (μg/m³)", color='orange')
        ax1.tick_params(axis='y', labelcolor='orange')
        ax2.plot(delivery_comp_filt.index, delivery_comp_filt['배달_건수_지수'], color='red', label='Delivery Index')
        ax2.set_ylabel("[translate:배달 건수 지수]", color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        ax1.set_title(f"{year_select_tab3} PM10 & Delivery Index Trend")
        fig.tight_layout()
        st.pyplot(fig)
        st.caption("[translate:PM10 농도가 높을수록 배달 건수 지수가 증가하는 경향이 있습니다.]")
    else:
        st.warning(f"[translate:선택된 연도({year_select_tab3}년)에 해당하는 PM10-배달 통합 데이터가 부족하거나, delivery.csv 로드에 문제가 있었습니다.]")

    st.subheader("[translate:지역별 배달 지표와 PM10 농도 시각화]")

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
        st.pydeck_chart(pdk.Deck(
            layers=[layer3], 
            initial_view_state=initial_view_state,
            tooltip={"text": "{자치구}\nPM10: {PM10:.1f}\n[translate:평균 지출액]: {Avg_Spending:.0f}₩"}
        ))
        st.caption("[translate:원의 크기는 평균 지출액(배달 수요 대리 지표), 색상은 PM10 농도 상태를 나타냅니다.]")
    else:
        st.warning(f"[translate:선택된 연도({year_select_tab3}년)에 해당하는 지역별 지출/PM10 데이터가 부족합니다.]")

    st.markdown("---")
    st.subheader("[translate:마케팅 관점의 인사이트 (소비 패턴 활용)]")
    st.markdown(
        """
        - [translate:핵심 관계:] PM10 농도가 높을 때 배달 수요와 지출액이 증가하는 패턴을 확인했습니다.
        - [translate:기업 운영 및 세일 전략:]
            - [translate:식재료 및 공급망 준비:] 고농도 시기 전에 재고 및 인력 최적화 필요.
            - [translate:세일 및 프로모션:] 고농도 시기 맞춤 프로모션 및 타겟 마케팅 권장.
        """
    )

with tab4:
    st.header("[translate:4. PM10, 교통, 배달/소비 간의 상관관계 및 미래 입지 전략]")
    st.markdown("[translate:주요 지표 간의 상관관계를 분석하고, 먼 미래의 환경 변화를 고려한 기업의 입지 및 인프라 투자 전략에 대한 인사이트를 도출합니다.]")

    st.subheader("[translate:주요 지표 간의 상관관계 (자치구별 평균 기준)]")
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
        "[translate:PM10]": pm10_avg_gu,
        "[translate:대중교통 이용량]": transit_avg_gu,
        "[translate:평균 지출액]": spending_avg_gu
    }).dropna()

    if not corr_df_gu.empty and len(corr_df_gu) >= 2:
        corr_mat = corr_df_gu.corr(method='pearson')
        fig, ax = plt.subplots(figsize=(7,7))
        sns.heatmap(corr_mat, annot=True, cmap='vlag', ax=ax, center=0, 
                    fmt=".2f", linewidths=.5, cbar_kws={'label': '[translate:피어슨 상관계수]'})
        ax.set_title("[translate:주요 지표 간 상관관계 분석 (자치구별 평균 기준)]", fontsize=14)
        ax.set_xticklabels(corr_mat.columns, rotation=45, ha='right')
        ax.set_yticklabels(corr_mat.columns, rotation=0)
        plt.tight_layout()
        st.pyplot(fig)
    elif not corr_df_gu.empty and len(corr_df_gu) < 2:
           st.warning("[translate:상관관계를 분석하기에 선택된 자치구 수가 충분하지 않습니다 (최소 2개 이상 필요).]")
    else:
        st.warning("[translate:선택된 조건에 해당하는 상관관계 데이터가 부족합니다.]")

    st.markdown("---")
    st.subheader("[translate:인구 이동 변화와 PM10 연계 분석 (장기 입지 전략)]")

    if not combined_ppl.empty and not pol_filt.empty:
        ppl_2012_pivot = combined_ppl[combined_ppl['Year'] == '2012'].set_index('자치구')['인구_이동_건수']
        ppl_2014_pivot = combined_ppl[combined_ppl['Year'] == '2014'].set_index('자치구')['인구_이동_건수']
        ppl_change = (ppl_2014_pivot - ppl_2012_pivot).rename("[translate:인구 이동 변화량]")
        pm10_long_term_avg = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().rename("[translate:평균 PM10]")
        ppl_pm10_comp = pd.concat([ppl_change, pm10_long_term_avg], axis=1).dropna()

        if not ppl_pm10_comp.empty and len(ppl_pm10_comp) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=ppl_pm10_comp, 
                x='[translate:평균 PM10]', 
                y='[translate:인구 이동 변화량]', 
                ax=ax, 
                s=100, 
                color='purple'
            )
            for gu, row in ppl_pm10_comp.iterrows():
                ax.text(row['[translate:평균 PM10]'] * 1.01, row['[translate:인구 이동 변화량]'], gu, fontsize=9)
            ax.axvline(ppl_pm10_comp['[translate:평균 PM10]'].mean(), color='r', linestyle='--', linewidth=1, label='Mean PM10')
            ax.axhline(0, color='k', linestyle='-', linewidth=1, label='Population Change 0')
            ax.set_title("[translate:PM10 농도와 인구 이동 건수 변화량 관계 (2014년 - 2012년 기준)]", fontsize=14)
            ax.set_xlabel(f"[translate:평균 PM10 농도 (선택 연도 기준)]", fontsize=12)
            ax.set_ylabel("[translate:인구 이동 건수 변화량 (2014 - 2012)]", fontsize=12)
            ax.legend(loc='lower left')
            plt.tight_layout()
            st.pyplot(fig)
            st.markdown(
                """
                - [translate:핵심 관계:] 평균 PM10 농도가 높은 지역일수록 인구 이동 변화량(감소 또는 증가 둔화)이 음의 값을 보이는지 장기적으로 파악.
                """
            )
        else:
            st.warning("[translate:인구 이동 변화 분석을 위한 데이터가 부족합니다 (2012, 2014년 자치구별 데이터 필요).]")
    else:
        st.warning("[translate:인구 이동 데이터 로드 문제로 인구 분석 수행 불가.]")

    st.markdown("---")
    st.subheader("[translate:미래 예측 기반 입지 및 인프라 전략 (종합 인사이트)]")
    st.markdown(
        """
        - [translate:장기 입지 전략:] 청정 지역 + 인구 유입 지역에 헬스케어, 에코투어리즘 등 집중 투자 권장.
        - [translate:인프라 투자:]
            - [translate:고농도 지역:] 미세먼지 대피형 복합 시설 및 실내 공기질 개선 인프라 투자.
            - [translate:청정 지역:] 환경 연계형 야외 스포츠 및 헬스케어 시설 투자.
        """
    )
