import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk
import os
import itertools # for combining population data

st.title("[PR 관점에서 본 서울 미세먼지 농도의 영향 분석 대시보드]")
# Streamlit 페이지 설정: 전체 레이아웃을 넓게 사용하도록 설정합니다.
st.set_page_config(page_title="서울 대기질 & 라이프스타일 분석 대시보드", layout="wide")

# matplotlib에서 한글 폰트 설정을 위한 함수
def set_matplotlib_korean_font():
    """Matplotlib에서 한글이 깨지지 않도록 폰트를 설정합니다."""
    # 폰트 경로를 직접 지정하거나, 시스템에 존재하는 폰트를 사용합니다.
    # Colab/Streamlit 환경을 고려하여 기본 폰트 설정으로만 시도
    plt.rcParams['font.family'] = 'Malgun Gothic' # Windows 기준
    plt.rcParams['axes.unicode_minus'] = False # 마이너스 폰트 깨짐 방지
    try:
        plt.rc('font', family='NanumGothic') # 시스템에 나눔고딕이 있을 경우 사용
    except:
        # 폰트가 없는 경우 기본 설정으로 진행 (경고 메시지 출력)
        pass

# 한글 폰트 설정 적용
set_matplotlib_korean_font()

# --- PM10 농도 기준 색상 및 레이블 정의 ---
def get_pm10_status(pm10):
    """PM10 농도에 따른 상태 및 색상(RGB) 반환"""
    if pd.isna(pm10): # 결측값 처리
        return '미정', [128, 128, 128] # Gray
    elif pm10 <= 30:
        return '좋음(0~30)', [170, 204, 247]  # Light Blue
    elif pm10 <= 80:
        return '보통(31~80)', [133, 224, 133]  # Light Green
    elif pm10 <= 150:
        return '나쁨(81~150)', [255, 179, 71]  # Orange
    else:
        return '매우 나쁨(151+)', [255, 118, 117]  # Red

