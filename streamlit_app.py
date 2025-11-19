import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import pydeck as pdk
import os
import itertools # for combining population data

st.set_page_config(page_title="Seoul Air Quality & Lifestyle Analysis Dashboard", layout="wide")

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
            st.error(f"❌ Failed to load data file: '{file_name}'. Please check the path.")
            data_map[var_name] = pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Serious error loading '{file_name}': {e}")
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
    st.error(f"Unexpected error during data loading: {e}")
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
    st.error("🚨 PM10 data (combined_pol.csv) failed to load. Dashboard functionality is unavailable. Please check the file.")
    st.stop()
elif trans.empty:
    st.warning("⚠️ Transit data (trans.csv) failed to load. Some mobility features will be limited.")
elif spent.empty:
    st.warning("⚠️ Spending data (spent.csv) failed to load. Some consumption features will be limited.")
elif delivery.empty:
    st.warning("⚠️ Delivery data (delivery.csv) failed to load. Some consumption features will be limited.")
elif combined_ppl.empty:
    st.warning("⚠️ Population flow data (ppl_2012.csv, ppl_2014.csv) failed to load. Some correlation and locational strategy features will be limited.")

st.sidebar.header("Filter Settings")

all_years = sorted(pol['Year'].unique())
default_years = all_years[-2:] if len(all_years) >= 2 else all_years

selected_years = st.sidebar.multiselect(
    "1. Select analysis years", 
    all_years, 
    default=default_years
)

opts = ["All Districts"] + GUS
default_gus = opts[1:6] if len(opts) >= 6 else opts[1:]

selected_gus_options = st.sidebar.multiselect(
    "2. Select districts for analysis", 
    opts, 
    default=default_gus
)
if "All Districts" in selected_gus_options:
    selected_gus = GUS
else:
    selected_gus = selected_gus_options

st.sidebar.subheader("PM10 Concentration Categories (μg/m³)")
pm_colors = {
    'Good': [170, 204, 247], 'Moderate': [133, 224, 133], 
    'Bad': [255, 179, 71], 'Very Bad': [255, 118, 117]
}
for status_en, color in pm_colors.items():
    st.sidebar.markdown(
        f"<div style='display:flex; align-items:center;'>"
        f"<span style='background-color:rgb({color[0]},{color[1]},{color[2]}); width:15px; height:15px; border-radius:3px; margin-right:5px;'></span>"
        f"<span>{status_en}</span>"
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
    "PM10 Trends",
    "Mobility & PR Strategy",
    "Consumption & Marketing Strategy",
    "Correlation & Location Strategy"
])

with tab1:
    st.header("1. PM10 Concentration Trend Analysis")
    st.markdown("Visualize changes in PM10 over time and district.")

    if pol_filt.empty:
        st.warning("No PM10 data for the selected years and districts.")
    else:
        st.subheader("Daily PM10 Concentration Trend (selected districts)")
        daily_pm10_trend = pol_filt.groupby(['Date','자치구'])['미세먼지(PM10)'].mean().unstack()
        st.line_chart(daily_pm10_trend, use_container_width=True)
        st.caption("Daily average PM10 concentration trend by district")

        st.subheader("Average PM10 by District")
        avg_pm10 = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = [get_pm10_status(v)[1] for v in avg_pm10.values]
        ax.bar(avg_pm10.index, avg_pm10.values, color=[(c[0]/255, c[1]/255, c[2]/255) for c in colors])
        ax.set_xlabel("District", fontsize=12)
        ax.set_ylabel("Average PM10 (μg/m³)", fontsize=12)
        ax.set_title(f"Average PM10 by District ({', '.join(selected_years)})", fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        st.pyplot(fig)

        st.subheader("PM10 Map by District")
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
    st.header("2. PM10 and Mobility Relation Analysis (PR Strategy)")
    st.markdown("Compare PM10 changes versus public transit usage to optimize PR strategy based on high pollution periods.")

    col1, col2 = st.columns(2)
    if mobility_filt.empty:
        st.warning("No integrated PM10-Transit data for selected conditions, or failed trans.csv loading.")
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
                ax1.set_xlabel("Date")
                ax1.set_ylabel("PM10 (μg/m³)", color='blue')
                ax1.tick_params(axis='y', labelcolor='blue')
                ax2.plot(daily_comp_mobility['Date'], daily_comp_mobility['승객_수'], color='green', label='Transit Total')
                ax2.set_ylabel("Transit Total", color='green')
                ax2.tick_params(axis='y', labelcolor='green')
                ax1.set_title("PM10 & Public Transit Daily Trend")
                fig.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("Insufficient data for selected condition.")

        with col2:
            st.subheader("Mean Transit by PM10 Status")
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
                ax.set_ylabel("Mean Transit Use", fontsize=12)
                ax.set_title("Avg Daily Transit Use by PM10 Status")
                plt.xticks(rotation=0)
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("Cannot compute mean transit by PM10 status.")

        st.markdown("---")
        st.subheader("PR Insights (Mobility)")
        st.markdown(
            """
            - **Key relation:** As PM10 rises into 'Bad' or above, public transit use may decrease or growth slows, reflecting citizens staying indoors.
            - **PR strategy:** At 'Bad' periods, safety poster campaigns in subway/bus can be focused for mask and indoor safety. 'Good' periods can feature outdoor activity campaigns for psychological recovery.
            """
        )

with tab3:
    st.header("3. PM10 and Consumption Pattern Analysis (Marketing Strategy)")
    st.markdown("Analyze delivery quantity and spending variation as PM10 changes for supply-chain and sale strategy.")

    year_select_tab3 = st.selectbox("Select analysis year.", selected_years, key="tab3_year_select")
    st.subheader(f"Annual PM10 & Delivery Index Trend ({year_select_tab3})")
    delivery_comp_filt = combined_delivery[combined_delivery['Year'] == year_select_tab3].set_index('Date')

    if not delivery_comp_filt.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()
        ax1.plot(delivery_comp_filt.index, delivery_comp_filt['미세먼지(PM10)'], color='orange', label='PM10')
        ax1.set_ylabel("PM10 (μg/m³)", color='orange')
        ax1.tick_params(axis='y', labelcolor='orange')
        ax2.plot(delivery_comp_filt.index, delivery_comp_filt['배달_건수_지수'], color='red', label='Delivery Index')
        ax2.set_ylabel("Delivery Index", color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        ax1.set_title(f"{year_select_tab3} PM10 & Delivery Index Trend")
        fig.tight_layout()
        st.pyplot(fig)
        st.caption("Delivery index may rise as PM10 becomes high.")

    else:
        st.warning(f"No PM10-delivery data for {year_select_tab3}, or delivery.csv loading failed.")

    st.subheader("District Map of Delivery Spending and PM10")

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
            tooltip={"text": "{자치구}\nPM10: {PM10:.1f}\nAvg spending: {Avg_Spending:.0f}₩"}
        ))
        st.caption("Circle size is mean spending (proxy for delivery), color shows PM10.")
    else:
        st.warning(f"Insufficient spending/PM10 data for {year_select_tab3}.")

    st.markdown("---")
    st.subheader("Consumption Insights (Marketing)")
    st.markdown(
        """
        - **Key relation:** Delivery demand and total/food spending rise when PM10 is high (more people staying inside).
        - **Business & sales strategies:** Prepare material/inventory for high PM10 season, optimize kitchen/delivery capacity, and launch 'safe delivery' promotions, especially in districts with high spending and PM10.
        """
    )