# --- 데이터 로드 및 전처리 함수 (파일 로드 실패 시 예외 처리 강화) ---
@st.cache_data
def load_data():
    """
    필요한 모든 데이터를 로드하고 전처리합니다.
    파일 로드 실패 시에도 앱이 중단되지 않고 빈 데이터프레임을 반환합니다.
    """
    files_needed = ["spent.csv", "ppl_2012.csv", "ppl_2014.csv",
                    "delivery.csv", "combined_pol.csv", "trans.csv"]

    data_map = {}
    
    # 공통적인 파일 로드 로직
    for file_name in files_needed:
        var_name = file_name.replace('.csv', '').replace('combined_', '')
        df = pd.DataFrame()
        
        try:
            # 인코딩 순서: euc-kr -> cp949 -> utf-8
            try:
                df = pd.read_csv(file_name, encoding='euc-kr')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_name, encoding='cp949')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_name, encoding='utf-8')
            
            data_map[var_name] = df
            
        except FileNotFoundError:
            # 파일이 없는 경우, 에러 메시지를 기록하고 빈 DataFrame 반환
            st.error(f"❌ 데이터 파일 로드 실패: '{file_name}' 파일을 찾을 수 없습니다. 경로를 확인해 주세요.")
            data_map[var_name] = pd.DataFrame()
        except Exception as e:
            # 그 외 로드 오류 처리 (예: 데이터 손상)
            st.error(f"❌ '{file_name}' 파일 로드 중 심각한 오류 발생: {e}")
            data_map[var_name] = pd.DataFrame()


    # 데이터 전처리
    
    # 1. 미세먼지 데이터 (pol)
    pol = data_map.get('pol') # 'combined_pol.csv' -> 'pol'
    if pol is None or pol.empty:
        pol = pd.DataFrame()
        daily_pol = pd.DataFrame()
    else:
        # PM10 데이터 전처리
        pol['일시'] = pol['일시'].astype(str)
        pol['Year'] = pol['일시'].str[:4]
        # 날짜 포맷팅 에러가 나지 않도록 'errors='coerce' 옵션 사용
        pol['Date'] = pd.to_datetime(pol['일시'], errors='coerce') 
        pol.dropna(subset=['Date'], inplace=True) # 날짜 변환 실패한 행 제거
        # PM10 상태 및 색상 적용
        pol['Status'], pol['Color'] = zip(*pol['미세먼지(PM10)'].apply(get_pm10_status))
        
        # 일별/자치구별 평균 미세먼지 계산
        daily_pol = pol.groupby(['Date', '자치구'])['미세먼지(PM10)'].mean().reset_index()
        daily_pol['Status'], daily_pol['Color'] = zip(*daily_pol['미세먼지(PM10)'].apply(get_pm10_status))

    # 2. 지출 데이터 (spent)
    spent = data_map.get('spent')
    if spent is None or spent.empty:
        spent = pd.DataFrame()
    else:
        # '기준_년분기_코드'에서 연도 추출
        spent['Year'] = spent['기준_년분기_코드'].astype(str).str[:4]
        
    # 3. 교통 데이터 (trans)
    trans = data_map.get('trans')
    if trans is None or trans.empty:
        trans = pd.DataFrame()
        daily_trans = pd.DataFrame()
    else:
        trans['Date'] = pd.to_datetime(trans['기준_날짜'], errors='coerce')
        trans.dropna(subset=['Date'], inplace=True)
        trans['Year'] = trans['기준_날짜'].astype(str).str[:4]
        # 일별/자치구별 총 승객 수
        daily_trans = trans.groupby(['Date', '자치구'])['승객_수'].sum().reset_index()

    # 4. 배달 데이터 (delivery)
    delivery = data_map.get('delivery')
    if delivery is None or delivery.empty:
        delivery = pd.DataFrame()
    else:
        # 컬럼 이름 정리: 따옴표 제거 및 이름 변경
        delivery.columns = delivery.columns.str.strip().str.replace('"', '')
        delivery = delivery.rename(columns={'전체': '배달_건수_지수'})
        delivery['Date'] = pd.to_datetime(delivery['Date'], errors='coerce')
        delivery.dropna(subset=['Date'], inplace=True)
        delivery['Year'] = delivery['Date'].dt.year.astype(str)
        
    # 5. 인구 데이터 (ppl_2012, ppl_2014) - 전처리 로직 추가
    ppl_2012_df = data_map.get('ppl_2012', pd.DataFrame())
    ppl_2014_df = data_map.get('ppl_2014', pd.DataFrame())

    def preprocess_ppl_data(df, year):
        if df.empty:
            return df
        # 컬럼 이름 변경
        df = df.rename(columns={'거주지': '자치구', '개수': '인구_이동_건수'})
        # '인구_이동_건수' 컬럼을 숫자로 변환
        df['인구_이동_건수'] = pd.to_numeric(df['인구_이동_건수'], errors='coerce')
        df.dropna(subset=['인구_이동_건수'], inplace=True)
        df['Year'] = str(year)
        # 서울 자치구만 필터링 (기타지역, 경기, 인천 등 제외)
        seoul_gus_list = ['강남구', '강동구', '강북구', '강서구', '관악구', '광진구', '구로구', '금천구', '노원구', '도봉구', '동대문구', '동작구', '마포구', '서대문구', '서초구', '성동구', '성북구', '송파구', '양천구', '영등포구', '용산구', '은평구', '종로구', '중구', '중랑구']
        return df[df['자치구'].isin(seoul_gus_list)]

    ppl_2012 = preprocess_ppl_data(ppl_2012_df, 2012)
    ppl_2014 = preprocess_ppl_data(ppl_2014_df, 2014)

    # Combine population data for easier use in Tab 4
    if not ppl_2012.empty and not ppl_2014.empty:
        combined_ppl = pd.concat([ppl_2012, ppl_2014], ignore_index=True)
    else:
        combined_ppl = pd.DataFrame()

    # --- 6. 통합 데이터 생성 ---
    
    # PM10과 대중교통 통합 (일별/자치구별)
    if not daily_pol.empty and not daily_trans.empty:
        combined_mobility = pd.merge(
            daily_pol, daily_trans, 
            on=['Date', '자치구'], 
            how='inner'
        )
    else:
        combined_mobility = pd.DataFrame()
    
    # PM10과 배달 통합
    if not daily_pol.empty and not delivery.empty:
        # 서울 전체 일평균 PM10 계산 (자치구 '평균'을 사용할 경우 오류 발생 가능성으로 새로 계산)
        seoul_daily_pol = daily_pol.groupby('Date')['미세먼지(PM10)'].mean().reset_index()
        combined_delivery = pd.merge(
            seoul_daily_pol, delivery,
            on='Date',
            how='inner'
        )
    else:
        combined_delivery = pd.DataFrame()

    # GUS (자치구 목록)
    GUS_df = pd.DataFrame() # GUS_df는 실제로 사용되지 않으므로 빈 DF 유지
    
    # combined_ppl을 추가하여 반환합니다.
    return (spent, ppl_2012, ppl_2014, delivery, pol, trans, 
            GUS_df, combined_mobility, combined_delivery, combined_ppl)

# --- 데이터 로드 및 전역 변수 설정 ---
# 로드 함수 실행 (반환 값에 combined_ppl 추가)
try:
    (spent, ppl_2012, ppl_2014, delivery, pol, trans, GUS_df, combined_mobility, combined_delivery, combined_ppl) = load_data()
except Exception as e:
    # load_data 함수 자체에서 오류가 나는 경우 (매우 드물지만 대비)
    st.error(f"데이터 로드 과정 중 예측하지 못한 오류가 발생했습니다: {e}")
    st.stop()


# 데이터 로드 후 자치구 목록 정의
if not pol.empty:
    # '평균' 항목을 제외한 자치구 목록 추출 및 정렬
    GUS = sorted(list(set(pol[pol['자치구'] != '평균']['자치구'])))
else:
    GUS = []

# 서울 자치구 위경도 정보 (하드코딩)
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

# --- 데이터 유효성 검사 (핵심 데이터 누락 시 경고) ---
if pol.empty:
    st.error("🚨 미세먼지 데이터(combined_pol.csv) 로드에 실패하여 대시보드 기능을 사용할 수 없습니다. 파일을 확인해 주세요.")
    st.stop() # 핵심 데이터가 없으면 실행 중단
elif trans.empty:
    st.warning("⚠️ 대중교통 데이터(trans.csv) 로드에 실패했습니다. '이동 및 PR 전략' 탭의 일부 기능이 제한됩니다.")
elif spent.empty:
    st.warning("⚠️ 지출 데이터(spent.csv) 로드에 실패했습니다. '소비 및 마케팅 전략' 탭의 일부 기능이 제한됩니다.")
elif delivery.empty:
    st.warning("⚠️ 배달 데이터(delivery.csv) 로드에 실패했습니다. '소비 및 마케팅 전략' 탭의 일부 기능이 제한됩니다.")
elif combined_ppl.empty:
    st.warning("⚠️ 인구 이동 데이터(ppl_2012.csv, ppl_2014.csv) 로드에 실패했습니다. '상관관계 및 입지 전략' 탭의 인구 분석 기능이 제한됩니다.")


# --- 사이드바 필터 설정 ---
st.sidebar.header("필터 설정")

# pol 데이터가 비어있지 않은 경우에만 연도 정보 사용
all_years = sorted(pol['Year'].unique())
default_years = all_years[-2:] if len(all_years) >= 2 else all_years

selected_years = st.sidebar.multiselect(
    "1. 분석 연도 선택", 
    all_years, 
    default=default_years
)

opts = ["전체 자치구"] + GUS
default_gus = opts[1:6] if len(opts) >= 6 else opts[1:]