with tab4:
    st.header("4. Correlation & Future Location Strategy")
    st.markdown("Analyze indicator correlation and location/investment strategy considering future air quality trends.")

    st.subheader("Correlation Matrix (District Average)")
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
        "Transit Use": transit_avg_gu,
        "Mean Spending": spending_avg_gu
    }).dropna()

    if not corr_df_gu.empty and len(corr_df_gu) >= 2:
        corr_mat = corr_df_gu.corr(method='pearson')
        fig, ax = plt.subplots(figsize=(7,7))
        sns.heatmap(corr_mat, annot=True, cmap='vlag', ax=ax, center=0, 
                    fmt=".2f", linewidths=.5, cbar_kws={'label': 'Pearson Correlation Coefficient'})
        ax.set_title("Indicator Correlation Analysis (District Average)", fontsize=14)
        ax.set_xticklabels(corr_mat.columns, rotation=45, ha='right')
        ax.set_yticklabels(corr_mat.columns, rotation=0)
        plt.tight_layout()
        st.pyplot(fig)
    elif not corr_df_gu.empty and len(corr_df_gu) < 2:
           st.warning("Not enough selected districts for correlation analysis (at least 2 required).")
    else:
        st.warning("Insufficient data for selected conditions.")

    st.markdown("---")
    st.subheader("Population Shift & PM10 Analysis (Long-term Strategy)")

    if not combined_ppl.empty and not pol_filt.empty:
        ppl_2012_pivot = combined_ppl[combined_ppl['Year'] == '2012'].set_index('자치구')['인구_이동_건수']
        ppl_2014_pivot = combined_ppl[combined_ppl['Year'] == '2014'].set_index('자치구')['인구_이동_건수']
        ppl_change = (ppl_2014_pivot - ppl_2012_pivot).rename("Population Change")
        pm10_long_term_avg = pol_filt.groupby('자치구')['미세먼지(PM10)'].mean().rename("Mean_PM10")
        ppl_pm10_comp = pd.concat([ppl_change, pm10_long_term_avg], axis=1).dropna()

        if not ppl_pm10_comp.empty and len(ppl_pm10_comp) >= 2:
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=ppl_pm10_comp, 
                x='Mean_PM10', 
                y='Population Change', 
                ax=ax, 
                s=100, 
                color='purple'
            )
            for gu, row in ppl_pm10_comp.iterrows():
                ax.text(row['Mean_PM10'] * 1.01, row['Population Change'], gu, fontsize=9)
            ax.axvline(ppl_pm10_comp['Mean_PM10'].mean(), color='r', linestyle='--', linewidth=1, label='Mean PM10')
            ax.axhline(0, color='k', linestyle='-', linewidth=1, label='Population Change 0')
            ax.set_title("Mean PM10 vs Population Change (2014 - 2012)", fontsize=14)
            ax.set_xlabel(f"Mean PM10 (selected years)", fontsize=12)
            ax.set_ylabel("Population Change (2014 - 2012)", fontsize=12)
            ax.legend(loc='lower left')
            plt.tight_layout()
            st.pyplot(fig)
            st.markdown(
                """
                - **Key relation:** High PM10 areas may show negative population change, thus long-term location strategy should favor cleaner, growing districts for investment.
                """
            )
        else:
            st.warning("Insufficient data for population change analysis (need both 2012 & 2014 by district).")
    else:
        st.warning("Population flow data failed to load. Cannot run population analysis.")

    st.markdown("---")
    st.subheader("Future-oriented Location & Infrastructure Strategy")
    st.markdown(
        """
        - **Long-term location:** Invest in health & ecology facilities in districts with cleaner air and growing population.
        - **Facilities:** Install air-cleaning indoor infrastructure for high pollution districts, ecology/outdoor for cleaner districts.
        """
    )