selected_gus_options = st.sidebar.multiselect(
    "2. 분석 자치구 선택", 
    opts, 
    default=default_gus
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

# combined_mobility 필터링
if not combined_mobility.empty:
    mobility_filt = combined_mobility[
        (combined_mobility['Date'].dt.year.astype(str).isin(selected_years)) & 
        (combined_mobility['자치구'].isin(selected_gus))
    ].copy()
else:
    mobility_filt = pd.DataFrame()

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

    if pol_filt.empty:
        st.warning("선택된 연도 및 자치구에 해당하는 미세먼지 데이터가 없습니다.")
    else:
        # 1. 시계열 변화 추이 (라인 그래프)
        st.subheader("일별 미세먼지 농도 추이 (선택 자치구)")
        daily_pm10_trend = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
        # 그래프 영역을 Streamlit 내장 차트 기능으로 표시
        st.line_chart(daily_pm10_trend, use_container_width=True)
        st.caption("선택된 자치구별 일평균 PM10 농도 변화 추이")

        # 2. 지역별 PM10 농도 비교 (막대 그래프)
        st.subheader("지역별 평균 PM10 농도 비교")
        avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().sort_values(ascending=False)
        
        # Matplotlib을 사용하여 막대 그래프 생성
        fig, ax = plt.subplots(figsize=(10, 5))
        # RGB 색상을 0~1로 정규화하여 Matplotlib에 적용
        colors = [get_pm10_status(v)[1] for v in avg_pm10.values]
        ax.bar(avg_pm10.index, avg_pm10.values, color=[(c[0]/255, c[1]/255, c[2]/255) for c in colors])
        ax.set_xlabel("자치구", fontsize=12)
        ax.set_ylabel("평균 PM10 (μg/m³)", fontsize=12)
        ax.set_title(f"선택 연도({', '.join(selected_years)}) 기준 자치구별 평균 PM10", fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        st.pyplot(fig) # 그래프를 Streamlit에 출력

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
    st.markdown("미세먼지 농도 변화에 따른 시민의 대중교통 이용 건수를 비교하여, **홍보 전략 최적화** 방안을 모색합니다.")

try:
    pol_df = pd.read_csv("combined_pol.csv")
    trans_df = pd.read_csv("trans.csv")
except FileNotFoundError:
    print("오류: 필요한 파일(combined_pol.csv 또는 trans.csv)을 찾을 수 없습니다.")
    exit()

# 2. 미세먼지 데이터 전처리 (일별 서울시 평균 PM10 농도 추출)
pol_df.rename(columns={'일시': '날짜', '미세먼지(PM10)': 'PM10_농도'}, inplace=True)
pol_df['날짜'] = pd.to_datetime(pol_df['날짜'])

# '자치구'가 '평균'인 값(서울시 일별 평균 PM10)을 대표값으로 사용
seoul_daily_pm10 = pol_df[pol_df['자치구'] == '평균'][['날짜', 'PM10_농도']].copy()

# 3. 대중교통 데이터 전처리 (일별 서울시 총 승객 수 합산)
trans_df.rename(columns={'기준_날짜': '날짜', '승객_수': '총_승객_수'}, inplace=True)
trans_df['날짜'] = pd.to_datetime(trans_df['날짜'])

# 날짜별로 모든 자치구의 승객 수를 합산하여 일별 총 승객 수 계산
daily_trans = trans_df.groupby('날짜')['총_승객_수'].sum().reset_index()

# 4. 데이터 병합 (날짜 기준)
# 공통된 날짜만을 기준으로 데이터를 병합합니다.
merged_df = pd.merge(daily_trans, seoul_daily_pm10, on='날짜', how='inner')

# NaN 값이 있는 행 제거
merged_df.dropna(inplace=True)

# 5. 상관관계 분석 (피어슨 상관계수)
# PM10 농도와 총 승객 수 간의 피어슨 상관계수를 계산합니다.
if not merged_df.empty:
    correlation = merged_df['PM10_농도'].corr(merged_df['총_승객_수'])
else:
    correlation = np.nan

# 6. 결과 출력 및 해석
print("\n--- 분석 결과 ---")

if not np.isnan(correlation):
    print(f"PM10 농도와 대중교통 이용 건수 간의 피어슨 상관계수: {correlation:.4f}")

    if correlation < -0.6:
        relationship = "강한 음의 상관관계"
        direction = "미세먼지 농도가 증가할수록 대중교통 이용 건수는 강하게 감소합니다."
    elif correlation < -0.2:
        relationship = "음의 상관관계"
        direction = "미세먼지 농도가 증가할수록 대중교통 이용 건수는 감소하는 경향이 있습니다."
    elif correlation > 0.6:
        relationship = "강한 양의 상관관계"
        direction = "미세먼지 농도가 증가할수록 대중교통 이용 건수도 강하게 증가합니다."
    elif correlation > 0.2:
        relationship = "양의 상관관계"
        direction = "미세먼지 농도가 증가할수록 대중교통 이용 건수도 증가하는 경향이 있습니다."
    else:
        relationship = "매우 약한 상관관계 또는 무상관"
        direction = "두 변수 간에 뚜렷한 선형 관계를 찾기 어렵습니다."

    print(f"해석: {relationship}가 나타났으며, 이는 '{direction}'는 경향을 보입니다.")
else:
    print("오류: 데이터 병합 후 유효한 데이터가 부족하여 상관관계를 계산할 수 없습니다.")

# 시각화를 위한 추가 데이터 준비 (상관계수 히트맵을 위한 2x2 행렬)
if not np.isnan(correlation):
    corr_matrix = pd.DataFrame({
        'PM10_농도': [1.0, correlation],
        '총_승객_수': [correlation, 1.0]
    }, index=['PM10_농도', '총_승객_수'])
    # print("\n상관계수 행렬:")
    # print(corr_matrix)
    # merged_df.to_csv("merged_data_for_correlation.csv", index=False)

    
    if mobility_filt.empty:
        st.warning("선택된 조건에 해당하는 미세먼지-교통 통합 데이터가 부족하거나, trans.csv 파일 로드에 문제가 있었습니다.")
    else:
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
                ax2.set_ylabel("총 승객 수", color='green')
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
            # 정렬 순서 정의
            status_order = ['좋음(0~30)', '보통(31~80)', '나쁨(81~150)', '매우 나쁨(151+)']
            
            # 카테고리 설정 및 정렬
            if not avg_transit_by_pm10.empty:
                avg_transit_by_pm10['Status'] = pd.Categorical(avg_transit_by_pm10['Status'], categories=status_order, ordered=True)
                avg_transit_by_pm10 = avg_transit_by_pm10.sort_values('Status').dropna(subset=['Status'])

                fig, ax = plt.subplots(figsize=(10, 5))
                # PM10 상태별 색상 매핑
                bar_colors = []
                for status in avg_transit_by_pm10['Status']:
                    # 상태명에서 괄호 앞 부분만 추출 ('좋음' 등)
                    simple_status = status.split('(')[0]
                    color = pm_colors.get(simple_status, [128, 128, 128]) # 기본 색상: 회색
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
        st.markdown(
            """
            - **핵심 관계:** 시각화 결과, **미세먼지 농도가 '나쁨' 이상으로 높아질수록 대중교통 이용 건수가 감소하거나 증가율이 둔화되는 패턴**이 보일 수 있습니다 (시민들이 외출을 자제하고 실내 활동을 선호).
            - **PR 전략 최적화:** - **고농도 예상 시기 (PM10 '나쁨' 이상): 이 시기에 맞춰 **지하철역과 버스 정거장** 등 대중교통 시설 내부에 포스터를 집중 홍보해야 합니다. **대중교통을 시민들이 더 많이 이용하며 대중교통 시설 내부에 포스터를 보는 시민들도 자연스럽게 증가할 것입니다.**
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
        st.warning(f"선택된 연도({year_select_tab3}년)에 해당하는 PM10-배달 통합 데이터가 부족하거나, delivery.csv 로드에 문제가 있었습니다.")

    # 2. 지역별 배달/지출 및 PM10 지도
    st.subheader("지역별 배달 지표와 PM10 농도 시각화")

    # Map Data Preparation (Using Avg Spending as proxy for Delivery volume)
    if not spent_filt.empty:
        spent_avg_tab3 = spent_filt[spent_filt['Year'] == year_select_tab3].groupby('자치구')['지출_총금액'].mean()
    else:
        spent_avg_tab3 = pd.Series()
        
    pm10_avg_tab3 = pol_filt[pol_filt['Year'] == year_select_tab3].groupby('자치구')['미세먼지(PM10)'].mean()

    # 데이터프레임 병합 및 지도 정보 추가
    map_data_tab3 = pd.merge(spent_avg_tab3.reset_index(), pm10_avg_tab3.reset_index(), on='자치구', how='inner', suffixes=('_spending', '_pm10'))
    map_data_tab3 = map_data_tab3.rename(columns={'지출_총금액': 'Avg_Spending', '미세먼지(PM10)': 'PM10'})
    map_data_tab3['lat'] = map_data_tab3['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[0])
    map_data_tab3['lon'] = map_data_tab3['자치구'].apply(lambda g: seoul_gu_latlon.get(g, (0,0))[1])
    
    if not map_data_tab3.empty and map_data_tab3['Avg_Spending'].max() > 0:
        # 지출 총금액을 지도에서 사용할 Radius로 스케일링
        map_data_tab3['Radius'] = map_data_tab3['Avg_Spending'] / map_data_tab3['Avg_Spending'].max() * 5000 + 1000
        map_data_tab3["pm_color"] = map_data_tab3["PM10"].apply(lambda v: get_pm10_status(v)[1])

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
            tooltip=[
    alt.Tooltip("자치구", title="자치구"),
    alt.Tooltip("PM10", title="PM10", format=",.1f"),
    alt.Tooltip("Avg_Spending", title="평균 지출액", format=",.0f")
]
        ))
        ))
        st.caption("원의 크기는 평균 지출액(배달 수요 대리 지표), 색상은 PM10 농도 상태를 나타냅니다.")
    else:
        st.warning(f"선택된 연도({year_select_tab3}년)에 해당하는 지역별 지출/PM10 데이터가 부족합니다.")

    st.markdown("---")
    st.subheader("마케팅 관점의 인사이트 (소비 패턴 활용)")
    st.markdown(
        """
        - **핵심 관계:** PM10 농도가 높을 때 (실내 체류 증가) 배달 수요와 총 지출액이 증가하는 패턴을 확인했습니다.
        - **기업 운영 및 세일 전략:**
            - **식재료 및 공급망 준비:** 미래 예측된 미세먼지 고농도 시기(예: 봄철 황사, 겨울철 고농도)에 맞춰 **식자재 재고 및 공급망**을 미리 확보하고, 배달 수요에 대응할 수 있도록 **조리 인력 배치**를 최적화해야 합니다.
            - **세일 및 프로모션 시기:** PM10 농도가 '나쁨' 이상으로 예측되는 시기에 맞춰 **'실내 안심 배달'** 프로모션이나 **'집콕 세일'** 기간을 설정함으로써, 일반적인 계절적 세일 기간과 관계없이 수요가 폭발하는 시점을 공략할 수 있습니다.
            - **타겟 마케팅:** 지도에서 확인된 **지출액(잠재 배달 수요)이 높으면서 PM10 농도가 높은 지역**을 중심으로 마케팅 예산을 집중 투입하여 효율을 높일 수 있습니다.
        """
    )


with tab4:
    st.header("4. PM10, 교통, 배달/소비 간의 상관관계 및 미래 입지 전략")
    st.markdown("주요 지표 간의 상관관계를 분석하고, 먼 미래의 환경 변화를 고려한 기업의 입지에 대한 인사이트를 도출합니다.")

    # 1. 상관관계 분석 (기존 로직 유지)
    st.subheader("주요 지표 간의 상관관계 (자치구별 평균 기준)")
    
    # 데이터프레임 병합 (교집합 기준)
    if not pol_filt.empty:
        pm10_avg_gu = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean()
    else:
        pm10_avg_gu = pd.Series()
        
    if not trans_filt.empty:
        # trans_filt에서 승객_수 합산
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
        # 상관계수 계산
        corr_mat = corr_df_gu.corr(method='pearson')

        fig, ax = plt.subplots(figsize=(7,7))
        # 히트맵 시각화
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

    st.markdown("---")
    
    # 2. 인구 이동 변화와 PM10 연계 분석 (새로운 섹션)
    st.subheader("인구 이동 변화와 PM10 농도 연계 분석 (장기 입지 전략)")
    
    if not combined_ppl.empty and not pol_filt.empty:
        # 2012년 대비 2014년 인구 이동 건수 변화 계산
        ppl_2012_pivot = combined_ppl[combined_ppl['Year'] == '2012'].set_index('자치구')['인구_이동_건수']
        ppl_2014_pivot = combined_ppl[combined_ppl['Year'] == '2014'].set_index('자치구')['인구_이동_건수']
        
        # 변화량 (2014 - 2012)
        ppl_change = (ppl_2014_pivot - ppl_2012_pivot).rename("인구_이동_변화량")
        
        # 현재 선택된 연도의 평균 PM10 농도 사용
        pm10_long_term_avg = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().rename("평균_PM10")
        
        # 데이터 통합
        ppl_pm10_comp = pd.concat([ppl_change, pm10_long_term_avg], axis=1).dropna()
        
        if not ppl_pm10_comp.empty and len(ppl_pm10_comp) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 산점도 생성
            sns.scatterplot(
                data=ppl_pm10_comp, 
                x='평균_PM10', 
                y='인구_이동_변화량', 
                ax=ax, 
                s=100, # 마커 크기
                color='purple'
            )
            
            # 자치구 라벨 추가 (시각적 판단을 돕기 위해)
            for gu, row in ppl_pm10_comp.iterrows():
                ax.text(row['평균_PM10'] * 1.01, row['인구_이동_변화량'], gu, fontsize=9)
            
            # 평균선 추가
            ax.axvline(ppl_pm10_comp['평균_PM10'].mean(), color='r', linestyle='--', linewidth=1, label='평균 PM10')
            ax.axhline(0, color='k', linestyle='-', linewidth=1, label='인구 변화량 0')
            
            ax.set_title("PM10 농도와 인구 이동 건수 변화량 관계 (2014년 - 2012년 기준)", fontsize=14)
            ax.set_xlabel(f"평균 PM10 농도 (선택 연도 기준)", fontsize=12)
            ax.set_ylabel("인구 이동 건수 변화량 (2014 - 2012)", fontsize=12)
            ax.legend(loc='lower left')
            plt.tight_layout()
            st.pyplot(fig)
            
            # 분석 인사이트
            st.markdown(
                """
                - **핵심 관계:** 이 산점도를 통해 **평균 PM10 농도가 높을수록 유동인구 수가 적어진다는 것을** 분석할 수 있습니다.
                - **입지 전략 재검토:** 만약 PM10이 높고 인구 변화량이 낮은(음수인) 사분면에 위치한 자치구가 있다면, 해당 지역은 장기적으로 거주 매력이 감소하고 있음을 시사합니다. 기업은 이 지역에 **새로운 인프라 투자를 신중하게 고려**하거나, 혹은 **공기질 개선 등 환경 요소를 고려한 차별화된 투자**를 진행해야 합니다.
                """
            )
        else:
            st.warning("인구 이동 변화 분석을 위한 데이터가 부족합니다 (자치구별 2012년/2014년 데이터 모두 필요).")
    else:
        st.warning("인구 이동 데이터(ppl_2012.csv, ppl_2014.csv) 로드에 문제가 있어 인구 분석을 수행할 수 없습니다.")
        
    st.markdown("---")
